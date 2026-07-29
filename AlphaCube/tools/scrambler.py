"""Create a legal random 3x3 scramble and save its 54-color JSON state."""

from __future__ import annotations

import argparse
import json
import random
import secrets
import sys
from pathlib import Path
from typing import Final

PROJECT_DIRECTORY: Final[Path] = Path(__file__).resolve().parents[1]
CORE_DIRECTORY: Final[Path] = PROJECT_DIRECTORY / "core"
DATA_DIRECTORY: Final[Path] = PROJECT_DIRECTORY / "data"
sys.path.insert(0, str(CORE_DIRECTORY))

from cube_3x3 import Cube3x3  # noqa: E402
from motion_database_3x3 import (  # noqa: E402
    INVERSE_MOVES,
    MOVE_FACES,
    MOVE_NAMES,
)


DEFAULT_OUTPUT: Final[Path] = DATA_DIRECTORY / "scrambled_state.json"


def read_move_count() -> int:
    while True:
        response = input("Number of scramble moves (1-100): ").strip()
        try:
            move_count = int(response)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if 1 <= move_count <= 100:
            return move_count
        print("Please enter a value from 1 through 100.")


def generate_scramble(
    move_count: int,
    seed: int,
) -> tuple[str, ...]:
    if not 1 <= move_count <= 100:
        raise ValueError("Scramble length must be from 1 through 100.")

    random_source = random.Random(seed)
    sequence: list[str] = []
    previous_face: str | None = None

    for _step in range(move_count):
        choices = [
            move
            for move in MOVE_NAMES
            if MOVE_FACES[move] != previous_face
        ]
        selected = random_source.choice(choices)
        sequence.append(selected)
        previous_face = MOVE_FACES[selected]

    return tuple(sequence)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a random 3x3 scramble.")
    parser.add_argument(
        "--moves",
        type=int,
        help="Number of random moves. If omitted, prompt in the terminal.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional repeatable random seed.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT}).",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    move_count = (
        arguments.moves if arguments.moves is not None else read_move_count()
    )
    if not 1 <= move_count <= 100:
        raise SystemExit("Error: --moves must be from 1 through 100.")

    seed = arguments.seed if arguments.seed is not None else secrets.randbits(64)
    sequence = generate_scramble(move_count, seed)
    cube = Cube3x3()
    cube.apply_sequence(sequence)

    output_path = arguments.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = cube.to_json_dict()
    data.update(
        {
            "format": "3x3-rubiks-cube-scramble",
            "seed": seed,
            "scramble_length": len(sequence),
            "scramble_sequence": list(sequence),
            "inverse_sequence": [
                INVERSE_MOVES[move] for move in reversed(sequence)
            ],
            "correct_movable_stickers": cube.correct_movable_stickers(),
        }
    )
    output_path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Seed:              {seed}")
    print(f"Scramble length:   {len(sequence)}")
    print("Scramble sequence: " + " ".join(sequence))
    print(
        "Correct stickers: "
        f"{cube.correct_movable_stickers()}/48 movable stickers"
    )
    print(f"Saved state:       {output_path}")


if __name__ == "__main__":
    main()
