"""The teaching content (backend/content/) and the scene-plan reference check (§5.2.3)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.content import CONTENT_DIR, load_content
from app.contracts import ScenePlan
from app.prompt_interpreter.plan_checks import References, expression_problem, reference_problems
from app.renderer.store import cache_key_for, playable_beats

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def copy_content(tmp_path: Path, change=None) -> Path:
    data = {name: json.loads((CONTENT_DIR / name).read_text()) for name in
            ("concepts.json", "glossary.json", "items.json")}  # fmt: skip
    if change:
        change(data)
    for name, value in data.items():
        (tmp_path / name).write_text(json.dumps(value))
    return tmp_path


def test_the_content_is_consistent():
    content = load_content()
    order = content.taxonomy.order()
    position = {concept: i for i, concept in enumerate(order)}
    for concept in content.taxonomy.concepts:
        for prerequisite in concept.prerequisites:
            assert position[prerequisite] < position[concept.id]
    # Every chip of the example module has a definition.
    terms = {g.term for g in content.glossary}
    assert {"graph", "coordinates", "gradient", "rise", "run"} <= terms


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["concepts.json"]["concepts"][0]["prerequisites"].append(2), "cycle"),
        (lambda d: d["concepts.json"]["concepts"][0]["prerequisites"].append(999), "unknown"),
        (lambda d: d["glossary.json"].append(dict(d["glossary.json"][0], id=99)), "twice"),
        (lambda d: d["items.json"][1].update(correct_option="$7$"), "not one of the options"),
        (lambda d: d["items.json"][0].update(options=["Yes", "No"]), "True and False"),
    ],
)
def test_content_mistakes_are_caught(tmp_path, change, message):
    # Concept 2 needs concept 1, so making 1 need 2 is a cycle.
    with pytest.raises(ValidationError, match=message):
        load_content(copy_content(tmp_path, change))


def references(**overrides) -> References:
    content = load_content()
    values = {
        "primitive_ids": {"FunctionGraph", "GradientTriangle", "EquationTransform"},
        "concept_ids": {c.id for c in content.taxonomy.concepts},
        "glossary_terms": {g.term.lower() for g in content.glossary},
        "check_ids": {i.id for i in content.items},
    }
    return References(**(values | overrides))


def test_the_example_plan_passes_the_reference_check():
    plan = ScenePlan.model_validate_json((EXAMPLES / "gradient_of_line.plan.json").read_text())
    assert reference_problems(plan, references()) == []


def test_the_reference_check_names_every_problem():
    plan = ScenePlan.model_validate_json((EXAMPLES / "gradient_of_line.plan.json").read_text())
    problems = reference_problems(
        plan, references(primitive_ids={"FunctionGraph"}, glossary_terms={"graph"}, check_ids=set())
    )
    assert "plan, segment 1: there is no primitive named 'GradientTriangle'" in problems
    assert "plan, segment 0: the glossary has no term 'coordinates'" in problems
    assert "plan: check item 2 is not in the item bank" in problems
    # The worked-example branch is checked too.
    assert "plan, worked_example branch: check item 3 is not in the item bank" in problems


@pytest.mark.parametrize(
    ("text", "parses"),
    [
        ("(1, 2)", True),
        ("(-1, sqrt(2))", True),
        ("(7 - (-1))/(3 - (-1))", True),
        ("y = 2*x + 1", True),
        ("x +* 2", False),
        ("__import__('os')", False),
        ("(1, 2, 3)", False),
    ],
)
def test_expressions_in_a_plan(text, parses):
    assert (expression_problem(text) is None) is parses


def test_the_cache_key_names_the_voice_engine():
    request = json.loads((EXAMPLES / "gradient_of_line.L2.render.json").read_text())
    from app.contracts import ModuleRenderRequest

    parsed = ModuleRenderRequest.model_validate(request)
    assert cache_key_for(parsed, "kokoro") != cache_key_for(parsed, "espeak")
    assert cache_key_for(parsed, "kokoro") == cache_key_for(parsed, "kokoro")


def test_a_partial_manifest_lists_only_beats_that_can_be_played_in_order():
    beats = {i: f"beat {i}" for i in (0, 2, 3)}
    assert playable_beats(beats, 0) == ["beat 0"]
    assert playable_beats(beats, 2) == ["beat 2", "beat 3"]
    assert playable_beats(beats, 1) == []
