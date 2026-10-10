from pathlib import Path

import pytest

from app.contracts import Level, ModuleRenderRequest, ScenePlan, variant_cache_key

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PLAN = ScenePlan.model_validate_json((EXAMPLES / "gradient_of_line.plan.json").read_text())


def load_request(level: Level) -> ModuleRenderRequest:
    path = EXAMPLES / f"gradient_of_line.L{int(level)}.render.json"
    return ModuleRenderRequest.model_validate_json(path.read_text())


def test_example_scene_plan_is_valid():
    assert [s.primitive_id for s in PLAN.segments] == [
        "FunctionGraph",
        "GradientTriangle",
        "EquationTransform",
    ]
    assert PLAN.branch_options[0].kind == "worked_example"


@pytest.mark.parametrize("level", list(Level))
def test_example_render_requests_match_the_plan(level):
    request = load_request(level)
    assert request.level is level
    assert request.module_id == PLAN.module_id
    # Every variant has the same beats, in the same order, as the plan's segments.
    assert [b.primitive_id for b in request.beats] == [s.primitive_id for s in PLAN.segments]


def test_the_three_levels_are_three_variants():
    keys = {variant_cache_key(load_request(level)) for level in Level}
    assert len(keys) == 3
