"""Interactive 3D viewer for the numbered 2x2 Rubik's Cube.

Run from the project root with:

    python3 Setup/rubiks_3d_viewer.py

Controls:
    - Enter one or more motions, such as: m1 m5 m2
    - Use the m1-m8 buttons for individual motions
    - Drag the cube with the left mouse button to rotate the view
    - Use the mouse wheel to zoom
    - Load or save a cube state as JSON
"""

from __future__ import annotations

import json
import math
import re
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Final

try:
    from .cube_2x2 import Cube2x2
    from .motion_database import MOTION_DESCRIPTIONS, MOTIONS
except ImportError:
    from cube_2x2 import Cube2x2
    from motion_database import MOTION_DESCRIPTIONS, MOTIONS


Vec3 = tuple[float, float, float]

APP_BACKGROUND: Final[str] = "#111827"
PANEL_BACKGROUND: Final[str] = "#f3f4f6"
CUBE_BODY_COLOR: Final[str] = "#111111"
CUBE_EDGE_COLOR: Final[str] = "#050505"

COLOR_HEX: Final[dict[int, str]] = {
    0: "#6b7280",  # unassigned
    1: "#f8fafc",  # white
    2: "#22c55e",  # green
    3: "#facc15",  # yellow
    4: "#2563eb",  # blue
    5: "#ef4444",  # red
    6: "#f97316",  # orange
}

TEXT_HEX: Final[dict[int, str]] = {
    0: "#ffffff",
    1: "#111827",
    2: "#052e16",
    3: "#422006",
    4: "#ffffff",
    5: "#ffffff",
    6: "#431407",
}

COLOR_NAMES: Final[dict[int, str]] = {
    0: "unassigned",
    1: "white",
    2: "green",
    3: "yellow",
    4: "blue",
    5: "red",
    6: "orange",
}

ANIMATION_DURATION_MS: Final[int] = 360
ANIMATION_FRAME_MS: Final[int] = 16

# Axis and signed quarter-turn angle for each motion. These rotations produce
# the same source-to-destination transfers recorded in motion_database.py.
MOTION_ROTATIONS: Final[dict[str, tuple[str, float]]] = {
    "m1": ("y", 90.0),
    "m2": ("y", -90.0),
    "m3": ("y", 90.0),
    "m4": ("y", -90.0),
    "m5": ("x", -90.0),
    "m6": ("x", 90.0),
    "m7": ("x", -90.0),
    "m8": ("x", 90.0),
}


# Each entry contains:
#     outward normal, local right direction, local down direction, positions
#
# The local directions make the 3D positions match Resources/Net.png.
FACE_GEOMETRY: Final[
    dict[str, tuple[Vec3, Vec3, Vec3, tuple[int, int, int, int]]]
] = {
    "front": (
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
        (1, 2, 3, 4),
    ),
    "right": (
        (1.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
        (0.0, -1.0, 0.0),
        (5, 6, 7, 8),
    ),
    "back": (
        (0.0, 0.0, -1.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
        (9, 10, 11, 12),
    ),
    "left": (
        (-1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, -1.0, 0.0),
        (13, 14, 15, 16),
    ),
    "top": (
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        (17, 18, 19, 20),
    ),
    "bottom": (
        (0.0, -1.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, -1.0),
        (21, 22, 23, 24),
    ),
}


def _add_vectors(*vectors: Vec3) -> Vec3:
    return tuple(sum(parts) for parts in zip(*vectors))  # type: ignore[return-value]


def _scale_vector(vector: Vec3, scale: float) -> Vec3:
    return tuple(component * scale for component in vector)  # type: ignore[return-value]


def _rotate_around_axis(point: Vec3, axis: str, angle: float) -> Vec3:
    """Rotate a world-space point around the x or y axis."""
    radians = math.radians(angle)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    x, y, z = point

    if axis == "x":
        return x, y * cosine - z * sine, y * sine + z * cosine
    if axis == "y":
        return x * cosine + z * sine, y, -x * sine + z * cosine
    raise ValueError(f"Unsupported animation axis: {axis!r}")


def cube_to_json_data(cube: Cube2x2) -> dict[str, Any]:
    """Create the supported JSON representation of a cube."""
    return {
        "format": "2x2-rubiks-cube-state",
        "version": 1,
        "color_codes": {
            str(code): name for code, name in COLOR_NAMES.items() if code != 0
        },
        "stickers": [
            {"position": position, "color": color}
            for position, color in cube.as_pairs()
        ],
    }


def cube_from_json_data(data: Any) -> Cube2x2:
    """Validate JSON-compatible data and return its cube state.

    Supported forms:
        {"stickers": [{"position": 1, "color": 1}, ...]}
        {"colors": [24 integer color values]}
        [24 integer color values]
    """
    if isinstance(data, list):
        colors = data
    elif isinstance(data, dict) and "colors" in data:
        colors = data["colors"]
    elif isinstance(data, dict) and "stickers" in data:
        stickers = data["stickers"]
        if not isinstance(stickers, list):
            raise ValueError("'stickers' must be a list.")

        colors_by_position: list[int | None] = [None] * 24
        for item in stickers:
            if not isinstance(item, dict):
                raise ValueError("Every sticker must be a JSON object.")

            position = item.get("position")
            color = item.get("color")
            if (
                not isinstance(position, int)
                or isinstance(position, bool)
                or position < 1
                or position > 24
            ):
                raise ValueError("Every sticker position must be from 1 to 24.")
            if colors_by_position[position - 1] is not None:
                raise ValueError(f"Position {position} appears more than once.")
            colors_by_position[position - 1] = color

        missing = [
            index + 1
            for index, color in enumerate(colors_by_position)
            if color is None
        ]
        if missing:
            raise ValueError(
                "The JSON is missing position(s): "
                + ", ".join(str(position) for position in missing)
            )
        colors = colors_by_position
    else:
        raise ValueError(
            "Expected a JSON object containing 'stickers' or 'colors'."
        )

    if not isinstance(colors, list):
        raise ValueError("'colors' must be a list.")

    # Cube2x2 performs the length, integer, and 0-6 range checks.
    cube = Cube2x2(colors)  # type: ignore[arg-type]
    if not cube.has_valid_color_counts():
        raise ValueError(
            "A complete state must contain exactly four stickers of each "
            "color code from 1 through 6."
        )
    return cube


class Rubiks3DViewer:
    """Tkinter application that renders and controls a Cube2x2."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("2x2 Rubik's Cube — 3D Motion Viewer")
        self.root.geometry("1120x760")
        self.root.minsize(820, 580)

        self.cube = Cube2x2()
        self.yaw = -30.0
        self.pitch = 25.0
        self.zoom = 1.0
        self.drag_start: tuple[int, int] | None = None
        self.motion_history: list[str] = []
        self.animation_queue: list[str] = []
        self.animation_running = False
        self.current_animation: str | None = None
        self.animation_progress = 0.0
        self.animation_started_at = 0.0
        self.animation_after_id: str | None = None

        self.command_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Solved cube ready.")
        self.history_var = tk.StringVar(value="No motions applied.")

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
            font=("TkDefaultFont", 11, "bold"),
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
            padding=10,
        )
        style.configure("Motion.TButton", font=("TkDefaultFont", 11, "bold"))

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
            width=350,
            padding=(24, 22),
        )
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_propagate(False)
        panel.columnconfigure((0, 1), weight=1)

        ttk.Label(
            panel,
            text="2×2 Cube Viewer",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(
            panel,
            text="Drag the cube to rotate it. Scroll to zoom.",
            style="Body.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 22))

        ttk.Label(
            panel,
            text="MOTION SEQUENCE",
            style="Section.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w")

        command_entry = ttk.Entry(
            panel,
            textvariable=self.command_var,
            font=("TkFixedFont", 12),
        )
        command_entry.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(7, 8),
        )
        command_entry.bind("<Return>", lambda _event: self.apply_entry())

        ttk.Button(
            panel,
            text="Apply sequence",
            command=self.apply_entry,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 20))

        ttk.Label(
            panel,
            text="INDIVIDUAL MOTIONS",
            style="Section.TLabel",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 7))

        for index, motion in enumerate(MOTIONS):
            row = 6 + index // 2
            column = index % 2
            short_description = (
                MOTION_DESCRIPTIONS[motion]
                .replace("horizontal layer", "row")
                .replace("vertical layer", "column")
            )
            ttk.Button(
                panel,
                text=f"{motion}  {short_description.split(' -> ')[1]}",
                style="Motion.TButton",
                command=lambda name=motion: self.apply_motions([name]),
            ).grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(0, 4) if column == 0 else (4, 0),
                pady=4,
            )

        file_row = 10
        ttk.Label(
            panel,
            text="CUBE STATE",
            style="Section.TLabel",
        ).grid(
            row=file_row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(22, 7),
        )

        ttk.Button(
            panel,
            text="Load JSON…",
            command=self.load_json,
        ).grid(row=file_row + 1, column=0, sticky="ew", padx=(0, 4))

        ttk.Button(
            panel,
            text="Save JSON…",
            command=self.save_json,
        ).grid(row=file_row + 1, column=1, sticky="ew", padx=(4, 0))

        ttk.Button(
            panel,
            text="Reset to solved",
            command=self.reset_cube,
        ).grid(
            row=file_row + 2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 18),
        )

        ttk.Label(
            panel,
            text="HISTORY",
            style="Section.TLabel",
        ).grid(row=file_row + 3, column=0, columnspan=2, sticky="w")

        ttk.Label(
            panel,
            textvariable=self.history_var,
            style="Body.TLabel",
            wraplength=300,
            justify="left",
        ).grid(
            row=file_row + 4,
            column=0,
            columnspan=2,
            sticky="nw",
            pady=(7, 16),
        )

        panel.rowconfigure(file_row + 5, weight=1)

        ttk.Label(
            panel,
            textvariable=self.status_var,
            style="Status.TLabel",
            wraplength=300,
            justify="left",
        ).grid(
            row=file_row + 6,
            column=0,
            columnspan=2,
            sticky="sew",
        )

        command_entry.focus_set()

    def _rotate(self, point: Vec3) -> Vec3:
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)

        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        x1 = point[0] * cos_yaw + point[2] * sin_yaw
        z1 = -point[0] * sin_yaw + point[2] * cos_yaw

        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        y2 = point[1] * cos_pitch - z1 * sin_pitch
        z2 = point[1] * sin_pitch + z1 * cos_pitch
        return x1, y2, z2

    def _project(self, point: Vec3) -> tuple[float, float]:
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        center_x = width / 2
        center_y = height / 2

        rotated = self._rotate(point)
        camera_distance = 6.0
        perspective = camera_distance / (camera_distance - rotated[2])
        scale = min(width, height) * 0.205 * self.zoom
        return (
            center_x + rotated[0] * scale * perspective,
            center_y - rotated[1] * scale * perspective,
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

        animated_positions: set[int] = set()
        animation_axis = ""
        animation_angle = 0.0
        if self.current_animation is not None:
            animated_positions = {
                position
                for cycle in MOTIONS[self.current_animation]
                for position in cycle
            }
            animation_axis, target_angle = MOTION_ROTATIONS[
                self.current_animation
            ]
            animation_angle = target_angle * self.animation_progress

        horizontal_bounds = ((-0.94, -0.06), (0.06, 0.94))
        vertical_bounds = ((-0.94, -0.06), (0.06, 0.94))

        for geometry in FACE_GEOMETRY.values():
            normal, right, down, positions = geometry

            # The black cube body stays in place while a layer is animated.
            rotated_normal = self._rotate(normal)
            if rotated_normal[2] > 0.015:
                base = self._face_square(
                    normal,
                    right,
                    down,
                    distance=1.0,
                    left=-1.02,
                    top=-1.02,
                    right_edge=1.02,
                    bottom=1.02,
                )
                base_depth = sum(self._rotate(point)[2] for point in base) / 4
                primitives.append(
                    (base_depth, "base", base, None, None)
                )

            for index, position in enumerate(positions):
                row, column = divmod(index, 2)
                left, right_edge = horizontal_bounds[column]
                top, bottom = vertical_bounds[row]
                sticker = self._face_square(
                    normal,
                    right,
                    down,
                    distance=1.018,
                    left=left,
                    top=top,
                    right_edge=right_edge,
                    bottom=bottom,
                )

                display_normal = normal
                label: int | None = position
                if position in animated_positions:
                    sticker = tuple(
                        _rotate_around_axis(
                            point,
                            animation_axis,
                            animation_angle,
                        )
                        for point in sticker
                    )  # type: ignore[assignment]
                    display_normal = _rotate_around_axis(
                        normal,
                        animation_axis,
                        animation_angle,
                    )
                    # Position numbers describe fixed slots, not moving
                    # stickers, so hide them during the physical turn.
                    if 0.0 < self.animation_progress < 1.0:
                        label = None

                if self._rotate(display_normal)[2] <= 0.015:
                    continue

                color = self.cube.get_color(position)
                sticker_depth = (
                    sum(self._rotate(point)[2] for point in sticker) / 4
                )
                primitives.append(
                    (sticker_depth, "sticker", sticker, color, label)
                )

        # Render every black face base before any sticker. Sorting all polygons
        # together by average depth allowed the center of a large face base to
        # be nearer than its farther two stickers, causing that base to paint
        # over half of its own face. Within each pass, farther polygons still
        # render first.
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
                    outline="#0b0f19",
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
                    font=("TkDefaultFont", 11, "bold"),
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
        self.zoom = max(0.55, min(1.7, self.zoom * factor))
        self.draw_cube()

    def apply_entry(self) -> None:
        raw_command = self.command_var.get()
        motions = [
            token.lower()
            for token in re.split(r"[\s,]+", raw_command.strip())
            if token
        ]
        if not motions:
            self.status_var.set("Enter at least one motion, such as m1 m5 m2.")
            return

        if self.apply_motions(motions):
            self.command_var.set("")

    def apply_motions(self, motions: list[str]) -> bool:
        invalid = [name for name in motions if name not in MOTIONS]
        if invalid:
            valid_names = ", ".join(MOTIONS)
            self.status_var.set(
                f"Unknown motion: {invalid[0]}. Valid motions: {valid_names}."
            )
            return False

        self.animation_queue.extend(motions)
        queued = len(self.animation_queue)
        self.status_var.set(
            f"Queued {' '.join(motions)}. {queued} motion(s) waiting."
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
        queue_label = (
            f" {remaining} motion(s) remain queued." if remaining else ""
        )
        self.status_var.set(
            f"Animating {self.current_animation}.{queue_label}"
        )
        self._run_animation_frame()

    def _run_animation_frame(self) -> None:
        if not self.animation_running or self.current_animation is None:
            return

        elapsed_ms = (
            time.perf_counter() - self.animation_started_at
        ) * 1000.0
        linear_progress = min(1.0, elapsed_ms / ANIMATION_DURATION_MS)

        # Smoothstep easing starts and ends the turn gently.
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

        completed_motion = self.current_animation
        self.cube.apply_motion(completed_motion)
        self.motion_history.append(completed_motion)
        self.motion_history = self.motion_history[-24:]
        self.history_var.set(" ".join(self.motion_history))
        self.current_animation = None
        self.animation_progress = 0.0
        self.draw_cube()

        self.animation_after_id = self.root.after(
            45,
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

    def reset_cube(self) -> None:
        self._cancel_animation()
        self.cube.reset()
        self.motion_history.clear()
        self.history_var.set("No motions applied.")
        self.status_var.set("Reset to the solved state.")
        self.draw_cube()

    def load_json(self) -> None:
        initial_directory = Path(__file__).resolve().parent
        file_path = filedialog.askopenfilename(
            title="Load a 2x2 cube state",
            initialdir=initial_directory,
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not file_path:
            return

        self._cancel_animation()
        try:
            with open(file_path, "r", encoding="utf-8") as state_file:
                data = json.load(state_file)
            loaded_cube = cube_from_json_data(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            messagebox.showerror(
                "Could not load cube state",
                str(error),
                parent=self.root,
            )
            self.status_var.set("JSON loading failed.")
            return

        self.cube = loaded_cube
        self.motion_history.clear()
        self.history_var.set("Loaded state; no motions applied yet.")
        self.status_var.set(f"Loaded {Path(file_path).name}.")
        self.draw_cube()

    def save_json(self) -> None:
        initial_directory = Path(__file__).resolve().parent
        file_path = filedialog.asksaveasfilename(
            title="Save the current 2x2 cube state",
            initialdir=initial_directory,
            initialfile="cube_state.json",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as state_file:
                json.dump(
                    cube_to_json_data(self.cube),
                    state_file,
                    indent=2,
                )
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


def main() -> None:
    root = tk.Tk()
    Rubiks3DViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
