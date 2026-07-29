"""Core facelet permutations for all 18 standard 3x3 moves.

The face order is F, R, B, L, U, D. Within each face, positions are stored
row by row as viewed directly from outside that face.

Each permutation uses ``result[destination] = state[source]``. The
permutations are generated from integer 3D coordinates, which keeps all
adjacent strips consistent without manually maintained sticker cycles.
"""

from __future__ import annotations

from typing import Final, TypeAlias


Vector: TypeAlias = tuple[int, int, int]
Permutation: TypeAlias = tuple[int, ...]

FACE_ORDER: Final[tuple[str, ...]] = ("F", "R", "B", "L", "U", "D")
FACE_NORMALS: Final[dict[str, Vector]] = {
    "F": (0, 0, 1),
    "R": (1, 0, 0),
    "B": (0, 0, -1),
    "L": (-1, 0, 0),
    "U": (0, 1, 0),
    "D": (0, -1, 0),
}


def _facelet_coordinate(face: str, row: int, column: int) -> Vector:
    """Return the cubical coordinate for one outward-facing sticker."""
    if face == "F":
        return column - 1, 1 - row, 1
    if face == "R":
        return 1, 1 - row, 1 - column
    if face == "B":
        return 1 - column, 1 - row, -1
    if face == "L":
        return -1, 1 - row, column - 1
    if face == "U":
        return column - 1, 1, row - 1
    if face == "D":
        return column - 1, -1, 1 - row
    raise ValueError(f"Unknown face: {face}")


FACELET_DESCRIPTORS: Final[tuple[tuple[Vector, Vector], ...]] = tuple(
    (
        _facelet_coordinate(face, row, column),
        FACE_NORMALS[face],
    )
    for face in FACE_ORDER
    for row in range(3)
    for column in range(3)
)
_DESCRIPTOR_TO_INDEX: Final[dict[tuple[Vector, Vector], int]] = {
    descriptor: index
    for index, descriptor in enumerate(FACELET_DESCRIPTORS)
}


def _dot(left: Vector, right: Vector) -> int:
    return sum(a * b for a, b in zip(left, right))


def _cross(left: Vector, right: Vector) -> Vector:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _rotate_clockwise(vector: Vector, axis: Vector) -> Vector:
    """Rotate a vector -90 degrees around an outward face normal."""
    perpendicular = _cross(vector, axis)
    parallel_scale = _dot(vector, axis)
    return (
        perpendicular[0] + axis[0] * parallel_scale,
        perpendicular[1] + axis[1] * parallel_scale,
        perpendicular[2] + axis[2] * parallel_scale,
    )


def _clockwise_permutation(face: str) -> Permutation:
    axis = FACE_NORMALS[face]
    source_for_destination = list(range(54))

    for source_index, (coordinate, normal) in enumerate(FACELET_DESCRIPTORS):
        if _dot(coordinate, axis) != 1:
            continue
        destination_descriptor = (
            _rotate_clockwise(coordinate, axis),
            _rotate_clockwise(normal, axis),
        )
        destination_index = _DESCRIPTOR_TO_INDEX[destination_descriptor]
        source_for_destination[destination_index] = source_index

    return tuple(source_for_destination)


def invert_permutation(permutation: Permutation) -> Permutation:
    inverse = [0] * len(permutation)
    for destination, source in enumerate(permutation):
        inverse[source] = destination
    return tuple(inverse)


def compose_permutations(
    first: Permutation,
    second: Permutation,
) -> Permutation:
    """Return the permutation produced by applying first, then second."""
    return tuple(first[second[destination]] for destination in range(54))


def apply_permutation(state: bytes, permutation: Permutation) -> bytes:
    if len(state) != 54:
        raise ValueError("A 3x3 state must contain exactly 54 facelets.")
    return bytes(state[source] for source in permutation)


MOVE_NAMES: Final[tuple[str, ...]] = tuple(
    move
    for face in ("U", "R", "F", "D", "L", "B")
    for move in (face, f"{face}'", f"{face}2")
)

MOVE_PERMUTATIONS_MUTABLE: dict[str, Permutation] = {}
for _face in ("U", "R", "F", "D", "L", "B"):
    _clockwise = _clockwise_permutation(_face)
    _counterclockwise = invert_permutation(_clockwise)
    _half_turn = compose_permutations(_clockwise, _clockwise)
    MOVE_PERMUTATIONS_MUTABLE[_face] = _clockwise
    MOVE_PERMUTATIONS_MUTABLE[f"{_face}'"] = _counterclockwise
    MOVE_PERMUTATIONS_MUTABLE[f"{_face}2"] = _half_turn

MOVE_PERMUTATIONS: Final[dict[str, Permutation]] = (
    MOVE_PERMUTATIONS_MUTABLE
)
MOVE_TO_INDEX: Final[dict[str, int]] = {
    move: index for index, move in enumerate(MOVE_NAMES)
}
INDEX_TO_MOVE: Final[tuple[str, ...]] = MOVE_NAMES
INVERSE_MOVES: Final[dict[str, str]] = {
    move: (
        move
        if move.endswith("2")
        else move[0]
        if move.endswith("'")
        else f"{move}'"
    )
    for move in MOVE_NAMES
}
MOVE_FACES: Final[dict[str, str]] = {
    move: move[0] for move in MOVE_NAMES
}


def validate_motion_database() -> None:
    """Raise an error if the generated move permutations are inconsistent."""
    identity = tuple(range(54))
    labelled_state = bytes(range(54))

    for move in MOVE_NAMES:
        permutation = MOVE_PERMUTATIONS[move]
        if tuple(sorted(permutation)) != identity:
            raise RuntimeError(f"{move} is not a valid permutation.")

        moved_count = sum(
            destination != source
            for destination, source in enumerate(permutation)
        )
        expected_moved = 20 if not move.endswith("2") else 20
        if moved_count != expected_moved:
            raise RuntimeError(
                f"{move} moves {moved_count} facelets; expected {expected_moved}."
            )

        moved = apply_permutation(labelled_state, permutation)
        restored = apply_permutation(
            moved,
            MOVE_PERMUTATIONS[INVERSE_MOVES[move]],
        )
        if restored != labelled_state:
            raise RuntimeError(f"{move} and its inverse do not cancel.")

    for face in ("U", "R", "F", "D", "L", "B"):
        state = labelled_state
        for _ in range(4):
            state = apply_permutation(state, MOVE_PERMUTATIONS[face])
        if state != labelled_state:
            raise RuntimeError(f"Four {face} turns should be the identity.")


validate_motion_database()
