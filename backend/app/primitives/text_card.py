"""TextCard: words on screen: a topic heading, a question in the learner's own words, or key
points shown one at a time, with inline maths between dollar signs (all topics).

The text comes from the language model, so it is checked before it reaches LaTeX: outside the
maths only plain words and punctuation are allowed (a dollar sign for money is written \\$),
and inside the maths only a known list of commands, with balanced braces. A card fills the
whole frame, or sits in the working region on the right beside a graph primitive, so that a
question stays in view while it is solved.
"""

import re
from typing import Annotated, Literal

from manim import DOWN, LEFT, Line, Tex, VGroup
from pydantic import Field, StringConstraints

from app.contracts import LayoutContract, PredicateFailure, PrimitiveParams
from app.contracts.primitive import FULL_FRAME
from app.primitives import style
from app.primitives.staged import Stage, StagedPrimitive, by_level, combine, stage

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
Point = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=140)]

# Commands allowed inside $...$; anything else (\input, \def, \write18, ...) is refused.
MATHS_COMMANDS = {
    "frac",
    "tfrac",
    "dfrac",
    "sqrt",
    "times",
    "div",
    "pm",
    "mp",
    "cdot",
    "pi",
    "theta",
    "alpha",
    "beta",
    "gamma",
    "delta",
    "Delta",
    "lambda",
    "mu",
    "sigma",
    "Sigma",
    "phi",
    "omega",
    "le",
    "leq",
    "ge",
    "geq",
    "ne",
    "neq",
    "approx",
    "equiv",
    "infty",
    "circ",
    "degree",
    "sin",
    "cos",
    "tan",
    "log",
    "ln",
    "left",
    "right",
    "mathbf",
    "overrightarrow",
    "vec",
    "bar",
    "hat",
    "angle",
    "triangle",
    "perp",
    "parallel",
    "in",
    "notin",
    "cup",
    "cap",
    "subset",
    "emptyset",
    "to",
    "rightarrow",
    "Rightarrow",
    "quad",
    "text",
    "dots",
    "ldots",
    "prime",
    "%",
    "$",
    ",",
    " ",
}
TEXT_CHARACTERS = re.compile(r"^[A-Za-z0-9\s.,;:!?'\"()\[\]\-–—/%&+=<>×÷°£€*@]*$")
COMMAND = re.compile(r"\\([A-Za-z]+|.)")
SIZES = {"full": (46, 54), "side": (34, 28)}  # (body size, characters per line)
TITLE_SIZE = {"full": 72, "side": 48}


class TextCardParams(PrimitiveParams):
    layout: Literal["title", "question", "points"]
    title: Short | None = Field(
        default=None, description='The heading: the topic, "Question", or "Key points"'
    )
    subtitle: Short | None = Field(default=None, description="For title: a line under it")
    text: Body | None = Field(
        default=None,
        description='For question: the question, maths between $...$, e.g. "Solve $2x + 3 = 7$"',
    )
    points: list[Point] | None = Field(
        default=None, min_length=1, max_length=6, description="For points: one line each"
    )
    place: Literal["full", "side"] = Field(
        default="full", description="full: the whole frame; side: the right, beside a graph"
    )


class TextCard(StagedPrimitive[TextCardParams]):
    primitive_id = "TextCard"
    version = "1"
    topic = "All topics"
    params_model = TextCardParams
    layout = LayoutContract(region=FULL_FRAME)

    def default_params(self) -> TextCardParams:
        return TextCardParams(layout="title", title="Circle theorems", subtitle="Angles in circles")

    def validate(self, params: TextCardParams) -> list[PredicateFailure]:
        if params.layout == "title" and params.title is None:
            return [_failure("needs_title", "a title card needs a title", "title")]
        if params.layout == "question" and params.text is None:
            return [_failure("needs_text", "a question card needs the question", "text")]
        if params.layout == "points" and params.points is None:
            return [_failure("needs_points", "a points card needs its points", "points")]
        pieces = [("title", params.title), ("subtitle", params.subtitle), ("text", params.text)]
        pieces += [(f"points[{i}]", p) for i, p in enumerate(params.points or [])]
        for name, value in pieces:
            if value is None:
                continue
            problem = _check(value)
            if problem:
                return [_failure("safe_text", f"{name}: {problem}", name.split("[")[0])]
        return []

    def computed_values(self, params: TextCardParams) -> dict[str, str]:
        return {"lines": str(len(_lines(params)))}

    def animate(self, scene, params, level, run_times, carried):
        # the region depends on where the card goes, so it is set before anything is cleared
        region = FULL_FRAME if params.place == "full" else style.WORKING_REGION
        self.layout = LayoutContract(region=region)
        yield from super().animate(scene, params, level, run_times, carried)

    def build(self, params: TextCardParams, level):
        region = FULL_FRAME if params.place == "full" else style.WORKING_REGION
        box = style.region_box(region).shrink(style.PADDING + 0.2)
        body_size, _ = SIZES[params.place]
        parts = {}
        rows = []
        if params.title:
            size = TITLE_SIZE[params.place] if params.layout == "title" else body_size + 8
            colour = style.TEXT_COLOUR if params.layout == "title" else style.HIGHLIGHT_COLOUR
            parts["title"] = Tex(_tex(params.title), font_size=size, color=colour)
            rows.append(parts["title"])
        if params.layout == "title":
            rule = Line(LEFT * 2, -LEFT * 2, color=style.HIGHLIGHT_COLOUR, stroke_width=4)
            parts["rule"] = rule
            rows.append(rule)
            if params.subtitle:
                parts["subtitle"] = Tex(
                    _tex(params.subtitle), font_size=body_size - 4, color=style.CURVE_COLOUR
                )
                rows.append(parts["subtitle"])
        elif params.layout == "question":
            lines = VGroup(*(Tex(_tex(line), font_size=body_size) for line in _lines(params)))
            lines.arrange(DOWN, aligned_edge=LEFT, buff=0.18)
            parts["text"] = lines
            rows.append(lines)
        else:
            for i, point in enumerate(params.points, start=1):
                wrapped = _wrap(point, SIZES[params.place][1] - 3)
                item = VGroup(
                    *(
                        Tex(_tex(("" if k else r"\textbullet\ ") + line), font_size=body_size)
                        for k, line in enumerate(wrapped)
                    )
                )
                item.arrange(DOWN, aligned_edge=LEFT, buff=0.12)
                for k in range(1, len(item)):
                    item[k].shift([0.35, 0, 0])  # wrapped lines sit under the words, not the dot
                parts[f"point_{i}"] = item
                rows.append(item)
        group = VGroup(*rows)
        if params.layout == "title":
            group.arrange(DOWN, buff=0.35)
            if params.place == "full":
                rule.scale_to_fit_width(max(group[0].width * 0.8, 1.0))
            else:
                rule.scale_to_fit_width(min(box.width * 0.8, group[0].width))
        else:
            group.arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        style.fit_inside(group, box)
        if params.layout != "title":
            # a question or a list reads from the top-left, not from the middle
            group.align_to([box.left, 0, 0], LEFT).align_to([0, box.top, 0], [0, 1, 0])
        return parts

    def stages(self, params: TextCardParams, level) -> list[Stage]:
        heading = ["title"] if params.title else []
        if params.layout == "title":
            steps = [stage("title", _spoken(params.title), 2.0, ["title", "rule"])]
            if params.subtitle:
                steps.append(stage("subtitle", _spoken(params.subtitle), 1.5, ["subtitle"]))
        elif params.layout == "question":
            steps = [stage("question", _spoken(params.text), 3.0, [*heading, "text"])]
            if heading:
                steps = [
                    stage("heading", _spoken(params.title), 1.0, heading),
                    stage("question", _spoken(params.text), 3.0, ["text"]),
                ]
        else:
            steps = [stage("heading", _spoken(params.title), 1.0, heading)] if heading else []
            steps += [
                stage(f"point_{i}", _spoken(point), 2.5, [f"point_{i}"])
                for i, point in enumerate(params.points, start=1)
            ]

        def concise(s):
            if len(s) == 1:
                return list(s)
            return [combine("card", " ".join(x.description for x in s), 3.0, *s)]

        return by_level(level, steps, lambda s: s, concise)


def _failure(predicate, message, parameter) -> PredicateFailure:
    return PredicateFailure(
        kind="consistency", predicate=predicate, message=message, parameters=[parameter]
    )


def _segments(value: str) -> list[tuple[bool, str]]:
    """(is maths, text) pieces; an escaped \\$ stays in the text."""
    pieces, maths, current, i = [], False, "", 0
    while i < len(value):
        if value.startswith(r"\$", i) and not maths:
            current += r"\$"
            i += 2
            continue
        if value[i] == "$":
            pieces.append((maths, current))
            maths, current = not maths, ""
        else:
            current += value[i]
        i += 1
    pieces.append((maths, current))
    return [(m, t) for m, t in pieces if t]


def _check(value: str) -> str | None:
    """Why the text is unsafe to pass to LaTeX, or None."""
    if value.replace(r"\$", "").count("$") % 2:
        return "a $ is not closed (write \\$ for a dollar sign)"
    for maths, text in _segments(value):
        if maths:
            for command in COMMAND.findall(text):
                if command not in MATHS_COMMANDS:
                    return f"\\{command} is not allowed in maths"
            depth = 0
            for ch in text:
                depth += (ch == "{") - (ch == "}")
                if depth < 0:
                    return "the braces in the maths do not match"
            if depth:
                return "the braces in the maths do not match"
        elif not TEXT_CHARACTERS.match(text.replace(r"\$", "")):
            bad = sorted({c for c in text.replace(r"\$", "") if not TEXT_CHARACTERS.match(c)})
            return f"characters not allowed in text: {''.join(bad)} (put maths between $...$)"
    return None


def _tex(value: str) -> str:
    """LaTeX for checked text: special text characters escaped, maths kept as it is."""
    out = []
    for maths, text in _segments(value):
        if maths:
            out.append(f"${text}$")
        else:
            text = text.replace(r"\$", "\x00")
            for ch, escaped in (
                ("%", r"\%"),
                ("&", r"\&"),
                ("<", r"$<$"),
                (">", r"$>$"),
                ("×", r"$\times$"),
                ("÷", r"$\div$"),
                ("°", r"$^\circ$"),
                ("£", r"\pounds{}"),
                ("€", "EUR"),
                ("–", "--"),
                ("—", "---"),
            ):
                text = text.replace(ch, escaped)
            out.append(text.replace("\x00", r"\$"))
    return "".join(out)


def _visible_length(value: str) -> int:
    """Roughly how wide a piece of text is, counting maths by its symbols, not its commands."""
    length = 0
    for maths, text in _segments(value):
        if maths:
            text = COMMAND.sub("x", text).replace("{", "").replace("}", "")
        length += len(text)
    return length


def _wrap(value: str, width: int) -> list[str]:
    """Lines of at most `width` visible characters, never breaking inside $...$."""
    words, inside = [], False
    for word in value.split(" "):
        if inside and words:
            words[-1] += " " + word
        else:
            words.append(word)
        if word.replace(r"\$", "").count("$") % 2:
            inside = not inside
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and _visible_length(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _lines(params: TextCardParams) -> list[str]:
    if params.layout == "question" and params.text:
        return _wrap(params.text, SIZES[params.place][1])
    if params.layout == "points":
        return [line for p in params.points for line in _wrap(p, SIZES[params.place][1] - 3)]
    return [params.title or ""] + ([params.subtitle] if params.subtitle else [])


SPOKEN = [
    (r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1 over \2"),
    (r"\\sqrt\{([^{}]*)\}", r"the square root of \1"),
    (r"\^\{?2\}?", " squared"),
    (r"\^\{?3\}?", " cubed"),
    (r"\^\{?\\circ\}?", " degrees"),
    (r"\\times", " times "),
    (r"\\div", " divided by "),
    (r"\\pi", "pi"),
    (r"\\theta", "theta"),
    (r"\\le(q)?", " is at most "),
    (r"\\ge(q)?", " is at least "),
    (r"\\ne(q)?", " is not "),
    (r"\\approx", " is about "),
    (r"=", " equals "),
]


def _spoken(value: str | None) -> str:
    """A first draft of the narration for the text: maths read as words."""
    if not value:
        return ""
    text = value.replace(r"\$", " dollars ")
    for pattern, words in SPOKEN:
        text = re.sub(pattern, words, text)
    text = re.sub(r"\\[A-Za-z]+", "", text).replace("$", "").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()
