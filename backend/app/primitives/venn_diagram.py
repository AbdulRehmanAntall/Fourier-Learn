"""VennDiagram: two or three sets in a universal set, their elements (or how many are in each
region), and the region named by set notation shaded and counted (4024 1.2, 8.3;
PRIMITIVES.md #3).

Set notation: A ∩ B (also "A & B"), A ∪ B (also "A | B"), A' for the complement, and brackets.
The shaded region is built from the circles exactly (boolean operations on the shapes), and its
size n(...) is counted from the elements or the region counts. The same diagram serves
probability: P = n(region) / n(ξ).
"""

import itertools
import re
from typing import Annotated, Literal

import numpy as np
from manim import (
    Circle,
    Difference,
    Intersection,
    MathTex,
    Rectangle,
    VGroup,
)
from pydantic import Field, StringConstraints, model_validator

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage

Element = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8)]
NAMES = ("A", "B", "C")
COLOURS = (style.CURVE_COLOUR, style.RUN_COLOUR, style.RISE_COLOUR)


class VennDiagramParams(PrimitiveParams):
    sets: list[list[Element]] | None = Field(
        default=None,
        min_length=2,
        max_length=3,
        description='The elements of A, B (and C), e.g. [["1", "2", "3"], ["2", "4"]]',
    )
    universal: list[Element] = Field(
        default=[], max_length=24, description="Elements of ξ outside every set (with `sets`)"
    )
    counts: dict[str, Annotated[int, Field(ge=0, le=999)]] | None = Field(
        default=None,
        description="Instead of elements, how many are in each region: keys are the sets the "
        'region is inside, e.g. {"A": 5, "AB": 3, "B": 7, "": 2} ("" is outside every set)',
    )
    set_count: Literal[2, 3] = Field(default=2, description="2 or 3 sets (with `counts`)")
    shade: str | None = Field(
        default=None, max_length=40, description='The region to shade, e.g. "A ∩ B\'"'
    )

    @model_validator(mode="after")
    def _one_kind(self):
        if (self.sets is None) == (self.counts is None):
            raise ValueError("give either sets (with elements) or counts")
        return self


class VennDiagram(StagedPrimitive[VennDiagramParams]):
    primitive_id = "VennDiagram"
    version = "1"
    topic = "Number"
    params_model = VennDiagramParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("universe", "*"), ("circles", "*"), ("shading", "*"), ("contents", "*")],
    )

    def default_params(self) -> VennDiagramParams:
        return VennDiagramParams(
            sets=[["1", "2", "3", "4", "6", "12"], ["2", "4", "6", "8", "10"]],
            universal=["5", "7", "9", "11"],
            shade="A ∩ B",
        )

    def validate(self, params: VennDiagramParams) -> list[PredicateFailure]:
        venn = _Venn(params)
        if params.sets is not None:
            total = sum(len(v) for v in venn.regions.values())
            if total > 24:
                return [
                    _failure("consistency", "few_elements", "more than 24 elements to show", "sets")
                ]
            if any(len(v) > 8 for v in venn.regions.values()):
                return [
                    _failure(
                        "consistency",
                        "region_fits",
                        "a region has more than 8 elements; use counts",
                        "sets",
                    )
                ]
            clash = set(params.universal) & set().union(*map(set, params.sets))
            if clash:
                return [
                    _failure(
                        "consistency",
                        "universal_outside",
                        f"{sorted(clash)} are in a set, not outside every set",
                        "universal",
                    )
                ]
        else:
            bad = [k for k in params.counts if not _valid_key(k, params.set_count)]
            if bad:
                return [
                    _failure(
                        "parsing",
                        "region_keys",
                        f'unknown regions {bad}; use keys such as A, AB, ABC or ""',
                        "counts",
                    )
                ]
        if params.shade is not None:
            try:
                _parse(params.shade, venn.count)
            except _Bad as bad:
                return [_failure("parsing", "shade_parses", str(bad), "shade")]
        return []

    def computed_values(self, params: VennDiagramParams) -> dict[str, str]:
        venn = _Venn(params)
        values = {
            f"n_{name}": str(venn.size(lambda r, i=i: r[i]))
            for i, name in enumerate(NAMES[: venn.count])
        }
        values["n_universal"] = str(venn.size(lambda r: True))
        if params.shade is not None:
            rule = _parse(params.shade, venn.count)
            values["n_shaded"] = str(venn.size(rule))
            values["shaded_elements"] = ", ".join(venn.elements(rule))
        return values

    def build(self, params: VennDiagramParams, level):
        venn = _Venn(params)
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        box = area.shrink(0.2)
        universe = Rectangle(
            width=box.width, height=box.height, color=style.TEXT_COLOUR, stroke_width=3
        ).move_to(box.center)
        xi = MathTex(r"\xi", font_size=style.FONT_SIZE).move_to([box.left + 0.3, box.top - 0.3, 0])
        radius = min(box.height * (0.36 if venn.count == 2 else 0.3), box.width * 0.24)
        circles = _circles(venn.count, radius, box.center)
        names = VGroup()
        for i, circle in enumerate(circles):
            direction = circle.get_center() - box.center
            direction = direction / (np.linalg.norm(direction) or 1)
            names.add(
                MathTex(NAMES[i], font_size=style.FONT_SIZE, color=COLOURS[i]).move_to(
                    circle.get_center() + direction * radius * 1.12 + [0, radius * 0.15, 0]
                )
            )
        parts = {
            "universe": VGroup(universe, xi),
            "circles": VGroup(*circles, names),
            "contents": _contents(venn, circles, universe, box),
        }
        if params.shade is not None:
            rule = _parse(params.shade, venn.count)
            parts["shading"] = _shading(venn.count, rule, circles, universe)
            parts["notation"] = text_line(_notation_latex(params.shade), upper)
            parts["count"] = text_line(
                rf"n\left({_notation_latex(params.shade)}\right) = {venn.size(rule)}", lower
            )
        return parts

    def stages(self, params: VennDiagramParams, level) -> list[Stage]:
        what = "elements" if params.sets is not None else "the number in each region"
        steps = [
            stage(
                "diagram",
                "The universal set is the rectangle; each set is a circle",
                2.5,
                ["universe", "circles"],
            ),
            stage(
                "contents",
                f"Write {what} in the right region: the overlap holds what is in both",
                3.5,
                ["contents"],
            ),
        ]
        if params.shade is not None:
            steps += [
                stage("notation", "Read the set notation", 2.0, ["notation"]),
                stage(
                    "shade",
                    "Shade the region it describes",
                    3.0,
                    ["shading"],
                    emphasise=["shading"],
                ),
                stage(
                    "count",
                    "Count what is in the shaded region",
                    2.5,
                    ["count"],
                    emphasise=["count"],
                ),
            ]

        def standard(s):
            if len(s) == 2:
                return s
            return [s[0], s[1], combine("shade", "Shade the region and count it", 3.5, *s[2:])]

        def concise(s):
            if len(s) == 2:
                return [combine("diagram", "The Venn diagram", 3.5, *s)]
            return [
                combine("diagram", "The Venn diagram", 3.5, s[0], s[1]),
                combine("shade", "The shaded region and its size", 3.5, *s[2:]),
            ]

        return by_level(level, steps, standard, concise)


class _Venn:
    """Each region, keyed by which sets it is inside, with its elements or its count."""

    def __init__(self, params: VennDiagramParams):
        self.by_elements = params.sets is not None
        if params.sets is not None:
            self.count = len(params.sets)
            members = [set(s) for s in params.sets]
            everything = list(dict.fromkeys([*itertools.chain(*params.sets), *params.universal]))
            self.regions = {key: [] for key in itertools.product((False, True), repeat=self.count)}
            for element in everything:
                key = tuple(element in m for m in members)
                self.regions[key].append(element)
            self.counts = {k: len(v) for k, v in self.regions.items()}
        else:
            self.count = params.set_count
            self.regions = {key: [] for key in itertools.product((False, True), repeat=self.count)}
            self.counts = {key: 0 for key in self.regions}
            for text, n in params.counts.items():
                key = tuple(NAMES[i] in text for i in range(self.count))
                self.counts[key] = n

    def size(self, rule) -> int:
        return sum(n for key, n in self.counts.items() if rule(key))

    def elements(self, rule) -> list[str]:
        return [e for key, items in self.regions.items() if rule(key) for e in items]


class _Bad(ValueError):
    pass


_TOKEN = re.compile(r"\s*(∩|∪|&|\||'|′|\(|\)|[ABC]|ξ|U)")


def _parse(text: str, count: int):
    """A set expression as a rule: region key -> is the region in the set."""
    tokens, position = [], 0
    while position < len(text.strip()):
        match = _TOKEN.match(text.strip(), position)
        if not match:
            raise _Bad(f"cannot read {text!r} at {text.strip()[position:]!r}")
        tokens.append(match.group(1))
        position = match.end()
    index = 0

    def peek():
        return tokens[index] if index < len(tokens) else None

    def take():
        nonlocal index
        index += 1
        return tokens[index - 1]

    def union():
        rule = intersection()
        while peek() in ("∪", "|"):
            take()
            right = intersection()
            rule = (lambda a, b: lambda r: a(r) or b(r))(rule, right)
        return rule

    def intersection():
        rule = unary()
        while peek() in ("∩", "&"):
            take()
            right = unary()
            rule = (lambda a, b: lambda r: a(r) and b(r))(rule, right)
        return rule

    def unary():
        rule = atom()
        while peek() in ("'", "′"):
            take()
            rule = (lambda a: lambda r: not a(r))(rule)
        return rule

    def atom():
        token = take() if peek() is not None else None
        if token == "(":
            rule = union()
            if peek() != ")":
                raise _Bad(f"a bracket is not closed in {text!r}")
            take()
            return rule
        if token in ("ξ", "U"):
            return lambda r: True
        if token in NAMES[:count]:
            i = NAMES.index(token)
            return lambda r: r[i]
        raise _Bad(f"unexpected {token!r} in {text!r}; use the sets {', '.join(NAMES[:count])}")

    rule = union()
    if index != len(tokens):
        raise _Bad(f"unexpected {tokens[index]!r} in {text!r}")
    return rule


def _valid_key(key: str, count: int) -> bool:
    return all(c in NAMES[:count] for c in key) and len(set(key)) == len(key)


def _notation_latex(text: str) -> str:
    tex = text.replace("&", r"\cap").replace("|", r"\cup").replace("∩", r"\cap ")
    tex = tex.replace("∪", r"\cup ").replace("′", "'").replace("ξ", r"\xi")
    return tex


def _circles(count: int, radius: float, centre: np.ndarray) -> list[Circle]:
    d = radius * 0.6
    if count == 2:
        offsets = [[-d, 0, 0], [d, 0, 0]]
    else:
        offsets = [[-d, d * 0.55, 0], [d, d * 0.55, 0], [0, -d * 0.85, 0]]
    return [
        Circle(radius=radius, color=COLOURS[i], stroke_width=4).move_to(centre + offsets[i])
        for i in range(count)
    ]


def _inside(point, circles) -> tuple:
    return tuple(np.linalg.norm(point - c.get_center()) < c.width / 2 for c in circles)


def _contents(venn: _Venn, circles, universe, box) -> VGroup:
    """Each region's elements (or its count) near the middle of the region."""
    xs = np.linspace(box.left + 0.25, box.right - 0.25, 90)
    ys = np.linspace(box.bottom + 0.25, box.top - 0.25, 60)
    samples: dict[tuple, list[np.ndarray]] = {key: [] for key in venn.regions}
    margin = 0.18
    for x in xs:
        for y in ys:
            point = np.array([x, y, 0.0])
            key = _inside(point, circles)
            clear = all(
                abs(np.linalg.norm(point - c.get_center()) - c.width / 2) > margin for c in circles
            )
            if clear:
                samples[key].append(point)
    group = VGroup()
    for key, points in samples.items():
        if not points:
            continue
        cloud = np.array(points)
        middle = cloud.mean(axis=0)
        if not any(key):
            middle = np.array([box.right - 0.6, box.bottom + 0.45, 0.0])
        texts = venn.regions[key] if venn.by_elements else [str(venn.counts[key])]
        if not texts:
            continue
        cols = 3 if len(texts) > 4 else 2
        rows = (len(texts) + cols - 1) // cols
        for k, text in enumerate(texts):
            row, col = divmod(k, cols)
            across = (col - (min(cols, len(texts)) - 1) / 2) * 0.42
            up = ((rows - 1) / 2 - row) * 0.38
            group.add(MathTex(text, font_size=30).move_to(middle + [across, up, 0]))
    return group


def _shading(count: int, rule, circles, universe) -> VGroup:
    """The union of the regions the rule picks, built from the circles' shapes."""
    pieces = VGroup()
    for key in itertools.product((False, True), repeat=count):
        if not rule(key):
            continue
        inside = [circles[i] for i in range(count) if key[i]]
        outside = [circles[i] for i in range(count) if not key[i]]
        shape = universe.copy() if not inside else inside[0].copy()
        for other in inside[1:]:
            shape = Intersection(shape, other)
        for other in outside:
            shape = Difference(shape, other)
        if len(shape.points) == 0:
            continue
        shape.set_fill(style.HIGHLIGHT_COLOUR, opacity=0.35).set_stroke(width=0)
        pieces.add(shape)
    return pieces


def _failure(kind, predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(kind=kind, predicate=predicate, message=message, parameters=[parameter])
