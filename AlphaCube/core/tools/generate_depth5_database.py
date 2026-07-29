"""Generate an exact reverse-BFS 3x3 solution database through depth 5.

Every database entry stores its exact distance and one move that reaches
the previous BFS layer. Repeated lookups therefore provide a guaranteed
shortest sequence from any stored state to the solved cube.
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Final

PROJECT_DIRECTORY: Final[Path] = Path(__file__).resolve().parents[1]
CORE_DIRECTORY: Final[Path] = PROJECT_DIRECTORY / "core"
DATA_DIRECTORY: Final[Path] = PROJECT_DIRECTORY / "data"
sys.path.insert(0, str(CORE_DIRECTORY))

from cube_3x3 import SOLVED_STATE  # noqa: E402
from motion_database_3x3 import (  # noqa: E402
    INDEX_TO_MOVE,
    INVERSE_MOVES,
    MOVE_NAMES,
    MOVE_PERMUTATIONS,
    MOVE_TO_INDEX,
    apply_permutation,
)


DEFAULT_OUTPUT: Final[Path] = DATA_DIRECTORY / "depth5_database.pkl"
DATABASE_FORMAT: Final[str] = "3x3-reverse-bfs-next-move"
DATABASE_VERSION: Final[int] = 1
MOVE_BITS: Final[int] = 5
MOVE_MASK: Final[int] = (1 << MOVE_BITS) - 1
NO_MOVE: Final[int] = MOVE_MASK
EXPECTED_EXACT_LAYER_COUNTS: Final[dict[int, int]] = {
    0: 1,
    1: 18,
    2: 243,
    3: 3_240,
    4: 43_239,
    5: 574_908,
}


def pack_entry(distance: int, solution_move: str | None) -> int:
    move_index = NO_MOVE if solution_move is None else MOVE_TO_INDEX[solution_move]
    return (distance << MOVE_BITS) | move_index


def unpack_entry(entry: int) -> tuple[int, str | None]:
    distance = entry >> MOVE_BITS
    move_index = entry & MOVE_MASK
    move = None if move_index == NO_MOVE else INDEX_TO_MOVE[move_index]
    return distance, move


def build_database(
    maximum_depth: int = 5,
    show_progress: bool = True,
) -> tuple[dict[bytes, int], list[int]]:
    if not 0 <= maximum_depth <= 5:
        raise ValueError("This generator supports depths from 0 through 5.")

    entries: dict[bytes, int] = {
        SOLVED_STATE: pack_entry(0, None),
    }
    frontier: list[bytes] = [SOLVED_STATE]
    layer_counts = [1]

    for depth in range(1, maximum_depth + 1):
        started_at = time.perf_counter()
        next_frontier: list[bytes] = []

        for state in frontier:
            for move in MOVE_NAMES:
                next_state = apply_permutation(
                    state,
                    MOVE_PERMUTATIONS[move],
                )
                if next_state in entries:
                    continue
                entries[next_state] = pack_entry(
                    depth,
                    INVERSE_MOVES[move],
                )
                next_frontier.append(next_state)

        expected_count = EXPECTED_EXACT_LAYER_COUNTS[depth]
        if len(next_frontier) != expected_count:
            raise RuntimeError(
                f"Depth {depth} produced {len(next_frontier):,} states; "
                f"expected {expected_count:,}. Check the move permutations."
            )

        layer_counts.append(len(next_frontier))
        frontier = next_frontier
        if show_progress:
            print(
                f"Depth {depth}: {len(frontier):>9,} new states, "
                f"{len(entries):>9,} cumulative, "
                f"{time.perf_counter() - started_at:.3f} seconds"
            )

    return entries, layer_counts


def save_database(
    output_path: Path,
    entries: dict[bytes, int],
    layer_counts: list[int],
) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": DATABASE_FORMAT,
        "version": DATABASE_VERSION,
        "maximum_depth": len(layer_counts) - 1,
        "move_names": MOVE_NAMES,
        "solved_state": SOLVED_STATE,
        "layer_counts": tuple(layer_counts),
        "entries": entries,
    }

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output_path.parent,
            prefix=output_path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_name = temporary_file.name
            pickle.dump(payload, temporary_file, protocol=pickle.HIGHEST_PROTOCOL)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        Path(temporary_name).replace(output_path)
    finally:
        if temporary_name is not None:
            temporary_path = Path(temporary_name)
            if temporary_path.exists():
                temporary_path.unlink()
    return output_path


def load_database(path: str | Path) -> dict[str, Any]:
    database_path = Path(path).expanduser().resolve()
    with database_path.open("rb") as database_file:
        payload = pickle.load(database_file)
    if not isinstance(payload, dict):
        raise ValueError("Database payload must be a dictionary.")
    if payload.get("format") != DATABASE_FORMAT:
        raise ValueError("Database format is not recognized.")
    if payload.get("version") != DATABASE_VERSION:
        raise ValueError("Database version is not supported.")
    if tuple(payload.get("move_names", ())) != MOVE_NAMES:
        raise ValueError("Database move order does not match this program.")
    if payload.get("solved_state") != SOLVED_STATE:
        raise ValueError("Database solved state does not match this program.")
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("Database entries are missing or invalid.")
    return payload


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the exact 3x3 reverse-BFS database."
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=5,
        help="Maximum BFS depth from 0 through 5 (default: 5).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Database output path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output database.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    output_path = arguments.output.expanduser().resolve()
    if output_path.exists() and not arguments.force:
        raise SystemExit(
            f"Error: database already exists: {output_path}\n"
            "Use --force to regenerate it."
        )

    started_at = time.perf_counter()
    entries, layer_counts = build_database(arguments.depth)
    saved_path = save_database(output_path, entries, layer_counts)
    file_size = saved_path.stat().st_size

    print()
    print(f"Saved database:    {saved_path}")
    print(f"Maximum depth:     {arguments.depth}")
    print(f"Total states:      {len(entries):,}")
    print(f"File size:         {file_size / (1024 * 1024):.2f} MiB")
    print(f"Total time:        {time.perf_counter() - started_at:.3f} seconds")


if __name__ == "__main__":
    main()
