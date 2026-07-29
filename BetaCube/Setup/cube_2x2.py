"""A sticker-based representation of the numbered 2x2 Rubik's Cube.

The cube contains 24 fixed positions. Each position stores one color value.
Motions copy colors between positions using the cycles in motion_database.py.
"""

from collections import Counter
from enum import IntEnum
from typing import Final, Iterable, Sequence

try:
    # Used when imported as: from Setup.cube_2x2 import Cube2x2
    from .motion_database import MOTIONS
except ImportError:
    # Used when run directly as: python3 Setup/cube_2x2.py
    from motion_database import MOTIONS


class Color(IntEnum):
    UNASSIGNED = 0
    WHITE = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    RED = 5
    ORANGE = 6


COLOR_SYMBOLS: Final[dict[int, str]] = {
    Color.UNASSIGNED: ".",
    Color.WHITE: "W",
    Color.GREEN: "G",
    Color.YELLOW: "Y",
    Color.BLUE: "B",
    Color.RED: "R",
    Color.ORANGE: "O",
}


FACE_POSITIONS: Final[dict[str, tuple[int, int, int, int]]] = {
    "front": (1, 2, 3, 4),
    "right": (5, 6, 7, 8),
    "back": (9, 10, 11, 12),
    "left": (13, 14, 15, 16),
    "top": (17, 18, 19, 20),
    "bottom": (21, 22, 23, 24),
}


# Index 0 is deliberately unused, allowing sticker[position] access.
SOLVED_STATE: Final[tuple[int, ...]] = (
    0,
    1, 1, 1, 1,  # Positions 1-4: white
    2, 2, 2, 2,  # Positions 5-8: green
    3, 3, 3, 3,  # Positions 9-12: yellow
    4, 4, 4, 4,  # Positions 13-16: blue
    5, 5, 5, 5,  # Positions 17-20: red
    6, 6, 6, 6,  # Positions 21-24: orange
)


# Fixed position layout from Resources/Net.png.
NET_POSITION_LAYOUT: Final[tuple[tuple[int | None, ...], ...]] = (
    (None, None, None, None, 17, 18, None, None),
    (None, None, None, None, 19, 20, None, None),
    (9, 10, 13, 14, 1, 2, 5, 6),
    (11, 12, 15, 16, 3, 4, 7, 8),
    (None, None, None, None, 21, 22, None, None),
    (None, None, None, None, 23, 24, None, None),
)


class Cube2x2:
    """Store colors at the 24 fixed cube-net positions."""

    def __init__(self, colors: Sequence[int] | None = None) -> None:
        self._stickers = self._normalize_colors(colors or SOLVED_STATE)

    @staticmethod
    def _normalize_colors(colors: Sequence[int]) -> list[int]:
        if len(colors) == 24:
            normalized = [0, *colors]
        elif len(colors) == 25:
            normalized = list(colors)
            normalized[0] = 0
        else:
            raise ValueError("A cube state must contain 24 color values.")

        for position in range(1, 25):
            Cube2x2._check_color(normalized[position])

        return normalized

    @staticmethod
    def _check_position(position: int) -> None:
        if not isinstance(position, int) or isinstance(position, bool):
            raise TypeError("Position must be an integer.")
        if position < 1 or position > 24:
            raise ValueError("Position must be between 1 and 24.")

    @staticmethod
    def _check_color(color: int) -> None:
        if not isinstance(color, int) or isinstance(color, bool):
            raise TypeError("Color must be an integer.")
        if color < Color.UNASSIGNED or color > Color.ORANGE:
            raise ValueError("Color must be between 0 and 6.")

    def get_color(self, position: int) -> int:
        """Return the color currently stored at a fixed position."""
        self._check_position(position)
        return self._stickers[position]

    def set_color(self, position: int, color: int) -> None:
        """Change the color at a fixed position."""
        self._check_position(position)
        self._check_color(color)
        self._stickers[position] = color

    def apply_motion(self, name: str) -> "Cube2x2":
        """Apply m1-m8 and return this cube for convenient chaining."""
        normalized_name = name.lower()
        if normalized_name not in MOTIONS:
            raise ValueError(
                f"Unknown motion {name!r}. Expected one of: "
                f"{', '.join(MOTIONS)}"
            )

        old_colors = self._stickers.copy()
        for cycle in MOTIONS[normalized_name]:
            for index, source in enumerate(cycle):
                destination = cycle[(index + 1) % len(cycle)]
                self._stickers[destination] = old_colors[source]

        return self

    def apply_sequence(self, motions: str | Iterable[str]) -> "Cube2x2":
        """Apply motion names from a string or iterable.

        Examples:
            cube.apply_sequence("m1 m5 m2")
            cube.apply_sequence(["m1", "m5", "m2"])
        """
        names = motions.split() if isinstance(motions, str) else motions
        for name in names:
            self.apply_motion(name)
        return self

    def reset(self) -> None:
        """Restore the original solved color arrangement."""
        self._stickers = list(SOLVED_STATE)

    def copy(self) -> "Cube2x2":
        """Return an independent copy of the cube."""
        return Cube2x2(self._stickers)

    def as_list(self) -> list[int]:
        """Return the 24 colors in position order, from 1 through 24."""
        return self._stickers[1:].copy()

    def as_pairs(self) -> list[tuple[int, int]]:
        """Return every sticker as a (position, color) pair."""
        return [(position, self._stickers[position]) for position in range(1, 25)]

    def as_net(self) -> list[list[int | None]]:
        """Return the colors arranged like the numbered cube-net image."""
        return [
            [
                None if position is None else self._stickers[position]
                for position in row
            ]
            for row in NET_POSITION_LAYOUT
        ]

    def has_valid_color_counts(self, allow_unassigned: bool = False) -> bool:
        """Check that each of the six colors occurs exactly four times."""
        counts = Counter(self._stickers[1:])
        if allow_unassigned:
            return all(counts[color] <= 4 for color in range(1, 7))
        return counts[Color.UNASSIGNED] == 0 and all(
            counts[color] == 4 for color in range(1, 7)
        )

    def is_solved(self) -> bool:
        """Return True when every face contains four matching colors."""
        for positions in FACE_POSITIONS.values():
            face_colors = {self._stickers[position] for position in positions}
            if len(face_colors) != 1 or Color.UNASSIGNED in face_colors:
                return False
        return True

    def __str__(self) -> str:
        """Draw a compact text version of the cube net."""
        rows: list[str] = []
        for row in self.as_net():
            cells = [
                " " if color is None else COLOR_SYMBOLS[color]
                for color in row
            ]
            rows.append(" ".join(cells).rstrip())
        return "\n".join(rows)


if __name__ == "__main__":
    cube = Cube2x2()
    print("Solved cube:")
    print(cube)

    cube.apply_motion("m1")
    print("\nAfter m1:")
    print(cube)
