"""Core fixed-position, 54-facelet representation of a 3x3 Rubik's Cube."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Final, Iterable

from motion_database_3x3 import (
    FACE_ORDER,
    MOVE_NAMES,
    MOVE_PERMUTATIONS,
    apply_permutation,
)


COLOR_NAMES: Final[dict[int, str]] = {
    1: "white",
    2: "green",
    3: "yellow",
    4: "blue",
    5: "red",
    6: "orange",
}
FACE_COLORS: Final[dict[str, int]] = dict(zip(FACE_ORDER, range(1, 7)))
SOLVED_STATE: Final[bytes] = bytes(
    color
    for color in range(1, 7)
    for _position in range(9)
)
CENTER_INDICES: Final[frozenset[int]] = frozenset(
    face_index * 9 + 4 for face_index in range(6)
)
MOVABLE_INDICES: Final[tuple[int, ...]] = tuple(
    index for index in range(54) if index not in CENTER_INDICES
)


def validate_state(state: bytes | bytearray | Iterable[int]) -> bytes:
    colors = bytes(state)
    if len(colors) != 54:
        raise ValueError("A 3x3 cube state must contain exactly 54 colors.")
    counts = Counter(colors)
    if any(counts.get(color, 0) != 9 for color in range(1, 7)):
        raise ValueError("A state must contain exactly nine of each color.")
    if any(color not in COLOR_NAMES for color in colors):
        raise ValueError("Every color must be an integer from 1 through 6.")
    for face_index, expected_color in enumerate(range(1, 7)):
        if colors[face_index * 9 + 4] != expected_color:
            raise ValueError(
                "Center colors must remain fixed in F, R, B, L, U, D order."
            )
    return colors


def colors_from_json(data: Any) -> bytes:
    if isinstance(data, list):
        colors = data
    elif isinstance(data, dict) and "colors" in data:
        colors = data["colors"]
    elif isinstance(data, dict) and "stickers" in data:
        stickers = data["stickers"]
        if not isinstance(stickers, list):
            raise ValueError("'stickers' must be a list.")
        by_position: list[int | None] = [None] * 54
        for sticker in stickers:
            if not isinstance(sticker, dict):
                raise ValueError("Every sticker must be a JSON object.")
            position = sticker.get("position")
            color = sticker.get("color")
            if (
                not isinstance(position, int)
                or isinstance(position, bool)
                or not 1 <= position <= 54
            ):
                raise ValueError("Sticker positions must be from 1 through 54.")
            if by_position[position - 1] is not None:
                raise ValueError(f"Position {position} occurs more than once.")
            by_position[position - 1] = color
        if any(color is None for color in by_position):
            raise ValueError("The JSON must contain all 54 positions.")
        colors = by_position
    else:
        raise ValueError(
            "Expected a list or a JSON object containing 'colors' or 'stickers'."
        )

    if not isinstance(colors, list):
        raise ValueError("Cube colors must be provided as a list.")
    if any(
        not isinstance(color, int) or isinstance(color, bool)
        for color in colors
    ):
        raise ValueError("Every color must be an integer.")
    return validate_state(colors)


def correct_movable_stickers(state: bytes) -> int:
    return sum(
        state[index] == SOLVED_STATE[index]
        for index in MOVABLE_INDICES
    )


class Cube3x3:
    def __init__(self, state: bytes | Iterable[int] = SOLVED_STATE) -> None:
        self.state = validate_state(state)

    def copy(self) -> "Cube3x3":
        return Cube3x3(self.state)

    def reset(self) -> None:
        self.state = SOLVED_STATE

    def apply_move(self, move: str) -> None:
        try:
            permutation = MOVE_PERMUTATIONS[move]
        except KeyError as error:
            raise ValueError(
                f"Unknown move {move!r}. Expected one of: "
                + ", ".join(MOVE_NAMES)
            ) from error
        self.state = apply_permutation(self.state, permutation)

    def apply_sequence(self, sequence: Iterable[str]) -> None:
        for move in sequence:
            self.apply_move(move)

    def is_solved(self) -> bool:
        return self.state == SOLVED_STATE

    def correct_movable_stickers(self) -> int:
        return correct_movable_stickers(self.state)

    def as_list(self) -> list[int]:
        return list(self.state)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "format": "3x3-rubiks-cube-state",
            "version": 1,
            "face_order": list(FACE_ORDER),
            "colors": self.as_list(),
            "stickers": [
                {"position": index + 1, "color": color}
                for index, color in enumerate(self.state)
            ],
        }

    def save_json(self, path: str | Path) -> Path:
        output_path = Path(path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_json_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path

    @classmethod
    def load_json(cls, path: str | Path) -> "Cube3x3":
        input_path = Path(path).expanduser().resolve()
        data = json.loads(input_path.read_text(encoding="utf-8"))
        return cls(colors_from_json(data))

    def net_text(self) -> str:
        faces = {
            face: [
                list(self.state[offset + row * 3 : offset + row * 3 + 3])
                for row in range(3)
            ]
            for face_index, face in enumerate(FACE_ORDER)
            for offset in (face_index * 9,)
        }

        lines: list[str] = []
        for row in faces["U"]:
            lines.append("       " + " ".join(map(str, row)))
        for row_index in range(3):
            lines.append(
                "  ".join(
                    " ".join(map(str, faces[face][row_index]))
                    for face in ("L", "F", "R", "B")
                )
            )
        for row in faces["D"]:
            lines.append("       " + " ".join(map(str, row)))
        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the 3x3 cube model.")
    parser.add_argument("moves", nargs="*", help="Moves such as R U R' U'.")
    parser.add_argument("--load", type=Path, help="Optional JSON state to load.")
    parser.add_argument("--save", type=Path, help="Optional JSON output path.")
    arguments = parser.parse_args()

    cube = (
        Cube3x3.load_json(arguments.load)
        if arguments.load
        else Cube3x3()
    )
    cube.apply_sequence(arguments.moves)
    print(cube.net_text())
    print()
    print(f"Correct movable stickers: {cube.correct_movable_stickers()}/48")
    print(f"Solved: {cube.is_solved()}")
    if arguments.save:
        print(f"Saved: {cube.save_json(arguments.save)}")


if __name__ == "__main__":
    main()
