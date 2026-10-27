"""TransformationStage: reflection, rotation, translation and enlargement of a shape on a grid,
with the transformation shown moving the shape and described in full, as an exam asks
(4024 7.1; PRIMITIVES.md #42).

A reflection needs its mirror line; a rotation its centre, angle and direction; a translation
its column vector; an enlargement its centre and scale factor (which may be fractional or
negative). The image's vertices are worked out exactly and labelled with primes.
"""

import math
from typing import Annotated, Literal

import sympy as sp
from manim import Arc, Arrow, DashedLine, Dot, Polygon, Rotate, Transform, VGroup
from pydantic import Field

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.primitives import style
from app.primitives.plotting import label, make_plot, text_line
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage
from app.primitives.symbolic import format_sf

Coordinate = Annotated[float, Field(ge=-20, le=20)]
Vertex = tuple[Coordinate, Coordinate]
Mirror = Literal["x=a", "y=b", "y=x", "y=-x"]


class TransformationStageParams(PrimitiveParams):
    kind: Literal["reflection", "rotation", "translation", "enlargement"]
    shape: list[Vertex] = Field(min_length=3, max_length=6, description="The object's vertices")
    mirror: Mirror = Field(default="y=x", description="For reflection")
    line_value: Coordinate = Field(default=0, description="a in x = a, or b in y = b")
    centre: Vertex = Field(default=(0, 0), description="For rotation and enlargement")
    angle: Literal[90, 180, 270] = 90
    clockwise: bool = False
    vector: Vertex = Field(default=(3, 1), description="For translation: the column vector")
    scale: Annotated[float, Field(ge=-4, le=4)] = Field(default=2, description="Scale factor")


class TransformationStage(StagedPrimitive[TransformationStageParams]):
    primitive_id = "TransformationStage"
    version = "1"
    topic = "Transformations"
    params_model = TransformationStageParams
    layout = LayoutContract(
        region=style.GRAPH_REGION,
        allowed_overlaps=[("axes", "*"), ("object", "*"), ("image", "*"), ("guide", "*")],
    )

    def default_params(self) -> TransformationStageParams:
        return TransformationStageParams(
            kind="enlargement", shape=[(1, 1), (3, 1), (1, 2)], centre=(0, 0), scale=2
        )

    def validate(self, params: TransformationStageParams) -> list[PredicateFailure]:
        if params.kind == "enlargement" and params.scale == 0:
            return [_failure("nonzero_scale", "a scale factor of 0 makes a point", "scale")]
        if params.kind == "translation" and params.vector == (0, 0):
            return [_failure("moves", "the zero vector does not move the shape", "vector")]
        image = _image(params)
        if max(abs(float(c)) for p in image for c in p) > 20:
            return [_failure("image_fits", "the image goes off the grid", "shape")]
        return []

    def computed_values(self, params: TransformationStageParams) -> dict[str, str]:
        return {
            "image": "; ".join(f"({_n(x)}, {_n(y)})" for x, y in _image(params)),
            "description": _describe(params, tex=False),
        }

    def build(self, params: TransformationStageParams, level):
        image = _image(params)
        pts = [(float(x), float(y)) for x, y in params.shape]
        img = [(float(x), float(y)) for x, y in image]
        extra = (
            [tuple(map(float, params.centre))] if params.kind in ("rotation", "enlargement") else []
        )
        xs = [p[0] for p in pts + img + extra]
        ys = [p[1] for p in pts + img + extra]
        plot = make_plot(self.layout.region, xs, ys, equal=True)
        letters = "ABCDEF"
        obj = Polygon(
            *(plot.point(*p) for p in pts),
            color=style.CURVE_COLOUR,
            stroke_width=4,
            fill_color=style.CURVE_COLOUR,
            fill_opacity=0.35,
        )
        out = Polygon(
            *(plot.point(*p) for p in img),
            color=style.HIGHLIGHT_COLOUR,
            stroke_width=4,
            fill_color=style.HIGHLIGHT_COLOUR,
            fill_opacity=0.35,
        )
        centre_obj = obj.get_center_of_mass()
        centre_img = out.get_center_of_mass()
        obj_labels = VGroup(
            *(
                label(letters[i], size=24, colour=style.CURVE_COLOUR).move_to(
                    plot.point(*p) + 0.25 * _away(plot.point(*p), centre_obj)
                )
                for i, p in enumerate(pts)
            )
        )
        img_labels = VGroup(
            *(
                label(letters[i] + "'", size=24, colour=style.HIGHLIGHT_COLOUR).move_to(
                    plot.point(*p) + 0.25 * _away(plot.point(*p), centre_img)
                )
                for i, p in enumerate(img)
            )
        )
        parts = {
            "axes": VGroup(plot.axes, plot.x_label, plot.y_label),
            "object": VGroup(obj, obj_labels),
            "image": VGroup(out, img_labels),
            "question": text_line(r"\text{Describe the transformation}", plot.upper),
            "answer": text_line(
                _describe(params, tex=True), plot.lower, colour=style.HIGHLIGHT_COLOUR
            ),
        }
        guide = VGroup()
        if params.kind == "reflection":
            lo, hi = plot.x_range[0], plot.x_range[1]
            ylo, yhi = plot.y_range[0], plot.y_range[1]
            ends = {
                "x=a": [(params.line_value, ylo), (params.line_value, yhi)],
                "y=b": [(lo, params.line_value), (hi, params.line_value)],
                "y=x": [(max(lo, ylo), max(lo, ylo)), (min(hi, yhi), min(hi, yhi))],
                "y=-x": [(max(lo, -yhi), -max(lo, -yhi)), (min(hi, -ylo), -min(hi, -ylo))],
            }[params.mirror]
            guide.add(
                DashedLine(
                    plot.point(*ends[0]),
                    plot.point(*ends[1]),
                    color=style.TANGENT_COLOUR,
                    stroke_width=3,
                )
            )
        elif params.kind in ("rotation", "enlargement"):
            c = plot.point(*map(float, params.centre))
            guide.add(Dot(c, color=style.TANGENT_COLOUR, radius=0.08))
            if params.kind == "enlargement":
                for p, q in zip(pts, img, strict=True):
                    # a ray from the centre through the point and its image; with a negative
                    # scale factor the image is on the other side, so the line runs through c
                    if params.scale < 0:
                        start, end = plot.point(*p), plot.point(*q)
                    else:
                        start = c
                        end = plot.point(*(q if abs(params.scale) >= 1 else p))
                    guide.add(DashedLine(start, end, color=style.TANGENT_COLOUR, stroke_width=2))
            else:
                p0 = plot.point(*pts[0])
                radius = math.dist(c[:2], p0[:2])
                start = math.atan2(p0[1] - c[1], p0[0] - c[0])
                turn = math.radians(params.angle) * (-1 if params.clockwise else 1)
                guide.add(
                    Arc(
                        radius=radius,
                        start_angle=start,
                        angle=turn,
                        arc_center=c,
                        color=style.TANGENT_COLOUR,
                        stroke_width=3,
                    )
                )
        else:
            for p, q in list(zip(pts, img, strict=True))[:1]:  # one vertex shows the vector
                guide.add(
                    Arrow(
                        plot.point(*p),
                        plot.point(*q),
                        buff=0.05,
                        color=style.TANGENT_COLOUR,
                        stroke_width=3,
                        max_tip_length_to_length_ratio=0.15,
                    )
                )
        parts["guide"] = guide
        self._move = (obj, out, params)
        return parts

    def move(self, scene, parts, level, run_time, min_run_time):
        """A copy of the object moves onto the image."""
        obj, out, params = self._move
        moving = obj.copy()
        scene.add(moving)
        hold = min(0.15, 0.2 * run_time)
        animation_time = min(max(min_run_time, 0.7 * run_time), run_time - hold)
        if params.kind == "rotation":
            turn = math.radians(params.angle) * (-1 if params.clockwise else 1)
            plot_centre = parts["guide"][0].get_center()
            scene.play(Rotate(moving, angle=turn, about_point=plot_centre), run_time=animation_time)
        else:
            scene.play(Transform(moving, out.copy()), run_time=animation_time)
        scene.remove(moving)
        scene.wait(run_time - animation_time)

    def stages(self, params: TransformationStageParams, level) -> list[Stage]:
        guide_words = {
            "reflection": "The mirror line: each point goes the same distance the other side",
            "rotation": "The centre of rotation: each point turns about it",
            "translation": "Every point moves by the same vector",
            "enlargement": "Lines from the centre through each point: distances times the "
            "scale factor",
        }[params.kind]
        steps = [
            stage("object", "Here is the shape", 2.0, ["question", "axes", "object"]),
            stage("guide", guide_words, 3.5, ["guide"]),
            stage("move", "Move the shape", 4.0, ["image"], motion="move"),
            stage("answer", "So the transformation is", 2.5, ["answer"], emphasise=["answer"]),
        ]

        def concise(s):
            return [combine("setup", s[1].description, 4.0, s[0], s[1]), s[2], s[3]]

        return by_level(level, steps, lambda s: s, concise)


def _n(value) -> str:
    return format_sf(value, 6)


def _away(point, centre):
    v = point - centre
    norm = (v[0] ** 2 + v[1] ** 2) ** 0.5 or 1
    return v / norm


def _image(params: TransformationStageParams) -> list[tuple[sp.Expr, sp.Expr]]:
    out = []
    cx, cy = (sp.nsimplify(v) for v in params.centre)
    for x, y in params.shape:
        x, y = sp.nsimplify(x), sp.nsimplify(y)
        if params.kind == "reflection":
            a = sp.nsimplify(params.line_value)
            x, y = {"x=a": (2 * a - x, y), "y=b": (x, 2 * a - y), "y=x": (y, x), "y=-x": (-y, -x)}[
                params.mirror
            ]
        elif params.kind == "rotation":
            turns = (params.angle // 90) % 4
            if params.clockwise:
                turns = (4 - turns) % 4
            dx, dy = x - cx, y - cy
            for _ in range(turns):  # each quarter turn anticlockwise: (x, y) -> (-y, x)
                dx, dy = -dy, dx
            x, y = cx + dx, cy + dy
        elif params.kind == "translation":
            x, y = x + sp.nsimplify(params.vector[0]), y + sp.nsimplify(params.vector[1])
        else:
            k = sp.nsimplify(params.scale)
            x, y = cx + k * (x - cx), cy + k * (y - cy)
        out.append((x, y))
    return out


def _describe(params: TransformationStageParams, tex: bool) -> str:
    centre = f"({_n(params.centre[0])}, {_n(params.centre[1])})"
    if params.kind == "reflection":
        line = {
            "x=a": f"x = {_n(params.line_value)}",
            "y=b": f"y = {_n(params.line_value)}",
            "y=x": "y = x",
            "y=-x": "y = -x",
        }[params.mirror]
        return rf"\text{{Reflection in the line }} {line}" if tex else f"Reflection in {line}"
    if params.kind == "rotation":
        way = (
            "" if params.angle == 180 else (" clockwise" if params.clockwise else " anticlockwise")
        )
        text = f"Rotation of {params.angle}°{way} about {centre}"
        if tex:
            return rf"\text{{Rotation }} {params.angle}^\circ\text{{{way} about {centre}}}"
        return text
    if params.kind == "translation":
        a, b = (_n(v) for v in params.vector)
        if tex:
            return (
                rf"\text{{Translation by }} \left(\begin{{smallmatrix}} {a} \\ {b}"
                rf"\end{{smallmatrix}}\right)"
            )
        return f"Translation by ({a}, {b})"
    k = format_sf(sp.nsimplify(params.scale))
    if tex:
        k_tex = sp.latex(sp.nsimplify(params.scale))
        return rf"\text{{Enlargement, scale factor }} {k_tex}\text{{, centre {centre}}}"
    return f"Enlargement, scale factor {k}, centre {centre}"


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )
