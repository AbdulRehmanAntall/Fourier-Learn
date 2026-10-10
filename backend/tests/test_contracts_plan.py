import pytest
from pydantic import ValidationError

from app.contracts import LessonPlan, Level, QueryInterpretation, ScenePlan


def segment(**overrides):
    return {
        "primitive_id": "FunctionGraph",
        "content": {"f": "x**2"},
        "narration_intent": "The graph of a quadratic is a parabola.",
        "glossary_terms": ["parabola"],
    } | overrides


def plan(module_id=1, concept_id=5, **overrides):
    return {
        "module_id": module_id,
        "concept_id": concept_id,
        "segments": [segment()],
        "check_items": [1],
    } | overrides


def test_level_labels_match_the_data_dictionary():
    assert Level.STANDARD.label == "Level 2"
    assert Level.from_label("Level 1") is Level.SUPPORTED
    with pytest.raises(ValueError):
        Level.from_label("Level two")


def test_im_lost_goes_one_level_down_and_stops_at_level_1():
    assert Level.CONCISE.lower() is Level.STANDARD
    assert Level.STANDARD.lower() is Level.SUPPORTED
    assert Level.SUPPORTED.lower() is None


def test_scene_plan_carries_no_difficulty_level():
    with pytest.raises(ValidationError, match="level"):
        ScenePlan.model_validate(plan(level=2))


def test_scene_plan_needs_at_least_one_segment_with_content():
    with pytest.raises(ValidationError):
        ScenePlan.model_validate(plan(segments=[]))
    with pytest.raises(ValidationError):
        ScenePlan.model_validate(plan(segments=[segment(content={})]))


def test_check_items_are_one_or_two_and_never_repeated():
    assert ScenePlan.model_validate(plan(check_items=[1, 2])).check_items == [1, 2]
    with pytest.raises(ValidationError):
        ScenePlan.model_validate(plan(check_items=[]))
    with pytest.raises(ValidationError):
        ScenePlan.model_validate(plan(check_items=[1, 2, 3]))
    with pytest.raises(ValidationError, match="repeat"):
        ScenePlan.model_validate(plan(check_items=[4, 4]))


def test_glossary_terms_fit_the_term_column():
    with pytest.raises(ValidationError):
        ScenePlan.model_validate(plan(segments=[segment(glossary_terms=["x" * 61])]))


def test_branch_options_are_theory_or_worked_example_and_do_not_nest():
    worked = {"kind": "worked_example", "plan": plan(module_id=2)}
    assert len(ScenePlan.model_validate(plan(branch_options=[worked])).branch_options) == 1

    with pytest.raises(ValidationError):
        ScenePlan.model_validate(plan(branch_options=[{"kind": "default", "plan": plan(2)}]))
    with pytest.raises(ValidationError, match="at most once"):
        ScenePlan.model_validate(plan(branch_options=[worked, worked]))

    nested = {"kind": "theory", "plan": plan(module_id=2, branch_options=[worked])}
    with pytest.raises(ValidationError, match="cannot offer branch options"):
        ScenePlan.model_validate(plan(branch_options=[nested]))


def test_lesson_plan_ends_with_the_target_concept_and_ids_are_unique():
    prerequisite, target = plan(module_id=1, concept_id=3), plan(module_id=2, concept_id=5)
    assert len(LessonPlan(target_concept_id=5, modules=[prerequisite, target]).modules) == 2

    with pytest.raises(ValidationError, match="target concept"):
        LessonPlan(target_concept_id=5, modules=[target, prerequisite])
    with pytest.raises(ValidationError, match="unique"):
        LessonPlan(target_concept_id=5, modules=[plan(module_id=2, concept_id=3), target])


def test_query_interpretation_is_a_concept_or_out_of_scope_with_nearest_concepts():
    assert QueryInterpretation(in_scope=True, target_concept_id=5).target_concept_id == 5
    assert QueryInterpretation(in_scope=False, nearest_concept_ids=[5, 6]).in_scope is False
    with pytest.raises(ValidationError):
        QueryInterpretation(in_scope=True)
    with pytest.raises(ValidationError):
        QueryInterpretation(in_scope=False)
