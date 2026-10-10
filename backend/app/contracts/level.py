"""Difficulty levels (report §5.4.1, Table 5.3)."""

from enum import IntEnum


class Level(IntEnum):
    """The three renderings of every micro-module.

    The levels differ in how much of the explanation is shown and how quickly it is delivered,
    not in what is taught. Level 2 is the reference level.
    """

    SUPPORTED = 1
    STANDARD = 2
    CONCISE = 3

    @property
    def label(self) -> str:
        """The value stored in MODULE.difficulty_level (Table 4.8), e.g. "Level 2"."""
        return f"Level {self.value}"

    @classmethod
    def from_label(cls, label: str) -> "Level":
        prefix = "Level "
        if not label.startswith(prefix) or not label[len(prefix) :].isdigit():
            raise ValueError(f"not a difficulty level label: {label!r}")
        return cls(int(label[len(prefix) :]))

    def lower(self) -> "Level | None":
        """The level an "I'm Lost" press switches to, or None at Level 1 (§5.6.3)."""
        return Level(self - 1) if self > Level.SUPPORTED else None


# Target durations of one module (Table 5.3). Level 2 is planned to run for about 60 seconds,
# Level 1 adds steps and slows the pace up to a cap of 90 seconds, Level 3 runs under 60 seconds.
LEVEL_1_MAX_DURATION_S = 90.0
LEVEL_2_TARGET_DURATION_S = 60.0
LEVEL_3_MAX_DURATION_S = 60.0
