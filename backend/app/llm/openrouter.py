"""OpenRouter (https://openrouter.ai): one API key for many hosted models, open and commercial.

OpenRouter speaks the OpenAI chat-completions format, so changing the model is only a change of
LLM_MODEL. Models whose id ends in ":free" cost nothing but are rate-limited.

Structured output is requested with `response_format` of type `json_schema`. Not every model
behind OpenRouter enforces it, so the schema is also stated in the system prompt, and the client
validates the reply in any case (app/llm/client.py).

Only the standard library is used for HTTP, so the runtime needs no extra package.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from app.llm.client import LLMError, LLMProvider, LLMReply, LLMRequest

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
# Statuses worth another try: rate limit, and the gateway or the model's host being unavailable.
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
ATTEMPTS = 3
MAX_WAIT_S = 20.0


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    headers: dict[str, str]
    body: str


# (url, headers, JSON body, timeout in seconds) -> response. Replaced in tests.
Post = Callable[[str, dict[str, str], bytes, float], HTTPResponse]


def urllib_post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> HTTPResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HTTPResponse(
                response.status, dict(response.headers), response.read().decode("utf-8")
            )
    except urllib.error.HTTPError as error:
        return HTTPResponse(
            error.code, dict(error.headers), error.read().decode("utf-8", "replace")
        )
    except (urllib.error.URLError, TimeoutError) as error:
        raise LLMError(f"OpenRouter could not be reached: {error}") from error


class OpenRouterLLM(LLMProvider):
    name: ClassVar[str] = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 60.0,
        post: Post = urllib_post,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout_s = timeout_s
        self.post = post
        self.sleep = sleep

    def payload(self, request: LLMRequest) -> dict:
        system = (
            f"{request.system}\n\nReply with one JSON object, and nothing else, that matches "
            f"this JSON Schema:\n{json.dumps(request.schema, sort_keys=True)}"
        )
        messages = [{"role": "system", "content": system}]
        messages += [{"role": m.role, "content": m.content} for m in request.messages]
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.schema,
                },
            },
        }

    def complete(self, request: LLMRequest) -> LLMReply:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Optional attribution headers that OpenRouter shows on its dashboard.
            "X-Title": "FourierLearn",
        }
        body = json.dumps(self.payload(request)).encode("utf-8")
        response = None
        for attempt in range(ATTEMPTS):
            response = self.post(self.url, headers, body, self.timeout_s)
            if response.status not in RETRY_STATUSES or attempt == ATTEMPTS - 1:
                break
            self.sleep(_wait(response, attempt))
        assert response is not None
        if response.status != 200:
            raise LLMError(
                f"OpenRouter returned {response.status}: {_error_message(response.body)}"
            )
        return _reply(response.body, self.model)


def _wait(response: HTTPResponse, attempt: int) -> float:
    retry_after = {k.lower(): v for k, v in response.headers.items()}.get("retry-after")
    try:
        seconds = float(retry_after) if retry_after else 2.0**attempt
    except ValueError:
        seconds = 2.0**attempt
    return min(max(seconds, 0.0), MAX_WAIT_S)


def _error_message(body: str) -> str:
    try:
        error = json.loads(body).get("error", {})
    except (ValueError, AttributeError):
        return body[:300]
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])[:300]
    return body[:300]


def _reply(body: str, requested_model: str) -> LLMReply:
    try:
        data = json.loads(body)
    except ValueError as error:
        raise LLMError("OpenRouter returned a body that is not JSON") from error
    if data.get("error"):
        raise LLMError(f"OpenRouter returned an error: {_error_message(body)}")
    try:
        choice = data["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LLMError("OpenRouter returned no choices") from error
    if not content:
        reason = choice.get("finish_reason") or "unknown"
        raise LLMError(f"OpenRouter returned an empty reply (finish reason: {reason})")
    usage = data.get("usage") or {}
    return LLMReply(
        text=content,
        model=data.get("model") or requested_model,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )
