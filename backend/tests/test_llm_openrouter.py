"""The OpenRouter provider, against a fake HTTP layer (no network, no API key)."""

import json

import pytest
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.llm import LLMClient, LLMError, LLMNotConfiguredError, LLMRequest, Message, get_client
from app.llm.openrouter import HTTPResponse, OpenRouterLLM


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: int


def completion(content: str | None, model: str = "vendor/model-a") -> HTTPResponse:
    body = {
        "model": model,
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 8},
    }
    return HTTPResponse(200, {}, json.dumps(body))


class FakeHTTP:
    def __init__(self, *responses: HTTPResponse) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict, dict, float]] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, json.loads(body), timeout))
        return self.responses.pop(0)


def provider(http: FakeHTTP, waits: list[float] | None = None) -> OpenRouterLLM:
    return OpenRouterLLM(
        api_key="test-key",
        model="vendor/model-a",
        base_url="https://openrouter.test/api/v1/",
        timeout_s=30,
        post=http,
        sleep=(waits.append if waits is not None else lambda _: None),
    )


REQUEST = LLMRequest(
    purpose="interpret",
    system="You map queries to concepts.",
    messages=(Message("user", "gradient"), Message("assistant", "{}"), Message("user", "fix it")),
    schema_name="Answer",
    schema=Answer.model_json_schema(),
    max_output_tokens=300,
)


def test_the_request_follows_the_chat_completions_format():
    http = FakeHTTP(completion('{"concept_id": 12}'))
    provider(http).complete(REQUEST)
    ((url, headers, body, timeout),) = http.calls
    assert url == "https://openrouter.test/api/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    assert timeout == 30
    assert body["model"] == "vendor/model-a"
    assert body["max_tokens"] == 300
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user"]
    assert body["messages"][0]["content"].startswith("You map queries to concepts.")
    assert body["messages"][3]["content"] == "fix it"


def test_structured_output_is_requested_and_the_schema_is_in_the_prompt():
    http = FakeHTTP(completion('{"concept_id": 12}'))
    provider(http).complete(REQUEST)
    body = http.calls[0][2]
    response_format = body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "Answer"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == Answer.model_json_schema()
    assert '"concept_id"' in body["messages"][0]["content"]


def test_the_reply_text_model_and_token_counts_are_returned():
    reply = provider(FakeHTTP(completion('{"concept_id": 12}', "vendor/model-a:free"))).complete(
        REQUEST
    )
    assert reply.text == '{"concept_id": 12}'
    assert reply.model == "vendor/model-a:free"
    assert (reply.input_tokens, reply.output_tokens) == (120, 8)


def test_a_rate_limit_is_retried_after_the_wait_it_asks_for():
    waits: list[float] = []
    http = FakeHTTP(
        HTTPResponse(429, {"Retry-After": "3"}, '{"error": {"message": "Rate limit exceeded"}}'),
        HTTPResponse(503, {}, "{}"),
        completion('{"concept_id": 1}'),
    )
    assert provider(http, waits).complete(REQUEST).text == '{"concept_id": 1}'
    assert len(http.calls) == 3
    assert waits == [3.0, 2.0]


def test_after_the_last_attempt_the_error_is_reported():
    http = FakeHTTP(*[HTTPResponse(429, {}, '{"error": {"message": "Rate limit exceeded"}}')] * 3)
    with pytest.raises(LLMError, match="429: Rate limit exceeded"):
        provider(http).complete(REQUEST)


def test_a_client_error_is_not_retried():
    http = FakeHTTP(HTTPResponse(401, {}, '{"error": {"message": "No auth credentials found"}}'))
    with pytest.raises(LLMError, match="401: No auth credentials found"):
        provider(http).complete(REQUEST)
    assert len(http.calls) == 1


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (HTTPResponse(200, {}, "not json"), "not JSON"),
        (HTTPResponse(200, {}, '{"error": {"message": "model unavailable"}}'), "unavailable"),
        (HTTPResponse(200, {}, '{"choices": []}'), "no choices"),
        (completion(None), "empty reply"),
    ],
)
def test_unusable_bodies_are_llm_errors(response, message):
    with pytest.raises(LLMError, match=message):
        provider(FakeHTTP(response)).complete(REQUEST)


def test_the_client_validates_what_openrouter_returns():
    client = LLMClient(provider(FakeHTTP(completion('```json\n{"concept_id": 30}\n```'))))
    result = client.structured(
        purpose="t", system="s", messages=[Message("user", "q")], output=Answer
    )
    assert result.value.concept_id == 30


def test_openrouter_needs_a_key_and_a_model(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    with pytest.raises(LLMNotConfiguredError, match="LLM_API_KEY and LLM_MODEL"):
        get_client()
    monkeypatch.setattr(settings, "llm_api_key", "k")
    monkeypatch.setattr(settings, "llm_model", "vendor/model-a:free")
    client = get_client()
    assert isinstance(client.provider, OpenRouterLLM)
    assert client.provider.model == "vendor/model-a:free"
