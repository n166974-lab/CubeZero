"""Motion database for the numbered 2x2 Rubik's Cube net.

Every cycle describes how colors move between fixed sticker positions.
For example, ``(1, 5, 9, 13)`` means:

    color at 1 -> 5
    color at 5 -> 9
    color at 9 -> 13
    color at 13 -> 1

Position numbers never move; only their stored colors are changed.
"""

from typing import Final


MotionCycles = tuple[tuple[int, int, int, int], ...]


MOTION_DESCRIPTIONS: Final[dict[str, str]] = {
    "m1": "top horizontal layer -> right",
    "m2": "top horizontal layer -> left",
    "m3": "bottom horizontal layer -> right",
    "m4": "bottom horizontal layer -> left",
    "m5": "left vertical layer -> up",
    "m6": "left vertical layer -> down",
    "m7": "right vertical layer -> up",
    "m8": "right vertical layer -> down",
}


MOTIONS: Final[dict[str, MotionCycles]] = {
    "m1": (
        (1, 5, 9, 13),
        (2, 6, 10, 14),
        (17, 19, 20, 18),
    ),
    "m2": (
        (1, 13, 9, 5),
        (2, 14, 10, 6),
        (17, 18, 20, 19),
    ),
    "m3": (
        (3, 7, 11, 15),
        (4, 8, 12, 16),
        (21, 22, 24, 23),
    ),
    "m4": (
        (3, 15, 11, 7),
        (4, 16, 12, 8),
        (21, 23, 24, 22),
    ),
    "m5": (
        (1, 17, 12, 21),
        (3, 19, 10, 23),
        (13, 15, 16, 14),
    ),
    "m6": (
        (1, 21, 12, 17),
        (3, 23, 10, 19),
        (13, 14, 16, 15),
    ),
    "m7": (
        (2, 18, 11, 22),
        (4, 20, 9, 24),
        (5, 6, 8, 7),
    ),
    "m8": (
        (2, 22, 11, 18),
        (4, 24, 9, 20),
        (5, 7, 8, 6),
    ),
}


INVERSE_MOTIONS: Final[dict[str, str]] = {
    "m1": "m2",
    "m2": "m1",
    "m3": "m4",
    "m4": "m3",
    "m5": "m6",
    "m6": "m5",
    "m7": "m8",
    "m8": "m7",
}


def get_motion(name: str) -> MotionCycles:
    """Return the position cycles for a motion name."""
    normalized_name = name.lower()
    if normalized_name not in MOTIONS:
        raise ValueError(
            f"Unknown motion {name!r}. Expected one of: {', '.join(MOTIONS)}"
        )
    return MOTIONS[normalized_name]


def get_inverse(name: str) -> str:
    """Return the name of a motion's inverse."""
    normalized_name = name.lower()
    if normalized_name not in INVERSE_MOTIONS:
        raise ValueError(
            f"Unknown motion {name!r}. Expected one of: "
            f"{', '.join(INVERSE_MOTIONS)}"
        )
    return INVERSE_MOTIONS[normalized_name]
