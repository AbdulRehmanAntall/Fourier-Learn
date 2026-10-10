import json
from pathlib import Path

from app.contracts import ModuleRenderRequest, ScenePlan, variant_cache_key

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_example_scene_plan_is_valid():
    plan = ScenePlan.model_validate_json((EXAMPLES / "gradient_of_line.plan.json").read_text())
    assert [s.primitive_id for s in plan.segments] == ["GradientTriangle", "EquationTransform"]
    assert plan.branch_options[0].kind == "worked_example"


def test_example_render_request_is_valid_and_matches_its_plan():
    raw = (EXAMPLES / "gradient_of_line.render.json").read_text()
    request = ModuleRenderRequest.model_validate_json(raw)
    plan = ScenePlan.model_validate(
        json.loads((EXAMPLES / "gradient_of_line.plan.json").read_text())
    )

    # Every variant has the same beats, in the same order, as the plan's segments.
    assert [b.primitive_id for b in request.beats] == [s.primitive_id for s in plan.segments]
    assert request.module_id == plan.module_id
    assert len(variant_cache_key(request)) == 64
