"""Solve a 3x3 with color-value beam search and an exact depth-5 finish.

At each forward depth, every retained state is expanded using the 18
standard moves (with redundant consecutive same-face moves omitted).
Every generated state is checked against the reverse BFS database before
heuristic pruning. If no database intersection is found, the highest-valued
states are retained for the next forward depth.

The state value is the number of movable facelets matching the solved cube,
from 0 through 48. This heuristic is experimental and does not guarantee
that the forward beam will reach the exact database.
"""

from __future__ import annotations

import argparse
import heapq
import json
import pickle
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

PROJECT_DIRECTORY: Final[Path] = Path(__file__).resolve().parents[1]
CORE_DIRECTORY: Final[Path] = PROJECT_DIRECTORY / "core"
DATA_DIRECTORY: Final[Path] = PROJECT_DIRECTORY / "data"
sys.path.insert(0, str(CORE_DIRECTORY))

from cube_3x3 import (  # noqa: E402
    SOLVED_STATE,
    colors_from_json,
    correct_movable_stickers,
)
from generate_depth5_database import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_DATABASE,
    load_database,
    unpack_entry,
)
from motion_database_3x3 import (  # noqa: E402
    INVERSE_MOVES,
    MOVE_FACES,
    MOVE_NAMES,
    MOVE_PERMUTATIONS,
    apply_permutation,
)


CubeState = bytes
MovePath = tuple[str, ...]
DEFAULT_STATE: Final[Path] = DATA_DIRECTORY / "scrambled_state.json"


@dataclass(frozen=True)
class SearchResult:
    solution: MovePath | None
    forward_depth: int
    database_suffix_length: int | None
    states_evaluated: int
    best_value: int
    elapsed_seconds: float


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="3x3 beam search with an exact depth-5 database finish."
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE,
        help=f"Scrambled JSON state (default: {DEFAULT_STATE}).",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"Reverse BFS database (default: {DEFAULT_DATABASE}).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=30,
        help="Maximum forward beam depth (default: 30).",
    )
    parser.add_argument(
        "--beam-width",
        type=int,
        default=10_000,
        help="Highest-valued states retained per depth (default: 10000).",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Use the recorded inverse scramble if beam search fails.",
    )
    return parser.parse_args()


def apply_sequence(state: CubeState, sequence: MovePath) -> CubeState:
    current = state
    for move in sequence:
        current = apply_permutation(current, MOVE_PERMUTATIONS[move])
    return current


def database_solution(
    state: CubeState,
    entries: dict[bytes, int],
) -> MovePath | None:
    """Return the exact stored suffix, or None when state is not stored."""
    first_entry = entries.get(state)
    if first_entry is None:
        return None

    path: list[str] = []
    current_state = state
    current_entry = first_entry

    while True:
        distance, move = unpack_entry(current_entry)
        if distance == 0:
            if current_state != SOLVED_STATE:
                raise RuntimeError("Database distance 0 is not the solved state.")
            return tuple(path)
        if move is None:
            raise RuntimeError("A non-solved database state has no solution move.")

        next_state = apply_permutation(
            current_state,
            MOVE_PERMUTATIONS[move],
        )
        next_entry = entries.get(next_state)
        if next_entry is None:
            raise RuntimeError("Database solution pointer leaves the database.")
        next_distance, _next_move = unpack_entry(next_entry)
        if next_distance != distance - 1:
            raise RuntimeError("Database solution pointer has an invalid distance.")

        path.append(move)
        current_state = next_state
        current_entry = next_entry


def beam_search(
    scrambled_state: CubeState,
    entries: dict[bytes, int],
    maximum_depth: int,
    beam_width: int,
    show_progress: bool = True,
) -> SearchResult:
    if maximum_depth < 0:
        raise ValueError("Maximum depth cannot be negative.")
    if beam_width <= 0:
        raise ValueError("Beam width must be greater than zero.")

    started_at = time.perf_counter()
    initial_value = correct_movable_stickers(scrambled_state)
    initial_suffix = database_solution(scrambled_state, entries)
    if initial_suffix is not None:
        return SearchResult(
            solution=initial_suffix,
            forward_depth=0,
            database_suffix_length=len(initial_suffix),
            states_evaluated=1,
            best_value=48,
            elapsed_seconds=time.perf_counter() - started_at,
        )

    frontier: dict[CubeState, MovePath] = {scrambled_state: ()}
    retained_states: set[CubeState] = {scrambled_state}
    states_evaluated = 1
    best_value = initial_value

    for depth in range(1, maximum_depth + 1):
        candidates: dict[CubeState, MovePath] = {}

        for state, path in frontier.items():
            forbidden_face = MOVE_FACES[path[-1]] if path else None
            for move in MOVE_NAMES:
                if MOVE_FACES[move] == forbidden_face:
                    continue

                next_state = apply_permutation(
                    state,
                    MOVE_PERMUTATIONS[move],
                )
                if next_state in retained_states or next_state in candidates:
                    continue

                next_path = (*path, move)
                states_evaluated += 1

                # Check the exact goal-side database before heuristic pruning.
                suffix = database_solution(next_state, entries)
                if suffix is not None:
                    solution = (*next_path, *suffix)
                    if show_progress:
                        print(
                            f"Depth {depth:>2}: database intersection found; "
                            f"exact suffix length {len(suffix)}."
                        )
                    return SearchResult(
                        solution=solution,
                        forward_depth=depth,
                        database_suffix_length=len(suffix),
                        states_evaluated=states_evaluated,
                        best_value=48,
                        elapsed_seconds=time.perf_counter() - started_at,
                    )

                value = correct_movable_stickers(next_state)
                best_value = max(best_value, value)
                candidates[next_state] = next_path

        if not candidates:
            break

        retained = heapq.nlargest(
            beam_width,
            candidates.items(),
            key=lambda item: correct_movable_stickers(item[0]),
        )
        frontier = dict(retained)
        retained_states.update(frontier)
        frontier_best = max(
            correct_movable_stickers(state) for state in frontier
        )

        if show_progress:
            print(
                f"Depth {depth:>2}: generated {len(candidates):>8,}, "
                f"kept {len(frontier):>6,}, "
                f"best value {frontier_best}/48"
            )

    return SearchResult(
        solution=None,
        forward_depth=maximum_depth,
        database_suffix_length=None,
        states_evaluated=states_evaluated,
        best_value=best_value,
        elapsed_seconds=time.perf_counter() - started_at,
    )


def inverse_recorded_scramble(data: Any) -> MovePath | None:
    if not isinstance(data, dict):
        return None
    sequence = data.get("scramble_sequence")
    if (
        not isinstance(sequence, list)
        or not all(isinstance(move, str) and move in MOVE_NAMES for move in sequence)
    ):
        return None
    return tuple(INVERSE_MOVES[move] for move in reversed(sequence))


def print_verified_solution(
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
    state_path = arguments.state.expanduser().resolve()
    database_path = arguments.database.expanduser().resolve()

    try:
        with state_path.open("r", encoding="utf-8") as state_file:
            state_data = json.load(state_file)
        scrambled_state = colors_from_json(state_data)
        database_payload = load_database(database_path)
        entries = database_payload["entries"]
    except (
        OSError,
        EOFError,
        pickle.UnpicklingError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Loaded state:       {state_path}")
    print(f"Loaded database:    {database_path}")
    print(f"Database states:    {len(entries):,}")
    print(f"Database depth:     {database_payload['maximum_depth']}")
    print(
        "Initial value:      "
        f"{correct_movable_stickers(scrambled_state)}/48"
    )
    print(f"Beam width:         {arguments.beam_width:,}")
    print(f"Maximum depth:      {arguments.depth}")
    print()

    try:
        result = beam_search(
            scrambled_state,
            entries,
            arguments.depth,
            arguments.beam_width,
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    if result.solution is not None:
        print_verified_solution(
            scrambled_state,
            result.solution,
            "Beam/database search succeeded.",
        )
        print(f"Forward depth:      {result.forward_depth}")
        print(
            "Database suffix:    "
            f"{result.database_suffix_length} move(s)"
        )
        print(f"States evaluated:   {result.states_evaluated:,}")
        print(f"Search time:        {result.elapsed_seconds:.3f} seconds")
        return

    print()
    print("Beam/database search did not find a solution.")
    print(f"Forward depth:      {result.forward_depth}")
    print(f"Best value reached: {result.best_value}/48")
    print(f"States evaluated:   {result.states_evaluated:,}")
    print(f"Search time:        {result.elapsed_seconds:.3f} seconds")

    fallback = inverse_recorded_scramble(state_data)
    if fallback is not None and arguments.fallback:
        print_verified_solution(
            scrambled_state,
            fallback,
            "Recorded inverse scramble fallback:",
        )
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
