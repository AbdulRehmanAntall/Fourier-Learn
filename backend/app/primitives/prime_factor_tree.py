"""PrimeFactorTree: a number split into prime factors with a factor tree, written in index form,
and the HCF and LCM of two numbers read from a Venn diagram of their primes (4024 1.1;
PRIMITIVES.md #2).

Each branch splits off the smallest prime, so the tree always ends in the same primes, circled.
For two numbers, the primes they share go in the overlap of the Venn diagram: the HCF is the
product of the overlap, the LCM the product of everything. SymPy factorises.
"""

from collections import Counter
from typing import Annotated

import numpy as np
import sympy as sp
from manim import Circle, Line, MathTex, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage

Whole = Annotated[int, Field(ge=4, le=10000)]


class PrimeFactorTreeParams(PrimitiveParams):
    number: Whole = Field(description="The number to factorise")
    other: Whole | None = Field(default=None, description="A second number, for the HCF and LCM")


class PrimeFactorTree(StagedPrimitive[PrimeFactorTreeParams]):
    primitive_id = "PrimeFactorTree"
    version = "1"
    topic = "Number"
    params_model = PrimeFactorTreeParams
    layout = LayoutContract(
        region=style.GRAPH_REGION, allowed_overlaps=[("venn*", "venn*"), ("tree_*", "tree_*")]
    )

    def default_params(self) -> PrimeFactorTreeParams:
        return PrimeFactorTreeParams(number=360, other=84)

    def validate(self, params: PrimeFactorTreeParams) -> list[PredicateFailure]:
        for name in ("number", "other"):
            value = getattr(params, name)
            if value is not None and sp.isprime(value):
                return [
                    PredicateFailure(
                        kind="consistency",
                        predicate="composite",
                        message=f"{value} is prime: it has no factor tree",
                        parameters=[name],
                    )
                ]
        return []

    def computed_values(self, params: PrimeFactorTreeParams) -> dict[str, str]:
        values = {"index_form": _index_text(params.number)}
        if params.other is not None:
            values["other_index_form"] = _index_text(params.other)
            values["hcf"] = str(sp.gcd(params.number, params.other))
            values["lcm"] = str(sp.lcm(params.number, params.other))
        return values

    def build(self, params: PrimeFactorTreeParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        numbers = [params.number] + ([params.other] if params.other is not None else [])
        columns = split_columns(area, [1] * len(numbers), gap=0.4)
        parts = {}
        for key, n, box in zip(("tree_n", "tree_m"), numbers, columns, strict=False):
            parts[key] = _tree(n, box)
        parts["index_n"] = text_line(_index_latex(params.number), upper)
        if params.other is not None:
            parts["index_m"] = text_line(_index_latex(params.other), lower)
            venn, labels = _venn(params.number, params.other, area)
            parts["venn"] = venn
            parts["venn_numbers"] = labels
            hcf, lcm = sp.gcd(params.number, params.other), sp.lcm(params.number, params.other)
            common = Counter(sp.factorint(params.number)) & Counter(sp.factorint(params.other))
            every = Counter(sp.factorint(params.number)) | Counter(sp.factorint(params.other))
            parts["hcf"] = text_line(
                rf"\text{{HCF}} = {_product(common)} = {hcf}", upper, colour=style.RISE_COLOUR
            )
            parts["lcm"] = text_line(
                rf"\text{{LCM}} = {_product(every)} = {lcm}", lower, colour=style.RUN_COLOUR
            )
        return parts

    def stages(self, params: PrimeFactorTreeParams, level) -> list[Stage]:
        n = params.number
        steps = [
            stage(
                "tree_n",
                f"Split {n} into a prime and what is left, again and again",
                3.5,
                ["tree_n"],
            ),
            stage(
                "index_n",
                "Multiply the circled primes, written with powers",
                2.5,
                ["index_n"],
                emphasise=["index_n"],
            ),
        ]
        if params.other is not None:
            m = params.other
            steps += [
                stage("tree_m", f"Do the same for {m}", 3.0, ["tree_m"]),
                stage("index_m", f"{m} in prime factors", 2.0, ["index_m"]),
                stage(
                    "venn",
                    "Put the primes in a Venn diagram: shared primes in the overlap",
                    3.5,
                    ["venn", "venn_numbers"],
                    hide=["tree_n", "tree_m"],
                ),
                stage(
                    "hcf",
                    "The HCF multiplies the shared primes",
                    2.5,
                    morph=[("index_n", "hcf")],
                    emphasise=["hcf"],
                ),
                stage(
                    "lcm",
                    "The LCM multiplies every prime in the diagram",
                    2.5,
                    morph=[("index_m", "lcm")],
                    emphasise=["lcm"],
                ),
            ]

        def standard(s):
            if len(s) == 2:
                return s
            return [
                combine("trees", "Factor trees for both numbers", 3.5, s[0], s[2]),
                combine("index", "Both in prime factors", 2.5, s[1], s[3]),
                s[4],
                combine("results", "The HCF and the LCM", 3.0, s[5], s[6]),
            ]

        def concise(s):
            if len(s) == 2:
                return [combine("tree", "The factor tree and the prime factors", 3.5, *s)]
            return [
                combine("trees", "Both numbers in prime factors", 3.5, *s[:4]),
                combine("results", "The HCF and LCM from the Venn diagram", 4.0, *s[4:]),
            ]

        return by_level(level, steps, standard, concise)


def _index_latex(n: int) -> str:
    factors = sp.factorint(n)
    terms = [f"{p}^{{{k}}}" if k > 1 else str(p) for p, k in sorted(factors.items())]
    return rf"{n} = " + r" \times ".join(terms)


def _index_text(n: int) -> str:
    factors = sp.factorint(n)
    return " x ".join(f"{p}^{k}" if k > 1 else str(p) for p, k in sorted(factors.items()))


def _product(counter: Counter) -> str:
    terms = [str(p) for p in sorted(counter.elements())]
    return r" \times ".join(terms) if terms else "1"


def _tree(n: int, box: style.Box) -> VGroup:
    """The factor tree: the composite part goes down to the right, each prime branches off to
    the left and is circled."""
    rows = []
    value = n
    while not sp.isprime(value):
        prime = min(sp.factorint(value))
        rows.append((value, prime))
        value //= prime
    depth = len(rows) + 1
    step_y = min(0.85, (box.height - 0.5) / depth)
    step_x = min(0.6, (box.width - 1.0) / (depth + 1))
    start = np.array([box.left + 0.6 + step_x, box.top - 0.35, 0.0])
    group = VGroup()
    point = start
    group.add(MathTex(str(n), font_size=34).move_to(point))
    for i, (composite, prime) in enumerate(rows):
        below = point + [step_x, -step_y, 0]
        left = point + [-step_x * 0.9, -step_y, 0]
        group.add(Line(point + [0.1, -0.2, 0], below + [-0.05, 0.2, 0], stroke_width=2))
        group.add(Line(point + [-0.1, -0.2, 0], left + [0.05, 0.2, 0], stroke_width=2))
        leaf = MathTex(str(prime), font_size=32, color=style.POINT_COLOUR).move_to(left)
        group.add(leaf, Circle(radius=0.24, color=style.POINT_COLOUR, stroke_width=2).move_to(left))
        rest = composite // prime
        last = i == len(rows) - 1
        node = MathTex(
            str(rest),
            font_size=32 if last else 34,
            color=style.POINT_COLOUR if last else style.TEXT_COLOUR,
        ).move_to(below)
        group.add(node)
        if last:
            group.add(Circle(radius=0.24, color=style.POINT_COLOUR, stroke_width=2).move_to(below))
        point = below
    if group.height > box.height or group.width > box.width:
        style.fit_inside(group, box)
    return group


def _venn(n: int, m: int, area: style.Box) -> tuple[VGroup, VGroup]:
    a, b = Counter(sp.factorint(n)), Counter(sp.factorint(m))
    common = a & b
    only_a, only_b = a - common, b - common
    radius = min(area.height * 0.4, area.width * 0.28)
    centre = area.center
    left = Circle(radius=radius, color=style.CURVE_COLOUR).move_to(centre + [-radius * 0.55, 0, 0])
    right = Circle(radius=radius, color=style.RUN_COLOUR).move_to(centre + [radius * 0.55, 0, 0])
    names = VGroup(
        MathTex(str(n), font_size=34, color=style.CURVE_COLOUR).next_to(left, [0, 1, 0], 0.1),
        MathTex(str(m), font_size=34, color=style.RUN_COLOUR).next_to(right, [0, 1, 0], 0.1),
    )
    numbers = VGroup()
    for counter, x in ((only_a, -radius * 1.0), (common, 0.0), (only_b, radius * 1.0)):
        items = sorted(counter.elements())
        rows = (len(items) + 1) // 2
        for k, prime in enumerate(items):
            row, col = divmod(k, 2)
            across = (col - 0.5) * 0.45 if len(items) > 1 else 0.0
            up = ((rows - 1) / 2 - row) * 0.5
            numbers.add(MathTex(str(prime), font_size=34).move_to(centre + [x + across, up, 0]))
    return VGroup(left, right, names), numbers
