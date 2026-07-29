"""Experimental beam-search solver guided by correct sticker positions.

Run after scrambler.py:

    python3 test/color_evaluation_solver.py

The search branches through m1-m8, keeps a configurable number of the
highest-valued states at each depth, and defines value as the number of
stickers matching the canonical solved cube.

This heuristic is not guaranteed to find a solution. If the input was made
by scrambler.py and heuristic search fails, the recorded scramble can be
inverted as a clearly identified fallback solution.
"""

from __future__ import annotations

import argparse
import heapq
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SETUP_DIRECTORY: Final[Path] = PROJECT_ROOT / "Setup"
DEFAULT_STATE: Final[Path] = Path(__file__).resolve().parent / "scrambled_state.json"

sys.path.insert(0, str(SETUP_DIRECTORY))

from cube_2x2 import Cube2x2  # noqa: E402
from motion_database import INVERSE_MOTIONS, MOTIONS, MotionCycles  # noqa: E402


CubeState = tuple[int, ...]
MovePath = tuple[str, ...]
SOLVED_STATE: Final[CubeState] = tuple(Cube2x2().as_list())
MOVE_NAMES: Final[tuple[str, ...]] = tuple(MOTIONS)


@dataclass(frozen=True)
class SearchResult:
    solution: MovePath | None
    depths_completed: int
    states_evaluated: int
    best_correct_stickers: int
    elapsed_seconds: float


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find a solution using depth-limited correct-sticker beam search."
        )
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE,
        help=f"Scrambled JSON state (default: {DEFAULT_STATE}).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=20,
        help="Maximum branching depth (default: 20).",
    )
    parser.add_argument(
        "--beam-width",
        type=int,
        default=10_000,
        help="Highest-valued states retained at each depth (default: 10000).",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Do not use the recorded inverse scramble if beam search fails.",
    )
    return parser.parse_args()


def apply_motion(state: CubeState, cycles: MotionCycles) -> CubeState:
    result = list(state)
    for cycle in cycles:
        for index, source_position in enumerate(cycle):
            destination_position = cycle[(index + 1) % len(cycle)]
            result[destination_position - 1] = state[source_position - 1]
    return tuple(result)


def apply_sequence(state: CubeState, sequence: MovePath) -> CubeState:
    result = state
    for motion in sequence:
        result = apply_motion(result, MOTIONS[motion])
    return result


def correct_sticker_count(state: CubeState) -> int:
    """Return a deterministic value from 0 through 24."""
    return sum(
        current == solved
        for current, solved in zip(state, SOLVED_STATE)
    )


def colors_from_json(data: Any) -> CubeState:
    if isinstance(data, list):
        colors = data
    elif isinstance(data, dict) and "colors" in data:
        colors = data["colors"]
    elif isinstance(data, dict) and "stickers" in data:
        stickers = data["stickers"]
        if not isinstance(stickers, list):
            raise ValueError("'stickers' must be a list.")

        by_position: list[int | None] = [None] * 24
        for sticker in stickers:
            if not isinstance(sticker, dict):
                raise ValueError("Every sticker must be a JSON object.")
            position = sticker.get("position")
            color = sticker.get("color")
            if (
                not isinstance(position, int)
                or isinstance(position, bool)
                or position < 1
                or position > 24
            ):
                raise ValueError("Sticker positions must be from 1 through 24.")
            if by_position[position - 1] is not None:
                raise ValueError(f"Position {position} occurs more than once.")
            by_position[position - 1] = color

        if any(color is None for color in by_position):
            raise ValueError("The JSON must contain all 24 positions.")
        colors = by_position
    else:
        raise ValueError(
            "Expected a JSON object containing 'stickers' or 'colors'."
        )

    if not isinstance(colors, list) or len(colors) != 24:
        raise ValueError("The state must contain exactly 24 colors.")
    if any(
        not isinstance(color, int)
        or isinstance(color, bool)
        or color < 1
        or color > 6
        for color in colors
    ):
        raise ValueError("Every color must be an integer from 1 through 6.")
    if any(colors.count(color) != 4 for color in range(1, 7)):
        raise ValueError("The state must contain four of each color.")
    return tuple(colors)


def beam_search(
    scrambled_state: CubeState,
    maximum_depth: int,
    beam_width: int,
    show_progress: bool = True,
) -> SearchResult:
    if maximum_depth < 0:
        raise ValueError("Maximum depth cannot be negative.")
    if beam_width <= 0:
        raise ValueError("Beam width must be greater than zero.")

    started_at = time.perf_counter()
    initial_score = correct_sticker_count(scrambled_state)
    if scrambled_state == SOLVED_STATE:
        return SearchResult(
            solution=(),
            depths_completed=0,
            states_evaluated=1,
            best_correct_stickers=24,
            elapsed_seconds=time.perf_counter() - started_at,
        )

    frontier: dict[CubeState, MovePath] = {scrambled_state: ()}
    retained_states: set[CubeState] = {scrambled_state}
    states_evaluated = 1
    best_score = initial_score

    for depth in range(1, maximum_depth + 1):
        candidates: dict[CubeState, MovePath] = {}

        for state, path in frontier.items():
            forbidden_inverse = (
                INVERSE_MOTIONS[path[-1]] if path else None
            )
            for motion in MOVE_NAMES:
                if motion == forbidden_inverse:
                    continue

                next_state = apply_motion(state, MOTIONS[motion])
                if next_state in retained_states or next_state in candidates:
                    continue

                next_path = (*path, motion)
                states_evaluated += 1
                score = correct_sticker_count(next_state)
                best_score = max(best_score, score)

                if next_state == SOLVED_STATE:
                    elapsed = time.perf_counter() - started_at
                    if show_progress:
                        print(
                            f"Depth {depth:>2}: solution found with "
                            f"{states_evaluated:,} states evaluated."
                        )
                    return SearchResult(
                        solution=next_path,
                        depths_completed=depth,
                        states_evaluated=states_evaluated,
                        best_correct_stickers=24,
                        elapsed_seconds=elapsed,
                    )

                candidates[next_state] = next_path

        if not candidates:
            break

        retained = heapq.nlargest(
            beam_width,
            candidates.items(),
            key=lambda item: correct_sticker_count(item[0]),
        )
        frontier = dict(retained)
        retained_states.update(frontier)

        if show_progress:
            frontier_best = max(
                correct_sticker_count(state) for state in frontier
            )
            print(
                f"Depth {depth:>2}: generated {len(candidates):>7,}, "
                f"kept {len(frontier):>6,}, "
                f"best value {frontier_best}/24"
            )

    return SearchResult(
        solution=None,
        depths_completed=maximum_depth,
        states_evaluated=states_evaluated,
        best_correct_stickers=best_score,
        elapsed_seconds=time.perf_counter() - started_at,
    )


def inverse_scramble(data: Any) -> MovePath | None:
    if not isinstance(data, dict):
        return None
    sequence = data.get("scramble_sequence")
    if (
        not isinstance(sequence, list)
        or not all(isinstance(move, str) and move in MOTIONS for move in sequence)
    ):
        return None
    return tuple(INVERSE_MOTIONS[move] for move in reversed(sequence))


def print_solution(
    scrambled_state: CubeState,
    solution: MovePath,
    label: str,
) -> None:
    final_state = apply_sequence(scrambled_state, solution)
    if final_state != SOLVED_STATE:
        raise RuntimeError("The reported solution failed verification.")

    print()
    print(label)
    print(f"Solution length:   {len(solution)}")
    print(
        "Solution sequence: "
        + (" ".join(solution) if solution else "(already solved)")
    )
    print("Verification:      solved")


def main() -> None:
    arguments = parse_arguments()
    if arguments.depth < 0:
        print("Error: depth cannot be negative.", file=sys.stderr)
        raise SystemExit(1)
    if arguments.beam_width <= 0:
        print("Error: beam width must be greater than zero.", file=sys.stderr)
        raise SystemExit(1)

    state_path = arguments.state.expanduser().resolve()
    try:
        with state_path.open("r", encoding="utf-8") as state_file:
            data = json.load(state_file)
        scrambled_state = colors_from_json(data)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Loaded state:       {state_path}")
    print(f"Initial value:      {correct_sticker_count(scrambled_state)}/24")
    print(f"Maximum depth:      {arguments.depth}")
    print(f"Beam width:         {arguments.beam_width:,}")
    print()

    result = beam_search(
        scrambled_state,
        maximum_depth=arguments.depth,
        beam_width=arguments.beam_width,
    )

    if result.solution is not None:
        print_solution(
            scrambled_state,
            result.solution,
            "Color-evaluation search succeeded.",
        )
        print(f"States evaluated:   {result.states_evaluated:,}")
        print(f"Search time:        {result.elapsed_seconds:.3f} seconds")
        return

    print()
    print("Color-evaluation search did not find a solution.")
    print(f"Depths completed:   {result.depths_completed}")
    print(f"States evaluated:   {result.states_evaluated:,}")
    print(f"Best value reached: {result.best_correct_stickers}/24")
    print(f"Search time:        {result.elapsed_seconds:.3f} seconds")

    fallback = inverse_scramble(data)
    if fallback is not None and not arguments.no_fallback:
        print_solution(
            scrambled_state,
            fallback,
            "Using the recorded inverse scramble as a guaranteed fallback.",
        )
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
