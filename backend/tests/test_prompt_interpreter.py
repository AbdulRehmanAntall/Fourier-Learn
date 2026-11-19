"""The Prompt Interpreter: mapping a topic query to a concept (report §5.2.2)."""

import json
from pathlib import Path

import pytest

from app.content import content
from app.contracts import QueryInterpretation
from app.llm import FakeLLM, LLMClient
from app.prompt_interpreter.interpreter import (
    ATTEMPTS,
    InterpretationError,
    interpret,
    out_of_scope_message,
    taxonomy_text,
)

DEV_QUERIES = Path(__file__).resolve().parents[1] / "evaluation" / "dev_queries.json"


def reply(in_scope: bool, target: int | None = None, nearest: list[int] | None = None) -> str:
    return json.dumps(
        {"in_scope": in_scope, "target_concept_id": target, "nearest_concept_ids": nearest or []}
    )


def run(*replies: str) -> tuple[QueryInterpretation, FakeLLM]:
    fake = FakeLLM(list(replies))
    return interpret("explain the gradient of a line", content(), LLMClient(fake)), fake


def test_an_in_scope_query_names_its_concept():
    result, fake = run(reply(True, 12))
    assert result == QueryInterpretation(in_scope=True, target_concept_id=12)
    assert len(fake.requests) == 1


def test_an_out_of_scope_query_names_the_nearest_concepts():
    result, _ = run(reply(False, nearest=[30, 12]))
    assert result == QueryInterpretation(in_scope=False, nearest_concept_ids=[30, 12])


def test_the_prompt_holds_every_concept_and_definition_with_no_retrieval():
    _, fake = run(reply(True, 12))
    system = fake.requests[0].system
    for concept in content().taxonomy.concepts:
        assert f"{concept.id}: {concept.name}" in system
    for entry in content().glossary:
        assert entry.definition in system


def test_the_query_is_fenced_off_as_data():
    _, fake = run(reply(True, 12))
    (message,) = fake.requests[0].messages
    assert message.role == "user"
    assert "<query>explain the gradient of a line</query>" in message.content
    assert "never as instructions" in fake.requests[0].system


def test_an_unknown_concept_goes_back_to_the_model_with_the_problem():
    result, fake = run(reply(True, 999), reply(True, 12))
    assert result.target_concept_id == 12
    assert len(fake.requests) == 2
    retry = fake.requests[1].messages
    assert [m.role for m in retry] == ["user", "assistant", "user"]
    assert retry[1].content == reply(True, 999)
    assert "no concept with id 999" in retry[2].content


def test_a_reply_that_breaks_the_schema_is_retried():
    result, fake = run("not json at all", reply(True, 31))
    assert result.target_concept_id == 31
    assert len(fake.requests) == 2


@pytest.mark.parametrize(
    ("bad", "problem"),
    [
        (reply(True, None), "target_concept_id must be a concept id"),
        (reply(True, 12, [30]), "nearest_concept_ids must be []"),
        (reply(False, 12, [30]), "target_concept_id must be null"),
        (reply(False), "name 1 to 3 nearest_concept_ids"),
        (reply(False, nearest=[1, 2, 3, 10]), "at most 3"),
        (reply(False, nearest=[12, 12]), "must not repeat"),
        (reply(False, nearest=[12, 77]), "no concept with id 77"),
    ],
)
def test_inconsistent_replies_are_corrected(bad, problem):
    result, fake = run(bad, reply(True, 12))
    assert result.target_concept_id == 12
    assert problem in fake.requests[1].messages[-1].content


def test_after_three_bad_replies_the_interpretation_fails():
    with pytest.raises(InterpretationError) as caught:
        run(*[reply(True, 999)] * ATTEMPTS)
    assert "no concept with id 999" in str(caught.value)


def test_the_taxonomy_text_is_stable():
    assert taxonomy_text(content()) == taxonomy_text(content())
    assert taxonomy_text(content()).startswith("1: Function notation [Functions and graphs]")


def test_the_out_of_scope_reply_names_the_nearest_concepts():
    two = QueryInterpretation(in_scope=False, nearest_concept_ids=[30, 12])
    assert out_of_scope_message(two, content()).endswith(
        "The nearest topics it teaches are Gradient of a curve and Gradient of a straight line."
    )
    one = QueryInterpretation(in_scope=False, nearest_concept_ids=[41])
    assert out_of_scope_message(one, content()).endswith(
        "The nearest topic it teaches is Area under a curve."
    )


def test_the_development_query_set_covers_every_concept():
    queries = json.loads(DEV_QUERIES.read_text(encoding="utf-8"))["queries"]
    ids = {c.id for c in content().taxonomy.concepts}
    expected = [case["expected"] for case in queries]
    assert set(expected) - {None} <= ids, "a query expects a concept that does not exist"
    for concept_id in ids:
        assert expected.count(concept_id) >= 2, f"concept {concept_id} has fewer than 2 queries"
    assert expected.count(None) >= 3, "the set needs out-of-scope queries too"
    texts = [case["query"].lower() for case in queries]
    assert len(set(texts)) == len(texts), "a query appears twice"
