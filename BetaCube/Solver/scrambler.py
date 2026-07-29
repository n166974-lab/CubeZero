"""Create a reproducible 2x2 cube scramble of 1 to 40 motions.

Run from the project root:

    python3 test/scrambler.py

The resulting state is saved to test/scrambled_state.json for use by
color_evaluation_solver.py.
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import sys
from pathlib import Path
from typing import Final


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SETUP_DIRECTORY: Final[Path] = PROJECT_ROOT / "Setup"
DEFAULT_OUTPUT: Final[Path] = Path(__file__).resolve().parent / "scrambled_state.json"
MAXIMUM_SCRAMBLE_LENGTH: Final[int] = 40

sys.path.insert(0, str(SETUP_DIRECTORY))

from cube_2x2 import Cube2x2, SOLVED_STATE  # noqa: E402
from motion_database import INVERSE_MOTIONS, MOTIONS  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scramble the 2x2 cube with up to 40 random motions."
    )
    parser.add_argument(
        "--moves",
        type=int,
        help="Number of scramble motions from 1 through 40.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional seed. The generated JSON always records the actual seed.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSON output path (default: {DEFAULT_OUTPUT}).",
    )
    return parser.parse_args()


def request_move_count(provided_count: int | None) -> int:
    if provided_count is not None:
        move_count = provided_count
    else:
        while True:
            raw_value = input("How many scramble motions (1-40)? ").strip()
            try:
                move_count = int(raw_value)
            except ValueError:
                print("Please enter a whole number from 1 through 40.")
                continue
            if 1 <= move_count <= MAXIMUM_SCRAMBLE_LENGTH:
                break
            print("Please enter a whole number from 1 through 40.")

    if move_count < 1 or move_count > MAXIMUM_SCRAMBLE_LENGTH:
        raise ValueError("Scramble motions must be from 1 through 40.")
    return move_count


def correct_sticker_count(colors: list[int]) -> int:
    return sum(
        current == solved
        for current, solved in zip(colors, SOLVED_STATE[1:])
    )


def create_scramble(
    move_count: int,
    seed: int,
) -> tuple[Cube2x2, list[str]]:
    random_source = random.Random(seed)
    cube = Cube2x2()
    sequence: list[str] = []

    for _ in range(move_count):
        choices = list(MOTIONS)
        if sequence:
            # An immediate inverse would cancel the preceding scramble move.
            inverse = INVERSE_MOTIONS[sequence[-1]]
            choices.remove(inverse)

        motion = random_source.choice(choices)
        cube.apply_motion(motion)
        sequence.append(motion)

    return cube, sequence


def save_scramble(
    output_path: Path,
    cube: Cube2x2,
    sequence: list[str],
    seed: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "format": "2x2-rubiks-cube-scramble",
        "version": 1,
        "seed": seed,
        "scramble_length": len(sequence),
        "scramble_sequence": sequence,
        "correct_stickers": correct_sticker_count(cube.as_list()),
        "stickers": [
            {"position": position, "color": color}
            for position, color in cube.as_pairs()
        ],
    }

    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as output_file:
            json.dump(data, output_file, indent=2)
            output_file.write("\n")
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    arguments = parse_arguments()
    try:
        move_count = request_move_count(arguments.moves)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    seed = arguments.seed if arguments.seed is not None else secrets.randbits(64)
    cube, sequence = create_scramble(move_count, seed)
    output_path = arguments.output.expanduser().resolve()
    save_scramble(output_path, cube, sequence, seed)

    correct = correct_sticker_count(cube.as_list())
    print()
    print(f"Seed:              {seed}")
    print(f"Scramble length:   {move_count}")
    print(f"Scramble sequence: {' '.join(sequence)}")
    print(f"Correct stickers:  {correct}/24")
    print(f"Saved state:       {output_path}")


if __name__ == "__main__":
    main()
