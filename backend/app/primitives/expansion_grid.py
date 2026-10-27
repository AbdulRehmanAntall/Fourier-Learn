"""ExpansionGrid: the area (grid) model for multiplying out brackets and for factorising
(4024 2.2, 2.5.5; PRIMITIVES.md #14).

Each term of the first bracket labels a row, each term of the second a column, and each cell
holds their product. Cells holding like terms share a colour, so collecting them is visible.
In "factorise" mode the expanded expression is given first and the brackets are read off the
grid's edges, so factorising is seen as expanding in reverse. Every product is computed by
SymPy; the grid is a model of the multiplication, so its cells are not drawn to scale.
"""

from typing import Annotated, Literal

import sympy as sp
from manim import BLUE_C, GREEN_C, ORANGE, PURPLE_B, RED_C, TEAL_C, MathTex, Rectangle
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, Level, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import text_line
from app.primitives.staged import Stage, StagedPrimitive, combine, stage
from app.primitives.symbolic import ExpressionError, parse_expression, tidy_latex

Factor = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
LIKE_COLOURS = [BLUE_C, GREEN_C, ORANGE, PURPLE_B, TEAL_C, RED_C]


class ExpansionGridParams(PrimitiveParams):
    factors: tuple[Factor, Factor] = Field(
        description='The two brackets, e.g. ["2*x + 3", "x - 4"]; each has 1 to 3 terms'
    )
    mode: Literal["expand", "factorise"] = Field(
        default="expand",
        description="expand: multiply out; factorise: start from the expanded expression and "
        "read the brackets off the grid",
    )


class ExpansionGrid(StagedPrimitive[ExpansionGridParams]):
    primitive_id = "ExpansionGrid"
    version = "1"
    topic = "Algebra and graphs"
    params_model = ExpansionGridParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("cell_*", "cell_*"), ("cell_*", "product_*")],
    )

    def default_params(self) -> ExpansionGridParams:
        return ExpansionGridParams(factors=("x + 2", "x + 3"))

    def validate(self, params: ExpansionGridParams) -> list[PredicateFailure]:
        failures = []
        for i, text in enumerate(params.factors):
            try:
                expr = parse_expression(text)
            except ExpressionError as error:
                failures.append(_failure("parsing", "factor_parses", str(error), f"factors[{i}]"))
                continue
            if not expr.is_polynomial(*expr.free_symbols) or expr.is_number:
                message = f"bracket {i + 1} must be a polynomial with a letter in it"
                failures.append(_failure("consistency", "polynomial", message, f"factors[{i}]"))
            elif len(_terms(expr)) > 3:
                message = f"bracket {i + 1} has more than 3 terms"
                failures.append(
                    _failure("consistency", "at_most_3_terms", message, f"factors[{i}]")
                )
        if failures:
            return failures
        product = sp.expand(_factor(params, 0) * _factor(params, 1))
        if product == 0:
            return [_failure("consistency", "nonzero", "the product is 0", "factors")]
        return []

    def computed_values(self, params: ExpansionGridParams) -> dict[str, str]:
        rows, columns = _terms(_factor(params, 0)), _terms(_factor(params, 1))
        values = {
            f"cell_{r + 1}_{c + 1}": str(row * column)
            for r, row in enumerate(rows)
            for c, column in enumerate(columns)
        }
        values["expanded"] = str(_expanded(params))
        values["factorised"] = f"({params.factors[0]})({params.factors[1]})"
        return values

    def build(self, params: ExpansionGridParams, level):
        first, second = _factor(params, 0), _factor(params, 1)
        rows, columns = _terms(first), _terms(second)
        expanded = _expanded(params)
        colours = _like_colours(rows, columns)

        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        brackets = rf"\left({tidy_latex(first)}\right)\left({tidy_latex(second)}\right)"
        parts = {}
        if params.mode == "expand":
            parts["question"] = text_line(brackets, upper)
            parts["answer"] = text_line(rf"= {tidy_latex(expanded)}", lower)
        else:
            parts["question"] = text_line(tidy_latex(expanded), upper)
            parts["answer"] = text_line(rf"= {brackets}", lower)

        # The grid: one row per term of the first bracket, one column per term of the second.
        edge = 1.0
        cell_w = min((area.width - edge - 0.4) / len(columns), 2.6)
        cell_h = min((area.height - edge - 0.4) / len(rows), 1.7)
        left = area.center[0] - (edge + cell_w * len(columns)) / 2 + edge
        top = area.center[1] + (edge + cell_h * len(rows)) / 2 - edge
        for r, row in enumerate(rows):
            for c, column in enumerate(columns):
                cell = Rectangle(
                    width=cell_w,
                    height=cell_h,
                    stroke_color=style.TEXT_COLOUR,
                    stroke_width=3,
                    fill_color=colours[(r, c)],
                    fill_opacity=0.25,
                )
                cell.move_to([left + (c + 0.5) * cell_w, top - (r + 0.5) * cell_h, 0])
                parts[f"cell_{r + 1}_{c + 1}"] = cell
                product = MathTex(sp.latex(row * column), font_size=style.FONT_SIZE)
                product.set_color(colours[(r, c)])
                style.fit_inside(
                    product,
                    style.Box(
                        cell.get_left()[0] + 0.1,
                        cell.get_right()[0] - 0.1,
                        cell.get_bottom()[1] + 0.1,
                        cell.get_top()[1] - 0.1,
                    ),
                )
                parts[f"product_{r + 1}_{c + 1}"] = product
            row_label = MathTex(_signed(row, r == 0), font_size=style.FONT_SIZE)
            if row_label.width > edge - 0.15:
                row_label.scale_to_fit_width(edge - 0.15)
            parts[f"row_{r + 1}"] = row_label.move_to(
                [left - edge / 2, top - (r + 0.5) * cell_h, 0]
            )
        for c, column in enumerate(columns):
            label = MathTex(_signed(column, c == 0), font_size=style.FONT_SIZE)
            label.move_to([left + (c + 0.5) * cell_w, top + edge / 2, 0])
            if label.width > cell_w - 0.1:
                label.scale_to_fit_width(cell_w - 0.1)
            parts[f"column_{c + 1}"] = label
        parts["times"] = MathTex(r"\times", font_size=style.FONT_SIZE).move_to(
            [left - edge / 2, top + edge / 2, 0]
        )
        return parts

    def stages(self, params: ExpansionGridParams, level) -> list[Stage]:
        rows, columns = _terms(_factor(params, 0)), _terms(_factor(params, 1))
        n_rows, n_cols = len(rows), len(columns)
        cells = [f"cell_{r}_{c}" for r in range(1, n_rows + 1) for c in range(1, n_cols + 1)]
        edges = [f"row_{r}" for r in range(1, n_rows + 1)]
        edges += [f"column_{c}" for c in range(1, n_cols + 1)]
        like = [
            [f"product_{r + 1}_{c + 1}" for r, c in group]
            for group in _like_groups(rows, columns)
            if len(group) > 1
        ]
        question = stage("question", "Show the expression", 2.0, ["question"])
        collect_what = (
            "Collect the like terms, which share a colour"
            if like
            else "Add the products: there are no like terms to collect"
        )
        answer = stage(
            "answer", collect_what, 2.5, ["answer"], emphasise=[n for group in like for n in group]
        )

        if params.mode == "expand":
            grid = stage(
                "grid",
                "Draw a grid: a row for each term of the first bracket and a "
                "column for each term of the second",
                2.5,
                ["times", *cells, *edges],
            )
            row_stages = [
                stage(
                    f"row_{r}_products",
                    f"Multiply {sp.latex(rows[r - 1])} by each term along the top",
                    2.0,
                    [f"product_{r}_{c}" for c in range(1, n_cols + 1)],
                )
                for r in range(1, n_rows + 1)
            ]
            if level is Level.SUPPORTED:
                return [question, grid, *row_stages, answer]
            products = combine(
                "products",
                "Fill each cell with the product of its row and column",
                2.5,
                *row_stages,
            )
            if level is Level.STANDARD:
                return [question, grid, products, answer]
            return [
                combine(
                    "grid",
                    "Draw the grid and fill each cell with a product",
                    2.5,
                    question,
                    grid,
                    products,
                ),
                answer,
            ]

        # Factorise: the corner cells come from the expression, the edges from the corners.
        corner_first = "product_1_1"
        corner_last = f"product_{n_rows}_{n_cols}"
        corners = [corner_first] if corner_first == corner_last else [corner_first, corner_last]
        others = [
            f"product_{r}_{c}"
            for r in range(1, n_rows + 1)
            for c in range(1, n_cols + 1)
            if f"product_{r}_{c}" not in corners
        ]
        grid = stage(
            "grid",
            "Draw an empty grid and put the first and last terms in its corners",
            2.5,
            ["times", *cells, *corners],
        )
        sides = stage(
            "edges",
            "Find the terms on the edges that multiply to give the corners",
            3.0,
            edges,
            emphasise=edges,
        )
        middle = stage(
            "check",
            "Check that the other cells give the middle terms",
            2.5,
            others,
            emphasise=[n for group in like for n in group],
        )
        answer = stage("answer", "Read the brackets off the edges", 2.0, ["answer"])
        if level is Level.SUPPORTED:
            return [question, grid, sides, middle, answer]
        if level is Level.STANDARD:
            return [
                question,
                grid,
                combine("edges", "Find the edges and check the middle cells", 3.0, sides, middle),
                answer,
            ]
        return [
            combine(
                "grid", "Show the expression in a grid with its corner terms", 2.5, question, grid
            ),
            combine(
                "answer", "Read the brackets off the edges and check", 3.0, sides, middle, answer
            ),
        ]


def _factor(params: ExpansionGridParams, i: int) -> sp.Expr:
    return parse_expression(params.factors[i])


def _expanded(params: ExpansionGridParams) -> sp.Expr:
    return sp.expand(_factor(params, 0) * _factor(params, 1))


def _terms(expr: sp.Expr) -> list[sp.Expr]:
    expr = sp.expand(expr)
    return list(expr.as_ordered_terms()) if isinstance(expr, sp.Add) else [expr]


def _monomial(term: sp.Expr) -> sp.Expr:
    _, rest = term.as_coeff_Mul()
    return rest


def _like_groups(rows, columns) -> list[list[tuple[int, int]]]:
    groups: dict[sp.Expr, list[tuple[int, int]]] = {}
    for r, row in enumerate(rows):
        for c, column in enumerate(columns):
            groups.setdefault(_monomial(sp.expand(row * column)), []).append((r, c))
    return list(groups.values())


def _like_colours(rows, columns) -> dict[tuple[int, int], object]:
    colours = {}
    for i, group in enumerate(_like_groups(rows, columns)):
        for cell in group:
            colours[cell] = LIKE_COLOURS[i % len(LIKE_COLOURS)]
    return colours


def _signed(term: sp.Expr, first: bool) -> str:
    """A term as an edge label: "+3" or "-4", the first one without a plus sign."""
    tex = sp.latex(term)
    return tex if first or tex.startswith("-") else f"+{tex}"


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
