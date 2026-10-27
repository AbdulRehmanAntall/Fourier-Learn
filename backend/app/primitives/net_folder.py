"""NetFolder: the net of a solid laid flat, face by face, with its faces, edges and vertices,
and the surface area as the total area of the net (4024 4.1, 4.2.3, with 5.4; PRIMITIVES.md
#33).

Solids: cube, cuboid, triangular prism (right-angled cross-section), square-based pyramid and
cylinder, whose curved surface unrolls into a rectangle 2πr wide. Faces that match are the same
colour, so the area is counted as pairs (or fours). Answers are exact in π where they can be.
"""

import math
from typing import Annotated, Literal

import sympy as sp
from manim import Circle, Polygon, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import Diagram, label, split_columns, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf, latex_with_pi

Length = Annotated[float, Field(gt=0, le=1000)]
COLOURS = [style.CURVE_COLOUR, style.RUN_COLOUR, style.RISE_COLOUR, style.SECANT_COLOUR]
NEEDS = {
    "cube": ("length",),
    "cuboid": ("length", "width", "height"),
    "prism": ("length", "width", "height"),
    "pyramid": ("width", "height"),
    "cylinder": ("radius", "height"),
}
COUNTS = {"cube": (6, 12, 8), "cuboid": (6, 12, 8), "prism": (5, 9, 6), "pyramid": (5, 8, 5)}


class NetFolderParams(PrimitiveParams):
    solid: Literal["cube", "cuboid", "prism", "pyramid", "cylinder"]
    length: Length | None = Field(default=None, description="Cube side; cuboid or prism length")
    width: Length | None = Field(default=None, description="Width; the base side of a pyramid")
    height: Length | None = Field(
        default=None, description="Height; the slant height of a pyramid's triangular face"
    )
    radius: Length | None = None
    unit: Literal["cm", "m", "mm", ""] = "cm"


class NetFolder(StagedPrimitive[NetFolderParams]):
    primitive_id = "NetFolder"
    version = "1"
    topic = "Geometry"
    params_model = NetFolderParams
    layout = LayoutContract(region=style.GRAPH_REGION, allowed_overlaps=[("faces_*", "*")])

    def default_params(self) -> NetFolderParams:
        return NetFolderParams(solid="cuboid", length=5, width=3, height=2)

    def validate(self, params: NetFolderParams) -> list[PredicateFailure]:
        missing = [n for n in NEEDS[params.solid] if getattr(params, n) is None]
        if missing:
            return [
                PredicateFailure(
                    kind="consistency",
                    predicate="needs_dimensions",
                    message=f"a {params.solid} needs {', '.join(missing)}",
                    parameters=missing,
                )
            ]
        return []

    def computed_values(self, params: NetFolderParams) -> dict[str, str]:
        return {"surface_area": format_sf(_total(params))}

    def build(self, params: NetFolderParams, level):
        title, area = style.graph_boxes(self.layout.region)
        upper, lower = style.title_lines(title)
        figure_box, working_box = split_columns(area, [1.25, 1], gap=0.3)
        groups = _net(params)
        points = [pt for _, faces in groups for face in faces for pt in _outline(face)]
        diagram = Diagram(points, figure_box, margin=0.25)
        parts = {}
        unit = rf"\text{{ {params.unit}}}" if params.unit else ""
        for i, (tex, faces) in enumerate(groups):
            colour = COLOURS[i % len(COLOURS)]
            group = VGroup()
            for face in faces:
                if face[0] == "circle":
                    _, (cx, cy), r = face
                    shape = Circle(
                        radius=diagram.length(r),
                        color=style.TEXT_COLOUR,
                        stroke_width=3,
                        fill_color=colour,
                        fill_opacity=0.5,
                    ).move_to(diagram.p(cx, cy))
                else:
                    shape = Polygon(
                        *(diagram.p(*pt) for pt in face),
                        color=style.TEXT_COLOUR,
                        stroke_width=3,
                        fill_color=colour,
                        fill_opacity=0.5,
                    )
                group.add(shape)
                text = label(tex, size=22)
                # a triangle narrows towards its tip, so its label must be smaller to fit
                room = 0.5 if face[0] != "circle" and len(face) == 3 else 0.9
                if text.width < shape.width * room and text.height < shape.height * 0.45:
                    group.add(
                        text.move_to(
                            shape.get_center_of_mass()
                            if face[0] != "circle"
                            else shape.get_center()
                        )
                    )
            parts[f"faces_{i + 1}"] = group
        rows = _working(params, groups, unit)
        mobjects = [label(t, size=30) for t in rows]
        stack = VGroup(*mobjects).arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.28)
        for mob in mobjects:
            if mob.width > working_box.width:
                mob.scale_to_fit_width(working_box.width)
        style.fit_inside(stack.arrange([0, -1, 0], aligned_edge=[-1, 0, 0], buff=0.28), working_box)
        for i, mob in enumerate(mobjects, start=1):
            parts[f"row_{i}"] = mob
        name = {
            "cube": "cube",
            "cuboid": "cuboid",
            "prism": "triangular prism",
            "pyramid": "square-based pyramid",
            "cylinder": "cylinder",
        }[params.solid]
        parts["question"] = text_line(rf"\text{{The net of a {name}}}", upper)
        square = "^2" if unit else ""
        parts["answer"] = text_line(
            rf"\text{{Surface area}} = {format_sf(_total(params))}{unit}{square}",
            lower,
            colour=style.HIGHLIGHT_COLOUR,
        )
        return parts

    def stages(self, params: NetFolderParams, level) -> list[Stage]:
        groups = _net(params)
        rows = [f"row_{i}" for i in range(1, len(_working(params, groups, "")) + 1)]
        unfold = [
            stage(f"faces_{i + 1}", words, 2.5, [f"faces_{i + 1}"])
            for i, words in enumerate(_group_words(params))
        ]
        steps = [
            stage("question", "Unfold the solid and lay its faces flat", 2.0, ["question"]),
            *unfold,
            stage("count", "Count the faces, edges and vertices", 3.0, rows[:1]),
            stage(
                "area",
                "The surface area is the area of the whole net",
                3.5,
                rows[1:],
                emphasise=rows[-1:],
            ),
            stage("answer", "So", 1.5, ["answer"], emphasise=["answer"]),
        ]

        def standard(s):
            return [
                combine("net", "Unfold the solid into its net", 4.0, *s[: 1 + len(unfold)]),
                *s[1 + len(unfold) :],
            ]

        def concise(s):
            return [
                combine("net", "Unfold the solid into its net", 4.0, *s[: 1 + len(unfold)]),
                combine("area", "Add up the faces", 4.0, *s[1 + len(unfold) :]),
            ]

        return by_level(level, steps, standard, concise)


def _n(value):
    return sp.nsimplify(value)


def _plain(value) -> str:
    return format_sf(value, 6)


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _outline(face):
    if face[0] == "circle":
        _, (cx, cy), r = face
        return [(cx - r, cy - r), (cx + r, cy + r)]
    return face


def _net(params: NetFolderParams) -> list[tuple[str, list]]:
    """Groups of matching faces: (label, faces), each face a list of points or a circle."""
    s = params.solid
    if s in ("cube", "cuboid"):
        L = params.length
        W = params.length if s == "cube" else params.width
        H = params.length if s == "cube" else params.height
        a, b, c = _plain(L), _plain(W), _plain(H)
        return [
            (rf"{a} \times {b}", [_rect(0, H, L, W), _rect(0, 2 * H + W, L, W)]),
            (rf"{a} \times {c}", [_rect(0, 0, L, H), _rect(0, H + W, L, H)]),
            (rf"{b} \times {c}", [_rect(-W, H + W, W, H), _rect(L, H + W, W, H)]),
        ]
    if s == "prism":
        L, b, h = params.length, params.width, params.height
        hyp = math.hypot(b, h)
        return [
            (
                rf"\tfrac{{1}}{{2}} \times {_plain(b)} \times {_plain(h)}",
                [[(0, L), (b, L), (0, L + h)], [(0, 0), (b, 0), (0, -h)]],
            ),
            (rf"{_plain(b)} \times {_plain(L)}", [_rect(0, 0, b, L)]),
            (rf"{_plain(h)} \times {_plain(L)}", [_rect(b, 0, h, L)]),
            (rf"{format_sf(hyp)} \times {_plain(L)}", [_rect(b + h, 0, hyp, L)]),
        ]
    if s == "pyramid":
        a, slant = params.width, params.height
        return [
            (rf"{_plain(a)} \times {_plain(a)}", [_rect(0, 0, a, a)]),
            (
                rf"\tfrac{{1}}{{2}} \times {_plain(a)} \times {_plain(slant)}",
                [
                    [(0, a), (a, a), (a / 2, a + slant)],
                    [(0, 0), (a, 0), (a / 2, -slant)],
                    [(0, 0), (0, a), (-slant, a / 2)],
                    [(a, 0), (a, a), (a + slant, a / 2)],
                ],
            ),
        ]
    r, h = params.radius, params.height
    width = 2 * math.pi * r
    return [
        (rf"2\pi \times {_plain(r)} \times {_plain(h)}", [_rect(0, 0, width, h)]),
        (
            rf"\pi \times {_plain(r)}^2",
            [("circle", (width / 2, h + r), r), ("circle", (width / 2, -r), r)],
        ),
    ]


def _group_words(params: NetFolderParams) -> list[str]:
    s = params.solid
    if s in ("cube", "cuboid"):
        return ["The top and the bottom", "The front and the back", "The two ends"]
    if s == "prism":
        return [
            "The two triangular ends",
            "The base rectangle",
            "The upright rectangle",
            "The sloping rectangle",
        ]
    if s == "pyramid":
        return ["The square base", "Four triangular faces fold up to meet at the top"]
    return ["The curved surface unrolls into a rectangle, 2 pi r long", "And the two circular ends"]


def _total(params: NetFolderParams) -> sp.Expr:
    s = params.solid
    if s in ("cube", "cuboid"):
        L = _n(params.length)
        W = L if s == "cube" else _n(params.width)
        H = L if s == "cube" else _n(params.height)
        return 2 * (L * W + L * H + W * H)
    if s == "prism":
        L, b, h = _n(params.length), _n(params.width), _n(params.height)
        return b * h + L * (b + h + sp.sqrt(b**2 + h**2))
    if s == "pyramid":
        a, slant = _n(params.width), _n(params.height)
        return a**2 + 2 * a * slant
    r, h = _n(params.radius), _n(params.height)
    return 2 * sp.pi * r * h + 2 * sp.pi * r**2


def _working(params: NetFolderParams, groups, unit: str) -> list[str]:
    s = params.solid
    if s == "cylinder":
        count = r"\text{2 flat faces and 1 curved surface}"
    else:
        f, e, v = COUNTS[s]
        count = rf"\text{{{f} faces, {e} edges, {v} vertices}}"
    terms = []
    for tex, faces in groups:
        terms.append(tex if len(faces) == 1 else rf"{len(faces)}({tex})")
    total = _total(params)
    value = latex_with_pi(total) if total.has(sp.pi) else format_sf(total)
    return [
        count,
        r"A = " + " + ".join(terms[:2]),
        *(rf"+ {t}" for t in terms[2:]),
        rf"A = {value}",
    ]


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
