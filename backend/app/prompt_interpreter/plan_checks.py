"""The reference check of a scene plan (report §5.2.3).

The schema check is the ScenePlan model itself (app/contracts/scene_plan.py). The reference
check needs the library and the taxonomy: every primitive the plan names exists, every glossary
term and check item exists, the concept exists, and every expression in the segments parses.
A plan that fails either check is sent back to the planning model with the problems listed.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass

from app.contracts import ScenePlan
from app.primitives.symbolic import ExpressionError, parse_equation, parse_expression

# A point written as "(1, 2)": each coordinate is checked as an expression.
_POINT = re.compile(r"^\(\s*([^,()]+(?:\([^()]*\))?[^,()]*)\s*,\s*(.+)\)$")


@dataclass(frozen=True)
class References:
    """What a plan may refer to: the library, the taxonomy, the glossary and the item bank."""

    primitive_ids: Collection[str]
    concept_ids: Collection[int]
    glossary_terms: Collection[str]
    """Lower-case."""
    check_ids: Collection[int]


def reference_problems(plan: ScenePlan, refs: References, where: str = "plan") -> list[str]:
    """Every reference in `plan` that does not resolve, as a sentence the model can act on."""
    problems = []
    if plan.concept_id not in refs.concept_ids:
        problems.append(f"{where}: concept {plan.concept_id} is not in the taxonomy")
    for index, segment in enumerate(plan.segments):
        at = f"{where}, segment {index}"
        if segment.primitive_id not in refs.primitive_ids:
            problems.append(f"{at}: there is no primitive named {segment.primitive_id!r}")
        for term in segment.glossary_terms:
            if term.lower() not in refs.glossary_terms:
                problems.append(f"{at}: the glossary has no term {term!r}")
        for name, expression in segment.content.items():
            problem = expression_problem(expression)
            if problem:
                problems.append(f"{at}: {name} = {expression!r} {problem}")
    for item in plan.check_items:
        if item not in refs.check_ids:
            problems.append(f"{where}: check item {item} is not in the item bank")
    for option in plan.branch_options:
        problems += reference_problems(option.plan, refs, f"{where}, {option.kind} branch")
    return problems


def expression_problem(text: str) -> str | None:
    """Why `text` is not a well-formed expression, equation or point, or None if it is."""
    point = _POINT.match(text.strip())
    parts = list(point.groups()) if point else [text]
    try:
        for part in parts:
            if "=" in part:
                parse_equation(part)
            else:
                parse_expression(part)
    except ExpressionError as error:
        return f"does not parse: {error}"
    return None
