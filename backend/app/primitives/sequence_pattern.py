"""SequencePattern: the first terms of a sequence, their differences (or ratios) and the nth
term worked out from them (4024 2.7; PRIMITIVES.md #17).

Linear sequences have a constant first difference d, so the nth term starts dn; the row dn is
compared with the terms to find the constant. Quadratic sequences have a constant second
difference 2a, so the nth term starts an²; what is left is linear. Cubic sequences have a
constant third difference; geometric (exponential) sequences a constant ratio. A growing dot
pattern can be shown above the terms. The kind and the nth term are found by SymPy.
"""

from typing import Annotated

import sympy as sp
from manim import Circle, MathTex, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import exact, format_number, latex_number, tidy_latex

N = sp.Symbol("n", integer=True, positive=True)
Term = Annotated[float, Field(ge=-10000, le=10000)]
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}


class SequencePatternParams(PrimitiveParams):
    terms: list[Term] = Field(
        min_length=4, max_length=6, description="The first terms of the sequence, from n = 1"
    )
    show_pattern: bool = Field(
        default=False,
        description="Draw each term as a growing pattern of dots (positive whole terms up to 30)",
    )


class SequencePattern(StagedPrimitive[SequencePatternParams]):
    primitive_id = "SequencePattern"
    version = "1"
    topic = "Algebra and graphs"
    params_model = SequencePatternParams
    layout = LayoutContract(region=style.GRAPH_REGION)

    def default_params(self) -> SequencePatternParams:
        return SequencePatternParams(terms=[5, 8, 11, 14], show_pattern=True)

    def validate(self, params: SequencePatternParams) -> list[PredicateFailure]:
        if _analyse(params) is None:
            message = (
                "no linear, quadratic, cubic or geometric rule fits these terms; a cubic needs "
                "5 terms"
            )
            return [_failure("consistency", "pattern_found", message, "terms")]
        if params.show_pattern and not all(
            float(t).is_integer() and 1 <= t <= 30 for t in params.terms
        ):
            message = "a dot pattern needs whole terms from 1 to 30"
            return [_failure("consistency", "pattern_drawable", message, "show_pattern")]
        return []

    def computed_values(self, params: SequencePatternParams) -> dict[str, str]:
        result = _analyse(params)
        values = {
            "kind": result.kind,
            "nth_term": str(result.formula),
            "next_term": format_number(result.formula.subs(N, len(params.terms) + 1)),
            "term_10": format_number(result.formula.subs(N, 10)),
        }
        names = {1: "first_difference", 2: "second_difference", 3: "third_difference"}
        for order, row in enumerate(result.differences, start=1):
            if len(set(row)) == 1:
                values[names[order]] = format_number(row[0])
        if result.kind == "geometric":
            values["ratio"] = format_number(result.ratio)
        return values

    def build(self, params: SequencePatternParams, level):
        result = _analyse(params)
        terms = [exact(t) for t in params.terms]
        count = len(terms)
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        listing = r",\ ".join(latex_number(t) for t in terms) + r",\ \ldots"
        parts = {
            "sequence": text_line(listing, upper),
            "formula": text_line(rf"n\text{{th term}} = {result.latex()}", lower),
        }

        # The table: a header column of row names, then one column per term; differences sit
        # between the columns they come from.
        rows: list[tuple[str, str, list[tuple[str, float]], object]] = [
            ("row_n", "n", [(str(i + 1), i) for i in range(count)], style.TEXT_COLOUR),
            (
                "row_terms",
                r"\text{term}",
                [(latex_number(t), i) for i, t in enumerate(terms)],
                style.TEXT_COLOUR,
            ),
        ]
        if result.kind == "geometric":
            rows.append(
                (
                    "row_ratio",
                    r"\text{ratio}",
                    [(rf"\times {_bracketed(result.ratio)}", i + 0.5) for i in range(count - 1)],
                    style.HIGHLIGHT_COLOUR,
                )
            )
        else:
            for order, row in enumerate(result.differences, start=1):
                rows.append(
                    (
                        f"row_d{order}",
                        rf"\text{{{ORDINAL[order]} diff}}",
                        [(_signed(d), i + order / 2) for i, d in enumerate(row)],
                        style.RISE_COLOUR if order == result.order else style.RUN_COLOUR,
                    )
                )
        if result.kind in ("linear", "quadratic"):
            lead_tex, lead_values = result.lead_row()
            rows.append(
                (
                    "row_lead",
                    lead_tex,
                    [(latex_number(v), i) for i, v in enumerate(lead_values)],
                    style.CURVE_COLOUR,
                )
            )
            rest = [t - v for t, v in zip(terms, lead_values, strict=True)]
            rows.append(
                (
                    "row_rest",
                    rf"\text{{term}} - {lead_tex}",
                    [(latex_number(v), i) for i, v in enumerate(rest)],
                    style.SECANT_COLOUR,
                )
            )

        pattern_height = 1.7 if params.show_pattern else 0.0
        table_top = area.top - pattern_height - (0.2 if params.show_pattern else 0)
        row_gap = min(0.75, (table_top - area.bottom) / max(len(rows), 1))
        header_width = 2.2
        spacing = (area.width - header_width - 0.3) / count
        x0 = area.left + header_width + spacing / 2
        for r, (name, header, cells, colour) in enumerate(rows):
            y = table_top - (r + 0.5) * row_gap
            head = MathTex(header, font_size=26, color=colour)
            if head.width > header_width - 0.2:
                head.scale_to_fit_width(header_width - 0.2)
            head.move_to([area.left + header_width / 2, y, 0])
            group = VGroup(head)
            for tex, position in cells:
                size = 26 if name.startswith(("row_d", "row_ratio")) else 32
                cell = MathTex(tex, font_size=size, color=colour)
                if cell.width > spacing * 0.95:
                    cell.scale_to_fit_width(spacing * 0.95)
                cell.move_to([x0 + position * spacing, y, 0])
                group.add(cell)
            parts[name] = group

        if params.show_pattern:
            for i, t in enumerate(terms):
                dots = _dots(int(t))
                box = style.Box(
                    x0 + (i - 0.45) * spacing,
                    x0 + (i + 0.45) * spacing,
                    area.top - pattern_height,
                    area.top,
                )
                parts[f"pattern_{i + 1}"] = style.fit_inside(dots, box)
        return parts

    def stages(self, params: SequencePatternParams, level) -> list[Stage]:
        result = _analyse(params)
        count = len(params.terms)
        pattern = [f"pattern_{i + 1}" for i in range(count)] if params.show_pattern else []
        steps = [
            stage("sequence", "Show the sequence", 1.5, ["sequence"]),
            stage(
                "table",
                "Number the terms: n is each term's position",
                2.0,
                ["row_n", "row_terms", *pattern],
            ),
        ]
        if result.kind == "geometric":
            steps.append(
                stage(
                    "ratio",
                    "Each term is the one before multiplied by the same number: the ratio",
                    2.5,
                    ["row_ratio"],
                    emphasise=["row_ratio"],
                )
            )
        else:
            for order in range(1, result.order + 1):
                constant = order == result.order
                words = (
                    f"The {ORDINAL[order]} differences are all the same"
                    if constant
                    else f"Find the {ORDINAL[order]} differences between the terms"
                    if order == 1
                    else f"The {ORDINAL[order - 1]} differences change, so take their differences"
                )
                steps.append(
                    stage(
                        f"differences_{order}",
                        words,
                        2.5,
                        [f"row_d{order}"],
                        emphasise=[f"row_d{order}"] if constant else [],
                    )
                )
        if result.kind in ("linear", "quadratic"):
            lead_tex, _ = result.lead_row()
            steps.append(
                stage(
                    "lead",
                    "So the nth term starts with "
                    + (
                        "the difference times n"
                        if result.kind == "linear"
                        else "half the second difference times n squared"
                    ),
                    2.5,
                    ["row_lead"],
                )
            )
            steps.append(
                stage(
                    "rest",
                    "Take that away from each term to see what is left",
                    2.5,
                    ["row_rest"],
                    emphasise=["row_rest"],
                )
            )
        steps.append(
            stage("formula", "Write the nth term", 2.0, ["formula"], emphasise=["formula"])
        )

        def standard(s):
            out = [
                combine("sequence", "Show the sequence with each term's position", 2.5, s[0], s[1])
            ]
            middle = s[2:-1]
            pattern_steps = [x for x in middle if x.name.startswith(("differences", "ratio"))]
            out.append(
                combine(
                    "differences",
                    "Find the differences (or ratios) until they are constant",
                    3.0,
                    *pattern_steps,
                )
            )
            rest = [x for x in middle if x not in pattern_steps]
            if rest:
                out.append(
                    combine(
                        "compare",
                        "Compare the terms with the first part of the nth term",
                        3.0,
                        *rest,
                    )
                )
            out.append(s[-1])
            return out

        def concise(s):
            return [
                combine("sequence", "Show the sequence and its differences", 3.0, *s[:-1]),
                s[-1],
            ]

        return by_level(level, steps, standard, concise)


class _Result:
    def __init__(self, kind, order, differences, formula, ratio=None):
        self.kind, self.order, self.differences = kind, order, differences
        self.formula, self.ratio = formula, ratio

    def latex(self) -> str:
        if self.kind == "geometric":
            first = self.formula.subs(N, 1)
            lead = "" if first == 1 else ("-" if first == -1 else rf"{latex_number(first)} \times ")
            return rf"{lead}{_bracketed(self.ratio)}^{{n - 1}}"
        return tidy_latex(sp.expand(self.formula))

    def lead_row(self) -> tuple[str, list[sp.Expr]]:
        degree = 1 if self.kind == "linear" else 2
        coefficient = sp.Poly(self.formula, N).coeff_monomial(N**degree)
        lead = coefficient * N**degree
        count = len(self.differences[0]) + 1
        return sp.latex(lead), [lead.subs(N, i) for i in range(1, count + 1)]


def _analyse(params: SequencePatternParams) -> _Result | None:
    terms = [exact(t) for t in params.terms]
    differences = []
    row = terms
    for order in range(1, 4):
        row = [b - a for a, b in zip(row, row[1:], strict=False)]
        differences.append(row)
        if len(row) >= 2 and len(set(row)) == 1:
            if order == 1 and row[0] == 0:
                break
            if order == 3 and len(terms) < 5:
                return None
            formula = sp.expand(sp.interpolate(list(enumerate(terms[: order + 1], 1)), N))
            if all(formula.subs(N, i + 1) == t for i, t in enumerate(terms)):
                kind = {1: "linear", 2: "quadratic", 3: "cubic"}[order]
                return _Result(kind, order, differences, formula)
        if len(row) < 2:
            break
    if all(t != 0 for t in terms):
        ratios = {b / a for a, b in zip(terms, terms[1:], strict=False)}
        if len(ratios) == 1:
            ratio = ratios.pop()
            if ratio not in (0, 1):
                formula = terms[0] * ratio ** (N - 1)
                return _Result("geometric", 1, [], formula, ratio)
    return None


def _signed(value: sp.Expr) -> str:
    tex = latex_number(value)
    return tex if tex.startswith("-") else f"+{tex}"


def _bracketed(value: sp.Expr) -> str:
    tex = latex_number(value)
    return rf"\left({tex}\right)" if value < 0 or "frac" in tex else tex


def _dots(count: int) -> VGroup:
    """`count` dots in rows of a fixed width, so each term's pattern grows the same way."""
    width = 5
    dots = VGroup()
    for k in range(count):
        dot = Circle(radius=0.12, color=style.POINT_COLOUR, fill_opacity=1, stroke_width=0)
        dot.move_to([(k % width) * 0.32, -(k // width) * 0.32, 0])
        dots.add(dot)
    return dots


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
