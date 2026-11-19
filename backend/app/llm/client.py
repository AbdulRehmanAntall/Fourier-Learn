"""The language-model client of the generation pipeline (report §5.2.2, §5.2.3, §5.3.3, §5.4.2).

Every call asks for structured output. The caller passes a Pydantic model, the provider is asked
for JSON that matches the model's JSON Schema, and the reply is validated against the model. A
reply that does not validate raises `LLMOutputError`, which lists the problems, so the caller can
send them back to the model and try again (§5.2.3, §5.3.3).

Every request and reply is appended to a JSON Lines log, one line per call. The evaluation of
§5.9.1 reads it: the plan and parameter validity rates are counted from these lines, and the
candidate models are compared on them.

Providers:
- `OpenRouterLLM` (app/llm/openrouter.py): many hosted models behind one API key. The model is
  chosen with LLM_MODEL.
- `FakeLLM`: scripted replies, for tests and CI. Needs no network or API key.

The planning model is chosen during development on the plan validity rate (§5.2.1), so nothing
outside app/llm may depend on a particular provider. Another provider is added as one more
`LLMProvider` and registered in `_PROVIDERS`.
"""

import json
import re
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings


class LLMError(RuntimeError):
    """The model could not be called, or did not answer."""


class LLMNotConfiguredError(LLMError):
    """No language model is set up (LLM_PROVIDER is empty)."""


class LLMOutputError(LLMError):
    """The model answered, but its reply is not valid against the requested schema."""

    def __init__(self, problems: list[str], text: str) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems
        self.text = text


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMRequest:
    """One call to the model, in a form every provider can translate."""

    purpose: str
    """What the call is for, such as "interpret" or "plan". Recorded in the log."""
    system: str
    messages: tuple[Message, ...]
    schema_name: str
    schema: dict
    """The JSON Schema the reply must follow."""
    max_output_tokens: int = 4000


@dataclass(frozen=True)
class LLMReply:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(ABC):
    name: ClassVar[str]

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMReply:
        """Send `request` and return the model's reply. Raise `LLMError` if no reply came."""


@dataclass(frozen=True)
class Structured[T: BaseModel]:
    """A validated reply, with the text it came from (needed to continue the conversation)."""

    value: T
    text: str


Script = str | Callable[[LLMRequest], str]


@dataclass
class FakeLLM(LLMProvider):
    """Plays back scripted replies in order and records every request it receives.

    A reply is either the text to return or a function of the request that returns it.
    """

    replies: list[Script] = field(default_factory=list)
    requests: list[LLMRequest] = field(default_factory=list)

    name: ClassVar[str] = "fake"

    def complete(self, request: LLMRequest) -> LLMReply:
        self.requests.append(request)
        if not self.replies:
            raise LLMError("FakeLLM has no scripted reply left")
        reply = self.replies.pop(0)
        text = reply(request) if callable(reply) else reply
        return LLMReply(text=text, model="fake")


class LLMClient:
    """Calls a provider for structured output and logs every call."""

    def __init__(self, provider: LLMProvider, log_path: Path | None = None) -> None:
        self.provider = provider
        self.log_path = log_path
        self._lock = threading.Lock()

    def structured[T: BaseModel](
        self,
        *,
        purpose: str,
        system: str,
        messages: Sequence[Message],
        output: type[T],
        max_output_tokens: int = 4000,
    ) -> Structured[T]:
        """Ask the model for a reply that validates as `output`.

        Raises `LLMOutputError` when the reply does not validate, and `LLMError` when the model
        could not be called.
        """
        request = LLMRequest(
            purpose=purpose,
            system=system,
            messages=tuple(messages),
            schema_name=output.__name__,
            schema=output.model_json_schema(),
            max_output_tokens=max_output_tokens,
        )
        started = time.monotonic()
        try:
            reply = self.provider.complete(request)
        except LLMError as error:
            self._log(request, None, started, [str(error)])
            raise
        try:
            value = output.model_validate_json(strip_code_fence(reply.text))
        except ValidationError as error:
            problems = validation_problems(error)
            self._log(request, reply, started, problems)
            raise LLMOutputError(problems, reply.text) from error
        self._log(request, reply, started, [])
        return Structured(value=value, text=reply.text)

    def _log(
        self, request: LLMRequest, reply: LLMReply | None, started: float, problems: list[str]
    ) -> None:
        if self.log_path is None:
            return
        record = {
            "at": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "purpose": request.purpose,
            "provider": self.provider.name,
            "model": reply.model if reply else None,
            "schema": request.schema_name,
            "system": request.system,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "reply": reply.text if reply else None,
            "valid": reply is not None and not problems,
            "problems": problems,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "input_tokens": reply.input_tokens if reply else None,
            "output_tokens": reply.output_tokens if reply else None,
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as log:
                log.write(line + "\n")


_FENCE = re.compile(r"^\s*```(?:json)?\s*\n(.*)\n\s*```\s*$", re.DOTALL)


def strip_code_fence(text: str) -> str:
    """The JSON inside a Markdown code fence, which some models add even when asked not to."""
    match = _FENCE.match(text)
    return match.group(1) if match else text


def validation_problems(error: ValidationError) -> list[str]:
    """The errors of a failed validation, as sentences the model can act on."""
    problems = []
    for item in error.errors():
        where = ".".join(str(part) for part in item["loc"]) or "the reply"
        problems.append(f"{where}: {item['msg']}")
    return problems


def _openrouter() -> LLMProvider:
    from app.llm.openrouter import OpenRouterLLM

    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("LLM_API_KEY", settings.llm_api_key),
            ("LLM_MODEL", settings.llm_model),
        )
        if not value.strip()
    ]
    if missing:
        raise LLMNotConfiguredError(f"LLM_PROVIDER is openrouter, so set {' and '.join(missing)}.")
    return OpenRouterLLM(
        api_key=settings.llm_api_key.strip(),
        model=settings.llm_model.strip(),
        base_url=settings.llm_base_url,
        timeout_s=settings.llm_timeout_s,
    )


_PROVIDERS: dict[str, Callable[[], LLMProvider]] = {
    FakeLLM.name: FakeLLM,
    "openrouter": _openrouter,
}


def get_client() -> LLMClient:
    """The client for the provider named by LLM_PROVIDER, logging to LLM_LOG_PATH."""
    settings = get_settings()
    name = settings.llm_provider.strip().lower()
    if not name:
        raise LLMNotConfiguredError(
            "No language model is configured. Set LLM_PROVIDER (and LLM_API_KEY) in backend/.env."
        )
    if name not in _PROVIDERS:
        known = ", ".join(sorted(_PROVIDERS))
        raise LLMNotConfiguredError(f"Unknown LLM_PROVIDER {name!r}. Known providers: {known}.")
    return LLMClient(_PROVIDERS[name](), settings.llm_log_path)
