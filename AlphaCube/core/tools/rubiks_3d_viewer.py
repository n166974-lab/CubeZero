"""Animated 3D viewer for the fixed-position 3x3 Rubik's Cube.

Run from the project root:

    python3 3X3/tools/rubiks_3d_viewer.py

The sequence field accepts standard notation such as:

    R U R' U' F2

You may copy either a bare sequence or a complete line beginning with
``Solution sequence:`` and use the viewer's Paste button. Moves animate
one at a time using the exact permutations shared with the solver.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Final


PROJECT_DIRECTORY: Final[Path] = Path(__file__).resolve().parents[1]
CORE_DIRECTORY: Final[Path] = PROJECT_DIRECTORY / "core"
DATA_DIRECTORY: Final[Path] = PROJECT_DIRECTORY / "data"
sys.path.insert(0, str(CORE_DIRECTORY))

from cube_3x3 import Cube3x3, colors_from_json  # noqa: E402
from motion_database_3x3 import (  # noqa: E402
    FACELET_DESCRIPTORS,
    FACE_NORMALS,
    MOVE_NAMES,
)


Vec3 = tuple[float, float, float]

APP_BACKGROUND: Final[str] = "#111827"
PANEL_BACKGROUND: Final[str] = "#f3f4f6"
CUBE_BODY_COLOR: Final[str] = "#0b0b0b"
CUBE_EDGE_COLOR: Final[str] = "#020202"
ANIMATION_DURATION_MS: Final[int] = 300
ANIMATION_FRAME_MS: Final[int] = 16

COLOR_HEX: Final[dict[int, str]] = {
    1: "#f8fafc",  # white
    2: "#22c55e",  # green
    3: "#facc15",  # yellow
    4: "#2563eb",  # blue
    5: "#ef4444",  # red
    6: "#f97316",  # orange
}
TEXT_HEX: Final[dict[int, str]] = {
    1: "#111827",
    2: "#052e16",
    3: "#422006",
    4: "#ffffff",
    5: "#ffffff",
    6: "#431407",
}

# outward normal, local right, local down, positions
FACE_GEOMETRY: Final[
    dict[str, tuple[Vec3, Vec3, Vec3, tuple[int, ...]]]
] = {
    "F": (
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
        tuple(range(1, 10)),
    ),
    "R": (
        (1.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
        (0.0, -1.0, 0.0),
        tuple(range(10, 19)),
    ),
    "B": (
        (0.0, 0.0, -1.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
        tuple(range(19, 28)),
    ),
    "L": (
        (-1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, -1.0, 0.0),
        tuple(range(28, 37)),
    ),
    "U": (
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        tuple(range(37, 46)),
    ),
    "D": (
        (0.0, -1.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
        tuple(range(46, 55)),
    ),
}

CELL_BOUNDS: Final[tuple[tuple[float, float], ...]] = (
    (-1.43, -0.53),
    (-0.45, 0.45),
    (0.53, 1.43),
)


def _add_vectors(*vectors: Vec3) -> Vec3:
    return tuple(sum(parts) for parts in zip(*vectors))  # type: ignore[return-value]


def _scale_vector(vector: Vec3, scale: float) -> Vec3:
    return tuple(component * scale for component in vector)  # type: ignore[return-value]


def _dot(left: Vec3, right: Vec3) -> float:
    return sum(a * b for a, b in zip(left, right))


def _cross(left: Vec3, right: Vec3) -> Vec3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _rotate_around_axis(
    point: Vec3,
    axis: Vec3,
    angle_degrees: float,
) -> Vec3:
    """Rotate a point around a unit cardinal axis with Rodrigues' formula."""
    radians = math.radians(angle_degrees)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    axis_cross_point = _cross(axis, point)
    parallel = _dot(axis, point) * (1.0 - cosine)
    return (
        point[0] * cosine
        + axis_cross_point[0] * sine
        + axis[0] * parallel,
        point[1] * cosine
        + axis_cross_point[1] * sine
        + axis[1] * parallel,
        point[2] * cosine
        + axis_cross_point[2] * sine
        + axis[2] * parallel,
    )


def move_rotation(move: str) -> tuple[Vec3, float]:
    """Return the outward axis and physical animation angle for a move."""
    axis = tuple(float(value) for value in FACE_NORMALS[move[0]])
    if move.endswith("2"):
        angle = -180.0
    elif move.endswith("'"):
        angle = 90.0
    else:
        angle = -90.0
    return axis, angle  # type: ignore[return-value]


def affected_positions(move: str) -> set[int]:
    """Return every facelet belonging to the physically rotating layer."""
    axis = FACE_NORMALS[move[0]]
    return {
        index + 1
        for index, (coordinate, _normal) in enumerate(FACELET_DESCRIPTORS)
        if sum(a * b for a, b in zip(coordinate, axis)) == 1
    }


def parse_move_sequence(raw_text: str) -> list[str]:
    """Parse bare notation or a copied ``Solution sequence:`` line."""
    text = raw_text.strip()
    if not text:
        return []

    solution_line = next(
        (
            line
            for line in text.splitlines()
            if "solution sequence:" in line.lower()
        ),
        None,
    )
    if solution_line is not None:
        text = solution_line.split(":", 1)[1]

    tokens = [
        token
        for token in re.split(r"[\s,;]+", text.strip())
        if token
    ]
    normalized = [
        token.replace("’", "'").replace("′", "'").upper()
        for token in tokens
    ]
    return normalized


class Rubiks3DViewer:
    """Tkinter application that renders and animates a Cube3x3."""

    def __init__(self, root: tk.Tk, initial_cube: Cube3x3 | None = None) -> None:
        self.root = root
        self.root.title("3×3 Rubik's Cube — Animated Sequence Viewer")
        self.root.geometry("1240x820")
        self.root.minsize(940, 660)

        self.cube = initial_cube or Cube3x3()
        self.yaw = -32.0
        self.pitch = 24.0
        self.zoom = 1.0
        self.drag_start: tuple[int, int] | None = None

        self.move_history: list[str] = []
        self.animation_queue: list[str] = []
        self.animation_running = False
        self.current_animation: str | None = None
        self.animation_progress = 0.0
        self.animation_started_at = 0.0
        self.animation_after_id: str | None = None

        self.command_var = tk.StringVar()
        self.history_var = tk.StringVar(value="No moves applied.")
        self.status_var = tk.StringVar(
            value=(
                "Solved cube ready."
                if self.cube.is_solved()
                else "Loaded cube ready."
            )
        )

        self._configure_style()
        self._build_interface()
        self.root.after_idle(self.draw_cube)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Panel.TFrame", background=PANEL_BACKGROUND)
        style.configure(
            "Title.TLabel",
            background=PANEL_BACKGROUND,
            foreground="#111827",
            font=("TkDefaultFont", 18, "bold"),
        )
        style.configure(
            "Section.TLabel",
            background=PANEL_BACKGROUND,
            foreground="#374151",
            font=("TkDefaultFont", 10, "bold"),
        )
        style.configure(
            "Body.TLabel",
            background=PANEL_BACKGROUND,
            foreground="#4b5563",
        )
        style.configure(
            "Status.TLabel",
            background="#e5e7eb",
            foreground="#1f2937",
            padding=9,
        )
        style.configure(
            "Move.TButton",
            font=("TkFixedFont", 11, "bold"),
        )

    def _build_interface(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        container = ttk.Frame(self.root)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            container,
            background=APP_BACKGROUND,
            highlightthickness=0,
            cursor="fleur",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self.draw_cube())
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag_view)
        self.canvas.bind("<MouseWheel>", self._zoom_view)
        self.canvas.bind("<Button-4>", lambda _event: self._change_zoom(1.08))
        self.canvas.bind("<Button-5>", lambda _event: self._change_zoom(0.92))

        panel = ttk.Frame(
            container,
            style="Panel.TFrame",
            width=420,
            padding=(22, 18),
        )
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_propagate(False)
        panel.columnconfigure((0, 1, 2), weight=1)

        ttk.Label(
            panel,
            text="3×3 Cube Viewer",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(
            panel,
            text=(
                "Paste a solver sequence, click Apply, then watch each "
                "face rotate. Drag to orbit and scroll to zoom."
            ),
            style="Body.TLabel",
            wraplength=365,
            justify="left",
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(4, 14),
        )

        ttk.Label(
            panel,
            text="MOVE SEQUENCE",
            style="Section.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        self.command_entry = ttk.Entry(
            panel,
            textvariable=self.command_var,
            font=("TkFixedFont", 12),
        )
        self.command_entry.grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(6, 7),
        )
        self.command_entry.bind(
            "<Return>",
            lambda _event: self.apply_entry(),
        )

        ttk.Button(
            panel,
            text="Paste",
            command=self.paste_sequence,
        ).grid(row=4, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(
            panel,
            text="Copy input",
            command=self.copy_input_sequence,
        ).grid(row=4, column=1, sticky="ew", padx=3)
        ttk.Button(
            panel,
            text="Apply",
            command=self.apply_entry,
        ).grid(row=4, column=2, sticky="ew", padx=(3, 0))

        ttk.Label(
            panel,
            text="INDIVIDUAL MOVES",
            style="Section.TLabel",
        ).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(16, 6),
        )

        for column, heading in enumerate(("Clockwise", "Counter", "180°")):
            ttk.Label(
                panel,
                text=heading,
                style="Body.TLabel",
                anchor="center",
            ).grid(row=6, column=column, sticky="ew")

        face_order = ("U", "R", "F", "D", "L", "B")
        for face_index, face in enumerate(face_order):
            row = 7 + face_index
            for column, move in enumerate((face, f"{face}'", f"{face}2")):
                ttk.Button(
                    panel,
                    text=move,
                    style="Move.TButton",
                    command=lambda name=move: self.apply_moves([name]),
                ).grid(
                    row=row,
                    column=column,
                    sticky="ew",
                    padx=(0, 3)
                    if column == 0
                    else (3, 0)
                    if column == 2
                    else 3,
                    pady=2,
                )

        state_row = 13
        ttk.Label(
            panel,
            text="CUBE STATE",
            style="Section.TLabel",
        ).grid(
            row=state_row,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(16, 6),
        )
        ttk.Button(
            panel,
            text="Load JSON…",
            command=self.load_json,
        ).grid(
            row=state_row + 1,
            column=0,
            sticky="ew",
            padx=(0, 3),
        )
        ttk.Button(
            panel,
            text="Save JSON…",
            command=self.save_json,
        ).grid(
            row=state_row + 1,
            column=1,
            sticky="ew",
            padx=3,
        )
        ttk.Button(
            panel,
            text="Reset",
            command=self.reset_cube,
        ).grid(
            row=state_row + 1,
            column=2,
            sticky="ew",
            padx=(3, 0),
        )
        ttk.Button(
            panel,
            text="Stop animation",
            command=self.stop_animation,
        ).grid(
            row=state_row + 2,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(7, 0),
        )

        history_row = state_row + 3
        ttk.Label(
            panel,
            text="APPLIED SEQUENCE",
            style="Section.TLabel",
        ).grid(
            row=history_row,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(15, 5),
        )
        ttk.Label(
            panel,
            textvariable=self.history_var,
            style="Body.TLabel",
            wraplength=365,
            justify="left",
        ).grid(
            row=history_row + 1,
            column=0,
            columnspan=3,
            sticky="nw",
        )
        ttk.Button(
            panel,
            text="Copy applied sequence",
            command=self.copy_history,
        ).grid(
            row=history_row + 2,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(7, 10),
        )

        panel.rowconfigure(history_row + 3, weight=1)
        ttk.Label(
            panel,
            textvariable=self.status_var,
            style="Status.TLabel",
            wraplength=365,
            justify="left",
        ).grid(
            row=history_row + 4,
            column=0,
            columnspan=3,
            sticky="sew",
        )
        self.command_entry.focus_set()

    def _rotate_view(self, point: Vec3) -> Vec3:
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        x_after_yaw = point[0] * cos_yaw + point[2] * sin_yaw
        z_after_yaw = -point[0] * sin_yaw + point[2] * cos_yaw
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        y_after_pitch = (
            point[1] * cos_pitch - z_after_yaw * sin_pitch
        )
        z_after_pitch = (
            point[1] * sin_pitch + z_after_yaw * cos_pitch
        )
        return x_after_yaw, y_after_pitch, z_after_pitch

    def _project(self, point: Vec3) -> tuple[float, float]:
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        rotated = self._rotate_view(point)
        camera_distance = 9.0
        perspective = camera_distance / (camera_distance - rotated[2])
        scale = min(width, height) * 0.13 * self.zoom
        return (
            width / 2 + rotated[0] * scale * perspective,
            height / 2 - rotated[1] * scale * perspective,
        )

    @staticmethod
    def _face_square(
        normal: Vec3,
        right: Vec3,
        down: Vec3,
        distance: float,
        left: float,
        top: float,
        right_edge: float,
        bottom: float,
    ) -> tuple[Vec3, Vec3, Vec3, Vec3]:
        face_center = _scale_vector(normal, distance)

        def point(horizontal: float, vertical: float) -> Vec3:
            return _add_vectors(
                face_center,
                _scale_vector(right, horizontal),
                _scale_vector(down, vertical),
            )

        return (
            point(left, top),
            point(right_edge, top),
            point(right_edge, bottom),
            point(left, bottom),
        )

    def draw_cube(self) -> None:
        self.canvas.delete("all")
        primitives: list[
            tuple[
                float,
                str,
                tuple[Vec3, Vec3, Vec3, Vec3],
                int | None,
                int | None,
            ]
        ] = []

        rotating_positions: set[int] = set()
        rotation_axis: Vec3 = (0.0, 0.0, 1.0)
        rotation_angle = 0.0
        if self.current_animation is not None:
            rotating_positions = affected_positions(self.current_animation)
            rotation_axis, target_angle = move_rotation(
                self.current_animation
            )
            rotation_angle = target_angle * self.animation_progress

        for normal, right, down, positions in FACE_GEOMETRY.values():
            if self._rotate_view(normal)[2] > 0.015:
                base = self._face_square(
                    normal,
                    right,
                    down,
                    distance=1.5,
                    left=-1.53,
                    top=-1.53,
                    right_edge=1.53,
                    bottom=1.53,
                )
                base_depth = (
                    sum(self._rotate_view(point)[2] for point in base) / 4
                )
                primitives.append(
                    (base_depth, "base", base, None, None)
                )

            for local_index, position in enumerate(positions):
                row, column = divmod(local_index, 3)
                left, right_edge = CELL_BOUNDS[column]
                top, bottom = CELL_BOUNDS[row]
                sticker = self._face_square(
                    normal,
                    right,
                    down,
                    distance=1.518,
                    left=left,
                    top=top,
                    right_edge=right_edge,
                    bottom=bottom,
                )
                display_normal = normal
                label: int | None = position

                if position in rotating_positions:
                    sticker = tuple(
                        _rotate_around_axis(
                            point,
                            rotation_axis,
                            rotation_angle,
                        )
                        for point in sticker
                    )  # type: ignore[assignment]
                    display_normal = _rotate_around_axis(
                        normal,
                        rotation_axis,
                        rotation_angle,
                    )
                    label = None

                if self._rotate_view(display_normal)[2] <= 0.015:
                    continue

                color = self.cube.state[position - 1]
                sticker_depth = (
                    sum(self._rotate_view(point)[2] for point in sticker) / 4
                )
                primitives.append(
                    (sticker_depth, "sticker", sticker, color, label)
                )

        primitives.sort(
            key=lambda primitive: (
                0 if primitive[1] == "base" else 1,
                primitive[0],
            )
        )
        for _depth, kind, vertices, color, label in primitives:
            projected = [self._project(point) for point in vertices]
            polygon_points = [
                coordinate for point in projected for coordinate in point
            ]
            if kind == "base":
                self.canvas.create_polygon(
                    polygon_points,
                    fill=CUBE_BODY_COLOR,
                    outline=CUBE_EDGE_COLOR,
                    width=3,
                )
            else:
                assert color is not None
                self.canvas.create_polygon(
                    polygon_points,
                    fill=COLOR_HEX[color],
                    outline="#080b12",
                    width=2,
                    joinstyle=tk.ROUND,
                )

            if label is not None and color is not None:
                center_x = sum(point[0] for point in projected) / 4
                center_y = sum(point[1] for point in projected) / 4
                self.canvas.create_text(
                    center_x,
                    center_y,
                    text=str(label),
                    fill=TEXT_HEX[color],
                    font=("TkDefaultFont", 8, "bold"),
                )

        self.canvas.create_text(
            18,
            18,
            anchor="nw",
            text="Drag to orbit  •  Scroll to zoom",
            fill="#9ca3af",
            font=("TkDefaultFont", 10),
        )

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x, event.y)

    def _drag_view(self, event: tk.Event) -> None:
        if self.drag_start is None:
            self.drag_start = (event.x, event.y)
            return
        previous_x, previous_y = self.drag_start
        self.yaw += (event.x - previous_x) * 0.55
        self.pitch -= (event.y - previous_y) * 0.55
        self.pitch = max(-89.0, min(89.0, self.pitch))
        self.drag_start = (event.x, event.y)
        self.draw_cube()

    def _zoom_view(self, event: tk.Event) -> None:
        self._change_zoom(1.08 if event.delta > 0 else 0.92)

    def _change_zoom(self, factor: float) -> None:
        self.zoom = max(0.55, min(1.75, self.zoom * factor))
        self.draw_cube()

    def paste_sequence(self) -> None:
        try:
            clipboard_text = self.root.clipboard_get()
        except tk.TclError:
            self.status_var.set("The clipboard does not contain text.")
            return
        moves = parse_move_sequence(clipboard_text)
        if not moves:
            self.status_var.set("No move sequence was found in the clipboard.")
            return
        self.command_var.set(" ".join(moves))
        self.status_var.set(f"Pasted {len(moves)} move(s).")

    def _copy_text(self, text: str, label: str) -> None:
        if not text:
            self.status_var.set(f"There is no {label.lower()} to copy.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self.status_var.set(f"Copied {label.lower()} to the clipboard.")

    def copy_input_sequence(self) -> None:
        self._copy_text(self.command_var.get().strip(), "Input sequence")

    def copy_history(self) -> None:
        self._copy_text(" ".join(self.move_history), "Applied sequence")

    def apply_entry(self) -> None:
        moves = parse_move_sequence(self.command_var.get())
        if not moves:
            self.status_var.set("Enter moves such as R U R' U' F2.")
            return
        if self.apply_moves(moves):
            self.command_var.set("")

    def apply_moves(self, moves: list[str]) -> bool:
        invalid = [move for move in moves if move not in MOVE_NAMES]
        if invalid:
            self.status_var.set(
                f"Unknown move: {invalid[0]}. Use U R F D L B with ', 2."
            )
            return False
        self.animation_queue.extend(moves)
        self.status_var.set(
            f"Queued {' '.join(moves)}. "
            f"{len(self.animation_queue)} move(s) waiting."
        )
        if not self.animation_running:
            self._start_next_animation()
        return True

    def _start_next_animation(self) -> None:
        self.animation_after_id = None
        if not self.animation_queue:
            self.animation_running = False
            self.current_animation = None
            self.animation_progress = 0.0
            state_label = (
                "Cube is solved." if self.cube.is_solved() else "State updated."
            )
            self.status_var.set(f"Animation complete. {state_label}")
            self.draw_cube()
            return

        self.animation_running = True
        self.current_animation = self.animation_queue.pop(0)
        self.animation_progress = 0.0
        self.animation_started_at = time.perf_counter()
        remaining = len(self.animation_queue)
        self.status_var.set(
            f"Animating {self.current_animation}. "
            f"{remaining} move(s) remain queued."
        )
        self._run_animation_frame()

    def _run_animation_frame(self) -> None:
        if not self.animation_running or self.current_animation is None:
            return
        elapsed_ms = (
            time.perf_counter() - self.animation_started_at
        ) * 1000.0
        linear_progress = min(
            1.0,
            elapsed_ms / ANIMATION_DURATION_MS,
        )
        self.animation_progress = (
            linear_progress
            * linear_progress
            * (3.0 - 2.0 * linear_progress)
        )
        self.draw_cube()

        if linear_progress < 1.0:
            self.animation_after_id = self.root.after(
                ANIMATION_FRAME_MS,
                self._run_animation_frame,
            )
            return

        completed_move = self.current_animation
        self.cube.apply_move(completed_move)
        self.move_history.append(completed_move)
        self.history_var.set(" ".join(self.move_history))
        self.current_animation = None
        self.animation_progress = 0.0
        self.draw_cube()
        self.animation_after_id = self.root.after(
            40,
            self._start_next_animation,
        )

    def _cancel_animation(self) -> None:
        if self.animation_after_id is not None:
            try:
                self.root.after_cancel(self.animation_after_id)
            except tk.TclError:
                pass
        self.animation_after_id = None
        self.animation_queue.clear()
        self.animation_running = False
        self.current_animation = None
        self.animation_progress = 0.0

    def stop_animation(self) -> None:
        self._cancel_animation()
        self.status_var.set("Animation stopped; unfinished moves were discarded.")
        self.draw_cube()

    def reset_cube(self) -> None:
        self._cancel_animation()
        self.cube.reset()
        self.move_history.clear()
        self.history_var.set("No moves applied.")
        self.status_var.set("Reset to the solved state.")
        self.draw_cube()

    def load_json(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Load a 3x3 cube state",
            initialdir=DATA_DIRECTORY,
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not file_path:
            return
        self._cancel_animation()
        try:
            with open(file_path, "r", encoding="utf-8") as state_file:
                data: Any = json.load(state_file)
            loaded_cube = Cube3x3(colors_from_json(data))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            messagebox.showerror(
                "Could not load cube state",
                str(error),
                parent=self.root,
            )
            self.status_var.set("JSON loading failed.")
            return
        self.cube = loaded_cube
        self.move_history.clear()
        self.history_var.set("Loaded state; no moves applied yet.")
        self.status_var.set(f"Loaded {Path(file_path).name}.")
        self.draw_cube()

    def save_json(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Save the current 3x3 cube state",
            initialdir=DATA_DIRECTORY,
            initialfile="cube_state.json",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as state_file:
                json.dump(self.cube.to_json_dict(), state_file, indent=2)
                state_file.write("\n")
        except OSError as error:
            messagebox.showerror(
                "Could not save cube state",
                str(error),
                parent=self.root,
            )
            self.status_var.set("JSON saving failed.")
            return
        self.status_var.set(f"Saved {Path(file_path).name}.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open the animated 3x3 viewer.")
    parser.add_argument(
        "--state",
        type=Path,
        help="Optional JSON cube state to load at startup.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    initial_cube: Cube3x3 | None = None
    if arguments.state is not None:
        try:
            initial_cube = Cube3x3.load_json(arguments.state)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise SystemExit(f"Error: {error}") from error

    root = tk.Tk()
    Rubiks3DViewer(root, initial_cube)
    root.mainloop()


if __name__ == "__main__":
    main()
