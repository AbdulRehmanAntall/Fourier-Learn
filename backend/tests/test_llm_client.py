"""The language-model client: structured output, validation and the call log (app/llm)."""

import json

import pytest
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.llm import (
    FakeLLM,
    LLMClient,
    LLMError,
    LLMNotConfiguredError,
    LLMOutputError,
    Message,
    get_client,
)
from app.llm.client import strip_code_fence


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: int
    reason: str


def ask(client: LLMClient):
    return client.structured(
        purpose="test",
        system="Answer with JSON.",
        messages=[Message("user", "Which concept?")],
        output=Answer,
    )


def test_a_valid_reply_is_parsed_and_its_text_kept():
    client = LLMClient(FakeLLM(['{"concept_id": 12, "reason": "gradient"}']))
    result = ask(client)
    assert result.value == Answer(concept_id=12, reason="gradient")
    assert json.loads(result.text) == {"concept_id": 12, "reason": "gradient"}


def test_the_provider_receives_the_schema_and_conversation():
    fake = FakeLLM(['{"concept_id": 1, "reason": "x"}'])
    ask(LLMClient(fake))
    (request,) = fake.requests
    assert request.purpose == "test"
    assert request.schema_name == "Answer"
    assert request.schema == Answer.model_json_schema()
    assert request.messages == (Message("user", "Which concept?"),)


def test_an_invalid_reply_raises_with_problems_the_model_can_act_on():
    client = LLMClient(FakeLLM(['{"concept_id": "twelve", "extra": 1}']))
    with pytest.raises(LLMOutputError) as caught:
        ask(client)
    problems = " | ".join(caught.value.problems)
    assert "concept_id" in problems
    assert "reason" in problems  # missing
    assert "extra" in problems  # not allowed
    assert caught.value.text == '{"concept_id": "twelve", "extra": 1}'


def test_a_reply_that_is_not_json_is_an_output_error():
    with pytest.raises(LLMOutputError):
        ask(LLMClient(FakeLLM(["I think it is concept 12."])))


def test_a_code_fence_around_the_json_is_tolerated():
    fenced = '```json\n{"concept_id": 3, "reason": "quadratic"}\n```'
    assert ask(LLMClient(FakeLLM([fenced]))).value.concept_id == 3
    assert strip_code_fence("no fence") == "no fence"


def test_a_failed_call_is_an_llm_error():
    with pytest.raises(LLMError):
        ask(LLMClient(FakeLLM([])))


def test_a_scripted_reply_can_depend_on_the_request():
    fake = FakeLLM([lambda request: json.dumps({"concept_id": 7, "reason": request.purpose})])
    assert ask(LLMClient(fake)).value.reason == "test"


def test_every_call_is_logged_as_one_json_line(tmp_path):
    log = tmp_path / "logs" / "llm.jsonl"
    client = LLMClient(
        FakeLLM(['{"concept_id": 12, "reason": "ok"}', '{"concept_id": "bad"}']), log
    )
    ask(client)
    with pytest.raises(LLMOutputError):
        ask(client)
    good, bad = (json.loads(line) for line in log.read_text(encoding="utf-8").splitlines())
    assert good["valid"] is True
    assert good["purpose"] == "test"
    assert good["provider"] == "fake"
    assert good["schema"] == "Answer"
    assert good["messages"] == [{"role": "user", "content": "Which concept?"}]
    assert good["reply"] == '{"concept_id": 12, "reason": "ok"}'
    assert good["problems"] == []
    assert bad["valid"] is False
    assert bad["problems"]


def test_a_failed_call_is_logged_too(tmp_path):
    log = tmp_path / "llm.jsonl"
    with pytest.raises(LLMError):
        ask(LLMClient(FakeLLM([]), log))
    record = json.loads(log.read_text(encoding="utf-8"))
    assert record["valid"] is False
    assert record["reply"] is None


def test_without_a_provider_the_client_is_not_configured(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "")
    with pytest.raises(LLMNotConfiguredError, match="LLM_PROVIDER"):
        get_client()
    monkeypatch.setattr(get_settings(), "llm_provider", "no-such-provider")
    with pytest.raises(LLMNotConfiguredError, match="Unknown"):
        get_client()
