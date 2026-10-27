"""IndexLaws: an expression simplified one index law at a time, each step labelled with the law
it uses (4024 1.7, 2.4; PRIMITIVES.md #8).

The model writes the lines and names the law of each step; SymPy checks that every line equals
the one before (letters are taken as positive, as O Level does for indices), so the working is
right and the law is shown where it is used: aᵐ × aⁿ = aᵐ⁺ⁿ, aᵐ ÷ aⁿ = aᵐ⁻ⁿ, (aᵐ)ⁿ = aᵐⁿ,
(ab)ⁿ = aⁿbⁿ, a⁰ = 1, a⁻ⁿ = 1/aⁿ, a^(1/n) = ⁿ√a.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import DOWN, LEFT, MathTex, SurroundingRectangle, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import inline
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import ExpressionError, format_value, parse_expression, written_latex

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Law = Literal["multiply", "divide", "power", "product", "zero", "negative", "fractional",
              "evaluate"]  # fmt: skip
LAWS = {
    "multiply": (r"a^m \times a^n = a^{m+n}", "Multiplying: add the indices"),
    "divide": (r"a^m \div a^n = a^{m-n}", "Dividing: subtract the indices"),
    "power": (r"\left(a^m\right)^n = a^{mn}", "A power of a power: multiply the indices"),
    "product": (r"(ab)^n = a^n b^n", "Raise each factor of the bracket to the power"),
    "zero": (r"a^0 = 1", "Anything to the power 0 is 1"),
    "negative": (r"a^{-n} = \tfrac{1}{a^n}", "A negative index means one over"),
    "fractional": (r"a^{\frac{1}{n}} = \sqrt[n]{a}", "A fractional index is a root"),
    "evaluate": (r"\text{work it out}", "Work out the numbers"),
}


class IndexLawsParams(PrimitiveParams):
    lines: list[Line] = Field(
        min_length=2,
        max_length=6,
        description='The working, e.g. ["x**3 * x**4", "x**(3 + 4)", "x**7"]',
    )
    laws: list[Law] = Field(
        min_length=1, max_length=5, description="The law used to reach each line after the first"
    )


class IndexLaws(StagedPrimitive[IndexLawsParams]):
    primitive_id = "IndexLaws"
    version = "1"
    topic = "Number"
    params_model = IndexLawsParams
    layout = LayoutContract(region=style.WORKING_REGION, allowed_overlaps=[("result_box", "*")])

    def default_params(self) -> IndexLawsParams:
        return IndexLawsParams(
            lines=["(2*x**3)**2 / (4*x**2)", "4*x**6 / (4*x**2)", "x**(6 - 2)", "x**4"],
            laws=["product", "divide", "evaluate"],
        )

    def validate(self, params: IndexLawsParams) -> list[PredicateFailure]:
        if len(params.laws) != len(params.lines) - 1:
            return [_failure("consistency", "one_law_per_step",
                             "give one law for each line after the first", "laws")]  # fmt: skip
        parsed = []
        for i, line in enumerate(params.lines):
            try:
                parsed.append(_positive(parse_expression(line, evaluate=False)))
            except ExpressionError as error:
                return [_failure("parsing", "line_parses", str(error), f"lines[{i}]")]
        for i in range(1, len(parsed)):
            if sp.simplify(parsed[i] - parsed[i - 1]) != 0:
                message = f"line {i + 1} does not equal line {i}"
                return [_failure("consistency", "step_equivalent", message, f"lines[{i}]")]
        return []

    def computed_values(self, params: IndexLawsParams) -> dict[str, str]:
        last = _positive(parse_expression(params.lines[-1]))
        return {"result": format_value(last) if last.is_number else str(last)}

    def build(self, params: IndexLawsParams, level):
        box = style.region_box(self.layout.region).shrink(style.PADDING)
        rows = []
        parts = {}
        for i, text in enumerate(params.lines):
            tex = written_latex(text)
            line = MathTex(tex if i == 0 else f"= {tex}", font_size=style.FONT_SIZE)
            parts[f"line_{i + 1}"] = line
            rows.append(line)
            if i < len(params.laws):
                law, _ = LAWS[params.laws[i]]
                note = MathTex(inline(law), font_size=28, color=style.HIGHLIGHT_COLOUR)
                parts[f"law_{i + 1}"] = note
                rows.append(note)
        for row in rows:
            if row.width > box.width:
                row.scale_to_fit_width(box.width)
        group = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=0.22)
        for i in range(len(params.laws)):
            parts[f"law_{i + 1}"].shift([0.4, 0, 0])  # notes sit indented under their line
        style.fit_inside(group, box)
        parts["result_box"] = SurroundingRectangle(rows[-1], color=style.HIGHLIGHT_COLOUR,
                                                   buff=0.1)  # fmt: skip
        return parts

    def stages(self, params: IndexLawsParams, level) -> list[Stage]:
        steps = [stage("line_1", "Here is the expression", 1.5, ["line_1"])]
        for i, law in enumerate(params.laws, start=1):
            _, words = LAWS[law]
            steps.append(stage(f"law_{i}", words, 2.5, [f"law_{i}"], emphasise=[f"law_{i}"]))
            steps.append(stage(f"line_{i + 1}", "Write the result", 2.0, [f"line_{i + 1}"]))
        steps[-1] = combine(steps[-1].name, "So the answer is", 2.0, steps[-1],
                            stage("box", "", 0.1, ["result_box"]))  # fmt: skip

        def standard(s):
            out = [s[0]]
            for k in range(1, len(s), 2):
                out.append(combine(s[k + 1].name, s[k].description, 2.5, s[k], s[k + 1]))
            return out

        def concise(s):
            return [s[0], combine("working", "Use the index laws", 3.5, *s[1:])]

        return by_level(level, steps, standard, concise)


def _positive(expr: sp.Expr) -> sp.Expr:
    """Letters as positive numbers, so (x**2)**(1/2) is x, as in O Level index work."""
    return expr.subs({s: sp.Symbol(s.name, positive=True) for s in expr.free_symbols})


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
