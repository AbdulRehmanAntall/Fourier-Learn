"""The base of most primitives: a picture built from named parts, revealed in stages.

A staged primitive builds every object of its picture up front, by name (`build`), and lists the
steps that reveal them at each level (`stages`). The animation, the step list the narration is
written against, and the layout check's object names all come from that one plan, so `steps` and
`animate` cannot disagree (docs/primitives.md, rule 13).

A stage can show parts, hide them, turn one part into another (`morph`), and emphasise parts.
A stage whose picture moves continuously (a tangent sliding, a point travelling) names a
`motion`: a method of the primitive that plays the whole step itself and takes exactly its run
time.

Level conventions (report Table 5.3): Level 1 shows each part in its own step and emphasises the
new ones; Level 2 is the reference; Level 3 shows the main steps only. `combine` merges stages,
so a primitive usually writes its Level 1 stages once and merges them for the other levels.
"""

from abc import abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import ClassVar

from manim import (
    UP,
    Animation,
    Create,
    DecimalNumber,
    Dot,
    FadeIn,
    FadeOut,
    GrowFromCenter,
    Indicate,
    Integer,
    MathTex,
    Mobject,
    ReplacementTransform,
    Succession,
    Tex,
    Text,
    VMobject,
    Write,
)

from app.contracts import Level, Primitive, PrimitiveParams, StepSpec
from app.primitives import style

Parts = dict[str, Mobject]


@dataclass(frozen=True)
class Stage:
    name: str
    description: str
    """What the step shows; the narration has one passage per step, written from this."""
    min_run_time: float
    show: tuple[str, ...] = ()
    hide: tuple[str, ...] = ()
    morph: tuple[tuple[str, str], ...] = ()
    """(old, new): the part `old` turns into `new`; old leaves the screen, new stays."""
    emphasise: tuple[str, ...] = ()
    motion: str | None = None
    """A method name: `self.<motion>(scene, parts, level, run_time, min_run_time)` plays the
    step. It may move parts that are already visible; parts in `show` appear after it."""
    labels: int | None = None
    highlights: int | None = None

    def spec(self) -> StepSpec:
        return StepSpec(
            name=self.name,
            description=self.description,
            min_run_time_s=self.min_run_time,
            labels=len(self.show) if self.labels is None else self.labels,
            highlights=len(self.emphasise) if self.highlights is None else self.highlights,
        )


def stage(
    name: str,
    description: str,
    min_run_time: float,
    show: Sequence[str] = (),
    *,
    hide: Sequence[str] = (),
    morph: Sequence[tuple[str, str]] = (),
    emphasise: Sequence[str] = (),
    motion: str | None = None,
) -> Stage:
    return Stage(
        name,
        description,
        min_run_time,
        tuple(show),
        tuple(hide),
        tuple(morph),
        tuple(emphasise),
        motion,
    )


def combine(name: str, description: str, min_run_time: float, *stages: Stage) -> Stage:
    """One step that does what `stages` do one after another, all at once. A part shown and then
    morphed or hidden within the step is resolved to what is left at its end."""
    if any(s.motion for s in stages):
        raise ValueError("a stage with a motion cannot be combined with others")
    show: list[str] = []
    hide: list[str] = []
    morph: list[tuple[str, str]] = []
    for current in stages:
        for old, new in current.morph:
            if old in show:
                show[show.index(old)] = new
            else:
                morph.append((old, new))
        for item in current.show:
            show.append(item)
        for item in current.hide:
            if item in show:
                show.remove(item)
            else:
                hide.append(item)
    emphasise = tuple(n for s in stages for n in s.emphasise if n in show or n not in hide)
    return Stage(name, description, min_run_time, tuple(show), tuple(hide), tuple(morph), emphasise)


def by_level(
    level: Level,
    supported: Sequence[Stage],
    standard: Callable[[Sequence[Stage]], Sequence[Stage]],
    concise: Callable[[Sequence[Stage]], Sequence[Stage]],
) -> list[Stage]:
    """The Level 1 stages, or the Level 2 or 3 stages made from them."""
    if level is Level.SUPPORTED:
        return list(supported)
    if level is Level.STANDARD:
        return list(standard(supported))
    return list(concise(supported))


@dataclass
class Intro:
    """How parts appear, by name pattern; the first matching pattern wins."""

    rules: list[tuple[str, str]] = field(default_factory=list)

    def kind(self, name: str) -> str | None:
        for pattern, kind in self.rules:
            if fnmatchcase(name, pattern):
                return kind
        return None


class StagedPrimitive[P: PrimitiveParams](Primitive[P]):
    """A primitive drawn by revealing named parts in stages."""

    intro: ClassVar[list[tuple[str, str]]] = []
    """(pattern, kind) overrides of how a part appears: "create", "write", "fade", "grow",
    "fade_up" (fade in moving up)."""

    @abstractmethod
    def build(self, params: P, level: Level) -> Parts:
        """Every object of the picture, by name, already laid out in the primitive's region."""

    @abstractmethod
    def stages(self, params: P, level: Level) -> list[Stage]:
        """The steps at a level."""

    def steps(self, params: P, level: Level) -> list[StepSpec]:
        return [s.spec() for s in self.stages(params, level)]

    def introduce(self, name: str, mobject: Mobject) -> Animation:
        kind = Intro(self.intro).kind(name) or _default_kind(mobject)
        if kind == "create":
            return Create(mobject)
        if kind == "write":
            return Write(mobject)
        if kind == "grow":
            return GrowFromCenter(mobject)
        if kind == "fade_up":
            return FadeIn(mobject, shift=0.2 * UP)
        if kind == "dot":
            return FadeIn(mobject, scale=0.5)
        return FadeIn(mobject)

    def animate(self, scene, params, level, run_times, carried):
        fades, visible = style.clear_region(carried, self.layout.region)
        parts = self.build(params, level)
        plan = self.stages(params, level)
        for i, (current, run_time) in enumerate(zip(plan, run_times, strict=True)):
            if current.motion:
                if i == 0:
                    raise ValueError("the first stage cannot be a motion")
                getattr(self, current.motion)(scene, parts, level, run_time, current.min_run_time)
                for name in current.hide:
                    scene.remove(parts[name])
                    visible.pop(name, None)
                for name in current.show:
                    scene.add(parts[name])
                    visible[name] = parts[name]
                yield dict(visible)
                continue

            animations: list[Animation] = list(fades) if i == 0 else []
            for old, new in current.morph:
                animations.append(ReplacementTransform(parts[old], parts[new]))
                visible.pop(old, None)
                visible[new] = parts[new]
            for name in current.show:
                appear = self.introduce(name, parts[name])
                if level is Level.SUPPORTED and name in current.emphasise:
                    appear = Succession(appear, Indicate(parts[name]))
                animations.append(appear)
                visible[name] = parts[name]
            for name in current.emphasise:
                if name not in current.show:
                    animations.append(Indicate(parts[name]))
            for name in current.hide:
                animations.append(FadeOut(parts[name]))
                visible.pop(name, None)
            play_step(scene, animations, run_time, current.min_run_time)
            yield dict(visible)


_TEXT_TYPES = (MathTex, Tex, Text, DecimalNumber, Integer)

FINAL_HOLD_S = 0.15
"""Every step ends on its finished picture for at least this long. Without it, a step whose
animation fills its run time ends a frame before the animation completes, and the last stroke
drawn (such as the last digit of an axis number) is missing from the step's final frame."""


def play_step(scene, animations: Sequence[Animation], run_time: float, min_run_time: float):
    """Play one step in exactly `run_time`: the animation, then a hold on the result."""
    hold = min(FINAL_HOLD_S, 0.2 * run_time)
    animation_time = min(max(min_run_time, 0.6 * run_time), run_time - hold)
    if animations:
        scene.play(*animations, run_time=animation_time)
    else:
        scene.wait(animation_time)
    scene.wait(run_time - animation_time)


def _default_kind(mobject: Mobject) -> str:
    if isinstance(mobject, Dot):
        return "dot"
    if isinstance(mobject, _TEXT_TYPES) or _all_text(mobject):
        return "write"
    if isinstance(mobject, VMobject) and _is_filled_without_stroke(mobject):
        return "fade"
    if isinstance(mobject, VMobject):
        return "create"
    return "fade"


def _all_text(mobject: Mobject) -> bool:
    children = mobject.submobjects
    return bool(children) and all(isinstance(c, _TEXT_TYPES) for c in children)


def _is_filled_without_stroke(mobject: VMobject) -> bool:
    family = [m for m in mobject.family_members_with_points() if isinstance(m, VMobject)]
    return bool(family) and all(
        m.get_fill_opacity() > 0 and m.get_stroke_width() == 0 for m in family
    )


def visible_names(stages: Sequence[Stage]) -> list[set[str]]:
    """The names visible after each stage, for tests: every shown name must exist, and nothing
    may be shown twice or hidden before it appears."""
    visible: set[str] = set()
    after = []
    for current in stages:
        for old, new in current.morph:
            if old not in visible:
                raise ValueError(f"{current.name}: morphs {old!r}, which is not visible")
            visible.discard(old)
            if new in visible:
                raise ValueError(f"{current.name}: {new!r} is already visible")
            visible.add(new)
        for name in current.show:
            if name in visible:
                raise ValueError(f"{current.name}: {name!r} is already visible")
            visible.add(name)
        for name in current.hide:
            if name not in visible:
                raise ValueError(f"{current.name}: hides {name!r}, which is not visible")
            visible.discard(name)
        after.append(set(visible))
    return after


def check_plan(parts: Mapping[str, Mobject], stages: Sequence[Stage]) -> None:
    """Raise if the stages refer to a part that `build` did not make."""
    names = set(parts)
    for current in stages:
        used = set(current.show) | set(current.hide) | set(current.emphasise)
        used |= {n for pair in current.morph for n in pair}
        missing = used - names
        if missing:
            raise ValueError(f"{current.name}: no parts named {sorted(missing)}")
    visible_names(stages)
