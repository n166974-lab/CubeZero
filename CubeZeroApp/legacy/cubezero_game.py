"""CubeZero desktop game for AlphaCube (3x3) and BetaCube (2x2).

Run from the CubeZeroApp/legacy folder:

    python3 cubezero_game.py

AlphaCube's Solve button always launches this exact command:

    python3 AlphaCube/tools/beam_database_solver.py --beam-width 20000 --depth 100
"""

from __future__ import annotations

import json
import math
import random
import re
import secrets
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable, Final


LEGACY_DIRECTORY: Final[Path] = Path(__file__).resolve().parent
PROJECT_ROOT: Final[Path] = LEGACY_DIRECTORY.parents[1]
LEGACY_ASSETS: Final[Path] = LEGACY_DIRECTORY / "assets"
LOGO_PATH: Final[Path] = LEGACY_ASSETS / "cubezero_logo.png"
ALPHA_TAB_ICON_PATH: Final[Path] = LEGACY_ASSETS / "alphacube_3d_tab.png"
BETA_TAB_ICON_PATH: Final[Path] = LEGACY_ASSETS / "betacube_3d_tab.png"
ALPHA_DIRECTORY: Final[Path] = PROJECT_ROOT / "AlphaCube"
ALPHA_CORE: Final[Path] = ALPHA_DIRECTORY / "core"
ALPHA_DATA: Final[Path] = ALPHA_DIRECTORY / "data"
BETA_DIRECTORY: Final[Path] = PROJECT_ROOT / "BetaCube"
BETA_SETUP: Final[Path] = BETA_DIRECTORY / "Setup"
BETA_SOLVER: Final[Path] = BETA_DIRECTORY / "Solver"

sys.path.insert(0, str(ALPHA_CORE))
from cube_3x3 import Cube3x3 as AlphaCube3x3  # noqa: E402
from motion_database_3x3 import (  # noqa: E402
    FACELET_DESCRIPTORS as ALPHA_FACELET_DESCRIPTORS,
    FACE_NORMALS as ALPHA_FACE_NORMALS,
    MOVE_FACES as ALPHA_MOVE_FACES,
    MOVE_NAMES as ALPHA_MOVE_NAMES,
)

sys.path.insert(0, str(BETA_SETUP))
from cube_2x2 import Cube2x2 as BetaCube2x2  # noqa: E402
from motion_database import (  # noqa: E402
    INVERSE_MOTIONS as BETA_INVERSES,
    MOTIONS as BETA_MOTIONS,
)


Vec3 = tuple[float, float, float]
CubeObject = AlphaCube3x3 | BetaCube2x2

ALPHA_SCRAMBLE_LENGTH: Final[int] = 40
BETA_SCRAMBLE_LENGTH: Final[int] = 20

ALPHA_SOLVE_COMMAND: Final[tuple[str, ...]] = (
    "python3",
    "AlphaCube/tools/beam_database_solver.py",
    "--beam-width",
    "20000",
    "--depth",
    "100",
)
BETA_SOLVE_COMMAND: Final[tuple[str, ...]] = (
    "python3",
    "BetaCube/Solver/color_evaluation_solver.py",
    "--no-fallback",
)

BACKGROUND: Final[str] = "#f5f7fb"
NAVY: Final[str] = "#dfe4ed"
NAVY_LIGHT: Final[str] = "#e8ecf3"
BLUE: Final[str] = "#3d5cab"
BLUE_DARK: Final[str] = "#2f478c"
GREEN: Final[str] = "#8dcc35"
ORANGE: Final[str] = "#ff541e"
TEXT: Final[str] = "#182238"
MUTED: Final[str] = "#68738a"
CARD: Final[str] = "#ffffff"
LOGO_BACKGROUND: Final[str] = "#fcfcfc"
LINE: Final[str] = "#dfe4ed"

COLOR_HEX: Final[dict[int, str]] = {
    1: "#f8fafc",
    2: "#8dcc35",
    3: "#facc15",
    4: "#3d5cab",
    5: "#ef4444",
    6: "#ff541e",
}
TEXT_HEX: Final[dict[int, str]] = {
    1: "#111827",
    2: "#17340a",
    3: "#4b3500",
    4: "#ffffff",
    5: "#ffffff",
    6: "#4a1607",
}

# Outward normal, local right, local down. Position lists are assigned per mode.
FACE_VECTORS: Final[
    dict[str, tuple[Vec3, Vec3, Vec3]]
] = {
    "F": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
    "R": ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, -1.0, 0.0)),
    "B": ((0.0, 0.0, -1.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
    "L": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    "U": ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "D": ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
}

ALPHA_FACE_POSITIONS: Final[dict[str, tuple[int, ...]]] = {
    "F": tuple(range(1, 10)),
    "R": tuple(range(10, 19)),
    "B": tuple(range(19, 28)),
    "L": tuple(range(28, 37)),
    "U": tuple(range(37, 46)),
    "D": tuple(range(46, 55)),
}
BETA_FACE_POSITIONS: Final[dict[str, tuple[int, ...]]] = {
    "F": (1, 2, 3, 4),
    "R": (5, 6, 7, 8),
    "B": (9, 10, 11, 12),
    "L": (13, 14, 15, 16),
    "U": (17, 18, 19, 20),
    "D": (21, 22, 23, 24),
}

ALPHA_CELL_BOUNDS: Final[tuple[tuple[float, float], ...]] = (
    (-1.43, -0.53),
    (-0.45, 0.45),
    (0.53, 1.43),
)
BETA_CELL_BOUNDS: Final[tuple[tuple[float, float], ...]] = (
    (-1.43, -0.08),
    (0.08, 1.43),
)

BETA_ROTATIONS: Final[dict[str, tuple[Vec3, float]]] = {
    "m1": ((0.0, 1.0, 0.0), 90.0),
    "m2": ((0.0, 1.0, 0.0), -90.0),
    "m3": ((0.0, 1.0, 0.0), 90.0),
    "m4": ((0.0, 1.0, 0.0), -90.0),
    "m5": ((1.0, 0.0, 0.0), -90.0),
    "m6": ((1.0, 0.0, 0.0), 90.0),
    "m7": ((1.0, 0.0, 0.0), -90.0),
    "m8": ((1.0, 0.0, 0.0), 90.0),
}


TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "settings": "⚙  Settings",
        "settings_title": "Settings",
        "language": "Language",
        "apply": "Apply",
        "cancel": "Cancel",
        "scramble": "SCRAMBLE",
        "solve": "SOLVE",
        "reset": "RESET CUBE",
        "solver_status": "SOLVER STATUS",
        "command": "COMMAND",
        "alpha_subtitle": "3×3 beam + depth-5 database",
        "beta_subtitle": "2×2 experimental solver",
        "alpha_detail": "Automatic 40-move scramble · Beam width 20,000 · Depth 100",
        "beta_detail": "Automatic 20-move scramble · Color-value beam search",
        "ready": "Ready.",
        "ready_play": "Ready to play",
        "ready_prompt": "Press SCRAMBLE to create a new automatic scramble.",
        "orbit": "Drag to orbit  •  Scroll to zoom",
        "scrambling": "Scrambling…",
        "scramble_progress": "Seed {seed}\nAnimating {count} automatic moves.",
        "already_solved": "Already solved",
        "new_game": "Press SCRAMBLE to begin a new game.",
        "solver_running": "Solver process is running in the background.",
        "thinking": "Thinking for {seconds:.1f} seconds…",
        "no_solution": "No solution after {seconds:.1f} seconds",
        "solver_failed": "The heuristic solver did not reach its finish database.",
        "solver_output_error": "Solver output error",
        "solved_in": "Solved in {seconds:.1f} seconds",
        "found_solution": "Found {count} moves. Animating the solution now.",
        "scramble_ready": "Scramble ready",
        "solve_prompt": "Press SOLVE to start the solver and live thinking timer.",
        "cube_solved": "Cube solved",
        "animation_complete": "Animation complete",
        "verified": "Verified solved. Press SCRAMBLE to play again.",
        "returned_failed": "The returned sequence did not solve the displayed cube.",
        "cube_reset": "Cube reset to solved.",
    },
    "zh": {
        "settings": "⚙  设置",
        "settings_title": "设置",
        "language": "界面语言",
        "apply": "应用",
        "cancel": "取消",
        "scramble": "打乱",
        "solve": "求解",
        "reset": "重置魔方",
        "solver_status": "求解器状态",
        "command": "运行命令",
        "alpha_subtitle": "3×3 束搜索与五步数据库求解器",
        "beta_subtitle": "2×2 实验性求解器",
        "alpha_detail": "自动打乱 40 步 · 束宽 20,000 · 深度 100",
        "beta_detail": "自动打乱 20 步 · 颜色评分束搜索",
        "ready": "准备就绪。",
        "ready_play": "可以开始",
        "ready_prompt": "点击“打乱”生成新的自动打乱。",
        "orbit": "拖动旋转视角  •  滚轮缩放",
        "scrambling": "正在打乱…",
        "scramble_progress": "随机种子 {seed}\n正在播放 {count} 步自动打乱。",
        "already_solved": "魔方已经复原",
        "new_game": "点击“打乱”开始新游戏。",
        "solver_running": "求解器正在后台运行。",
        "thinking": "已思考 {seconds:.1f} 秒…",
        "no_solution": "思考 {seconds:.1f} 秒后仍未找到解法",
        "solver_failed": "启发式求解器未能到达最终数据库。",
        "solver_output_error": "求解器输出错误",
        "solved_in": "用时 {seconds:.1f} 秒找到解法",
        "found_solution": "找到 {count} 步解法，正在播放。",
        "scramble_ready": "打乱完成",
        "solve_prompt": "点击“求解”启动求解器和实时计时。",
        "cube_solved": "魔方已复原",
        "animation_complete": "动画播放完成",
        "verified": "已验证复原。点击“打乱”再次开始。",
        "returned_failed": "返回的步骤未能复原画面中的魔方。",
        "cube_reset": "魔方已重置为复原状态。",
    },
}


def add_vectors(*vectors: Vec3) -> Vec3:
    return tuple(sum(parts) for parts in zip(*vectors))  # type: ignore[return-value]


def scale_vector(vector: Vec3, scale: float) -> Vec3:
    return tuple(component * scale for component in vector)  # type: ignore[return-value]


def dot(left: Vec3, right: Vec3) -> float:
    return sum(a * b for a, b in zip(left, right))


def cross(left: Vec3, right: Vec3) -> Vec3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def rotate_around_axis(point: Vec3, axis: Vec3, angle: float) -> Vec3:
    radians = math.radians(angle)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    crossed = cross(axis, point)
    parallel = dot(axis, point) * (1.0 - cosine)
    return (
        point[0] * cosine + crossed[0] * sine + axis[0] * parallel,
        point[1] * cosine + crossed[1] * sine + axis[1] * parallel,
        point[2] * cosine + crossed[2] * sine + axis[2] * parallel,
    )


def parse_solution_sequence(output: str) -> list[str]:
    for line in output.splitlines():
        if line.strip().lower().startswith("solution sequence:"):
            sequence = line.split(":", 1)[1].strip()
            if sequence == "(already solved)":
                return []
            return sequence.split()
    raise ValueError("The solver output did not contain a solution sequence.")


class BrowserTab(tk.Canvas):
    """A compact browser-style tab with rounded upper corners."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        icon_grid: int | None = None,
        icon_image: tk.PhotoImage | None = None,
    ) -> None:
        super().__init__(
            parent,
            width=210,
            height=60,
            background=NAVY,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )
        self.tab_text = text
        self.tab_command = command
        self.icon_grid = icon_grid
        self.icon_image = icon_image
        self.active = False
        self.enabled = True
        self.bind("<Configure>", lambda _event: self.draw_tab())
        self.bind("<Button-1>", self.activate)
        self.draw_tab()

    def activate(self, _event: tk.Event) -> None:
        if self.enabled:
            self.tab_command()

    def set_active(self, active: bool) -> None:
        self.active = active
        self.draw_tab()

    def set_text(self, text: str) -> None:
        self.tab_text = text
        self.draw_tab()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.draw_tab()

    def draw_tab(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 210)
        height = max(self.winfo_height(), 60)
        radius = 14
        fill = CARD if (self.active or self.icon_image is not None) else NAVY_LIGHT

        self.create_rectangle(
            radius, 0, width - radius, height, fill=fill, outline=""
        )
        self.create_rectangle(
            0, radius, width, height, fill=fill, outline=""
        )
        self.create_arc(
            0, 0, radius * 2, radius * 2,
            start=90, extent=90, fill=fill, outline="",
        )
        self.create_arc(
            width - radius * 2, 0, width, radius * 2,
            start=0, extent=90, fill=fill, outline="",
        )
        if self.active:
            self.create_line(
                10, height - 2, width - 10, height - 2,
                fill=BLUE, width=3,
            )
        else:
            self.create_line(
                0, height - 1, width, height - 1, fill="#c4cbd7"
            )
        text_x = width / 2
        if self.icon_image is not None:
            self.create_image(
                12,
                height / 2,
                image=self.icon_image,
                anchor="w",
            )
            text_x = 64 + (width - 64) / 2
        elif self.icon_grid is not None:
            icon_size = 38.0
            icon_x = 14.0
            icon_y = (height - icon_size) / 2.0
            gap = 1.5
            cell = (icon_size - gap * (self.icon_grid - 1)) / self.icon_grid
            icon_color = BLUE if self.icon_grid == 3 else ORANGE
            self.create_rectangle(
                icon_x - 2,
                icon_y - 2,
                icon_x + icon_size + 2,
                icon_y + icon_size + 2,
                fill="#111827",
                outline="",
            )
            for row in range(self.icon_grid):
                for column in range(self.icon_grid):
                    left = icon_x + column * (cell + gap)
                    top = icon_y + row * (cell + gap)
                    self.create_rectangle(
                        left,
                        top,
                        left + cell,
                        top + cell,
                        fill=icon_color,
                        outline="#111827",
                        width=1,
                    )
            text_x = 58 + (width - 58) / 2

        self.create_text(
            text_x,
            height / 2 + 1,
            text=self.tab_text,
            fill=TEXT if self.enabled else "#8b93a3",
            font=("TkDefaultFont", 13, "bold"),
        )


class CubeStage(tk.Canvas):
    """Canvas-based animated stage shared by both cube modes."""

    FRAME_MS: Final[int] = 16
    TURN_DURATION_MS: Final[int] = 250

    def __init__(
        self,
        parent: tk.Misc,
        on_queue_finished: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            background="#eef2f7",
            highlightthickness=0,
            cursor="fleur",
        )
        self.on_queue_finished = on_queue_finished
        self.language = "en"
        self.mode = "alpha"
        self.cube: CubeObject = AlphaCube3x3()
        self.yaw = -31.0
        self.pitch = 23.0
        self.zoom = 1.0
        self.drag_start: tuple[int, int] | None = None
        self.queue: list[str] = []
        self.current_move: str | None = None
        self.animation_progress = 0.0
        self.animation_started_at = 0.0
        self.after_id: str | None = None
        self.bind("<Configure>", lambda _event: self.draw())
        self.bind("<ButtonPress-1>", self.start_drag)
        self.bind("<B1-Motion>", self.drag_view)
        self.bind("<MouseWheel>", self.zoom_view)
        self.bind("<Button-4>", lambda _event: self.change_zoom(1.08))
        self.bind("<Button-5>", lambda _event: self.change_zoom(0.92))

    @property
    def animating(self) -> bool:
        return self.current_move is not None or bool(self.queue)

    def set_language(self, language: str) -> None:
        self.language = language
        self.draw()

    def set_cube(self, mode: str, cube: CubeObject) -> None:
        self.cancel_animation()
        self.mode = mode
        self.cube = cube
        self.yaw = -31.0
        self.pitch = 23.0
        self.zoom = 1.0
        self.draw()

    def animate(self, moves: list[str]) -> None:
        if not moves:
            self.on_queue_finished()
            return
        self.queue.extend(moves)
        if self.current_move is None:
            self.start_next_move()

    def cancel_animation(self) -> None:
        if self.after_id is not None:
            try:
                self.after_cancel(self.after_id)
            except tk.TclError:
                pass
        self.after_id = None
        self.queue.clear()
        self.current_move = None
        self.animation_progress = 0.0

    def start_next_move(self) -> None:
        self.after_id = None
        if not self.queue:
            self.current_move = None
            self.animation_progress = 0.0
            self.draw()
            self.on_queue_finished()
            return
        self.current_move = self.queue.pop(0)
        self.animation_progress = 0.0
        self.animation_started_at = time.perf_counter()
        self.run_frame()

    def run_frame(self) -> None:
        if self.current_move is None:
            return
        elapsed_ms = (
            time.perf_counter() - self.animation_started_at
        ) * 1000.0
        linear = min(1.0, elapsed_ms / self.TURN_DURATION_MS)
        self.animation_progress = linear * linear * (3.0 - 2.0 * linear)
        self.draw()
        if linear < 1.0:
            self.after_id = self.after(self.FRAME_MS, self.run_frame)
            return

        completed = self.current_move
        if self.mode == "alpha":
            assert isinstance(self.cube, AlphaCube3x3)
            self.cube.apply_move(completed)
        else:
            assert isinstance(self.cube, BetaCube2x2)
            self.cube.apply_motion(completed)
        self.current_move = None
        self.animation_progress = 0.0
        self.draw()
        self.after_id = self.after(35, self.start_next_move)

    def move_rotation(self) -> tuple[Vec3, float, set[int]]:
        assert self.current_move is not None
        move = self.current_move
        if self.mode == "alpha":
            axis = tuple(
                float(value) for value in ALPHA_FACE_NORMALS[move[0]]
            )
            if move.endswith("2"):
                target_angle = -180.0
            elif move.endswith("'"):
                target_angle = 90.0
            else:
                target_angle = -90.0
            cardinal_axis = ALPHA_FACE_NORMALS[move[0]]
            affected = {
                index + 1
                for index, (coordinate, _normal) in enumerate(
                    ALPHA_FACELET_DESCRIPTORS
                )
                if sum(
                    left * right
                    for left, right in zip(coordinate, cardinal_axis)
                )
                == 1
            }
            return axis, target_angle, affected  # type: ignore[return-value]

        axis, target_angle = BETA_ROTATIONS[move]
        affected = {
            position
            for cycle in BETA_MOTIONS[move]
            for position in cycle
        }
        return axis, target_angle, affected

    def color_at(self, position: int) -> int:
        if self.mode == "alpha":
            assert isinstance(self.cube, AlphaCube3x3)
            return self.cube.state[position - 1]
        assert isinstance(self.cube, BetaCube2x2)
        return self.cube.get_color(position)

    def face_positions(self) -> dict[str, tuple[int, ...]]:
        return (
            ALPHA_FACE_POSITIONS
            if self.mode == "alpha"
            else BETA_FACE_POSITIONS
        )

    def cell_bounds(self) -> tuple[tuple[float, float], ...]:
        return ALPHA_CELL_BOUNDS if self.mode == "alpha" else BETA_CELL_BOUNDS

    def rotate_view(self, point: Vec3) -> Vec3:
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        x1 = point[0] * cos_yaw + point[2] * sin_yaw
        z1 = -point[0] * sin_yaw + point[2] * cos_yaw
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        return (
            x1,
            point[1] * cos_pitch - z1 * sin_pitch,
            point[1] * sin_pitch + z1 * cos_pitch,
        )

    def project(self, point: Vec3) -> tuple[float, float]:
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        rotated = self.rotate_view(point)
        camera_distance = 9.0
        perspective = camera_distance / (camera_distance - rotated[2])
        scale = min(width, height) * 0.135 * self.zoom
        return (
            width / 2 + rotated[0] * scale * perspective,
            height / 2 - rotated[1] * scale * perspective,
        )

    @staticmethod
    def square(
        normal: Vec3,
        right: Vec3,
        down: Vec3,
        distance: float,
        left: float,
        top: float,
        right_edge: float,
        bottom: float,
    ) -> tuple[Vec3, Vec3, Vec3, Vec3]:
        center = scale_vector(normal, distance)

        def point(horizontal: float, vertical: float) -> Vec3:
            return add_vectors(
                center,
                scale_vector(right, horizontal),
                scale_vector(down, vertical),
            )

        return (
            point(left, top),
            point(right_edge, top),
            point(right_edge, bottom),
            point(left, bottom),
        )

    def draw(self) -> None:
        self.delete("all")
        rotating: set[int] = set()
        axis: Vec3 = (0.0, 0.0, 1.0)
        angle = 0.0
        if self.current_move is not None:
            axis, target, rotating = self.move_rotation()
            angle = target * self.animation_progress

        primitives: list[
            tuple[
                int,
                float,
                tuple[Vec3, Vec3, Vec3, Vec3],
                int | None,
            ]
        ] = []
        positions_by_face = self.face_positions()
        bounds = self.cell_bounds()
        grid_size = 3 if self.mode == "alpha" else 2

        for face, (normal, right, down) in FACE_VECTORS.items():
            if self.rotate_view(normal)[2] > 0.015:
                body = self.square(
                    normal,
                    right,
                    down,
                    1.5,
                    -1.53,
                    -1.53,
                    1.53,
                    1.53,
                )
                body_depth = (
                    sum(self.rotate_view(point)[2] for point in body) / 4
                )
                primitives.append((0, body_depth, body, None))

            for local_index, position in enumerate(positions_by_face[face]):
                row, column = divmod(local_index, grid_size)
                left, right_edge = bounds[column]
                top, bottom = bounds[row]
                sticker = self.square(
                    normal,
                    right,
                    down,
                    1.518,
                    left,
                    top,
                    right_edge,
                    bottom,
                )
                display_normal = normal
                if position in rotating:
                    sticker = tuple(
                        rotate_around_axis(point, axis, angle)
                        for point in sticker
                    )  # type: ignore[assignment]
                    display_normal = rotate_around_axis(normal, axis, angle)
                if self.rotate_view(display_normal)[2] <= 0.015:
                    continue
                sticker_depth = (
                    sum(self.rotate_view(point)[2] for point in sticker) / 4
                )
                primitives.append(
                    (1, sticker_depth, sticker, self.color_at(position))
                )

        primitives.sort(key=lambda item: (item[0], item[1]))
        for layer, _depth, vertices, color in primitives:
            projected = [self.project(point) for point in vertices]
            flat = [coordinate for point in projected for coordinate in point]
            if layer == 0:
                self.create_polygon(
                    flat,
                    fill="#080a0f",
                    outline="#020306",
                    width=3,
                )
            else:
                assert color is not None
                self.create_polygon(
                    flat,
                    fill=COLOR_HEX[color],
                    outline="#080b12",
                    width=2,
                    joinstyle=tk.ROUND,
                )

        mode_label = "ALPHACUBE · 3×3" if self.mode == "alpha" else "BETACUBE · 2×2"
        self.create_text(
            24,
            22,
            anchor="nw",
            text=mode_label,
            fill="#000000",
            font=("TkDefaultFont", 16, "bold"),
        )
        self.create_text(
            24,
            51,
            anchor="nw",
            text=TRANSLATIONS[self.language]["orbit"],
            fill="#374151",
            font=("TkDefaultFont", 10),
        )

    def start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x, event.y)

    def drag_view(self, event: tk.Event) -> None:
        if self.drag_start is None:
            self.drag_start = (event.x, event.y)
            return
        previous_x, previous_y = self.drag_start
        self.yaw += (event.x - previous_x) * 0.55
        self.pitch -= (event.y - previous_y) * 0.55
        self.pitch = max(-89.0, min(89.0, self.pitch))
        self.drag_start = (event.x, event.y)
        self.draw()

    def zoom_view(self, event: tk.Event) -> None:
        self.change_zoom(1.08 if event.delta > 0 else 0.92)

    def change_zoom(self, factor: float) -> None:
        self.zoom = max(0.55, min(1.75, self.zoom * factor))
        self.draw()


class CubeZeroGame:
    """Main splash screen and two-tab game controller."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CubeZero")
        self.root.geometry("1320x840")
        self.root.minsize(1040, 700)
        self.root.configure(background=BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.alpha_cube = AlphaCube3x3()
        self.beta_cube = BetaCube2x2()
        self.active_mode = "alpha"
        self.language = "en"
        self.last_scramble: dict[str, list[str]] = {
            "alpha": [],
            "beta": [],
        }
        self.animation_purpose = ""
        self.solver_running = False
        self.solver_mode = ""
        self.solver_started_at = 0.0
        self.solver_process: subprocess.Popen[str] | None = None
        self.timer_after_id: str | None = None
        self.splash_typing_after_id: str | None = None

        self.logo_original: tk.PhotoImage | None = None
        self.logo_splash: tk.PhotoImage | None = None
        self.logo_small: tk.PhotoImage | None = None
        self.alpha_tab_icon_source: tk.PhotoImage | None = None
        self.beta_tab_icon_source: tk.PhotoImage | None = None
        self.alpha_tab_icon: tk.PhotoImage | None = None
        self.beta_tab_icon: tk.PhotoImage | None = None

        self.status_var = tk.StringVar(value=self.t("ready"))
        self.thinking_var = tk.StringVar(value=self.t("ready_play"))
        self.detail_var = tk.StringVar(value="")
        self.command_var = tk.StringVar(value="")

        self.show_splash()

    def clear_root(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()

    def t(self, key: str, **values: Any) -> str:
        return TRANSLATIONS[self.language][key].format(**values)

    def load_logo(self) -> None:
        if self.logo_original is not None:
            return
        try:
            self.logo_original = tk.PhotoImage(file=LOGO_PATH)
            self.logo_splash = self.logo_original.subsample(2, 2)
            self.logo_small = self.logo_original.subsample(14, 14)
        except tk.TclError:
            self.logo_original = None

        try:
            self.alpha_tab_icon_source = tk.PhotoImage(
                file=ALPHA_TAB_ICON_PATH
            )
            self.alpha_tab_icon = self.alpha_tab_icon_source.subsample(7, 7)
        except tk.TclError:
            self.alpha_tab_icon_source = None
            self.alpha_tab_icon = None

        try:
            self.beta_tab_icon_source = tk.PhotoImage(
                file=BETA_TAB_ICON_PATH
            )
            self.beta_tab_icon = self.beta_tab_icon_source.subsample(10, 10)
        except tk.TclError:
            self.beta_tab_icon_source = None
            self.beta_tab_icon = None

    def show_splash(self) -> None:
        self.clear_root()
        self.load_logo()
        splash = tk.Frame(self.root, background=LOGO_BACKGROUND)
        self.splash_frame = splash
        splash.pack(fill="both", expand=True)

        center = tk.Frame(splash, background=LOGO_BACKGROUND)
        center.place(relx=0.5, rely=0.48, anchor="center")
        if self.logo_splash is not None:
            tk.Label(
                center,
                image=self.logo_splash,
                background=LOGO_BACKGROUND,
                borderwidth=0,
            ).pack()
        else:
            tk.Label(
                center,
                text="CUBEZERO",
                foreground=BLUE,
                background=LOGO_BACKGROUND,
                font=("TkDefaultFont", 54, "bold"),
            ).pack(pady=(0, 30))

        self.splash_text_label = tk.Label(
            center,
            text="",
            foreground=TEXT,
            background=LOGO_BACKGROUND,
            font=("TkDefaultFont", 18, "bold"),
        )
        self.splash_text_label.pack(pady=(6, 8))
        self.animate_splash_text(0)

        tk.Label(
            splash,
            text="ALPHACUBE 3×3  ·  BETACUBE 2×2",
            foreground="#9aa3b5",
            background=LOGO_BACKGROUND,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="bottom", pady=22)

    def animate_splash_text(self, index: int) -> None:
        phrase = "Think big, start small."
        if not self.splash_text_label.winfo_exists():
            return
        if index <= len(phrase):
            cursor = "│" if index < len(phrase) else ""
            self.splash_text_label.configure(
                text=phrase[:index] + cursor
            )
            delay = 130 if index and phrase[index - 1] in ",." else 72
            self.splash_typing_after_id = self.root.after(
                delay,
                lambda: self.animate_splash_text(index + 1),
            )
            return
        self.splash_typing_after_id = self.root.after(900, self.start_page_turn)

    def start_page_turn(self) -> None:
        self.splash_typing_after_id = None
        self.root.update_idletasks()
        self.page_width = max(self.root.winfo_width(), 1)
        self.page_height = max(self.root.winfo_height(), 1)

        # Build the game underneath the intro page before the turn begins.
        self.splash_frame.pack_forget()
        self.splash_frame.place(
            x=0,
            y=0,
            anchor="nw",
            width=self.page_width,
            height=self.page_height,
        )
        self.show_game(keep_splash=True)
        self.root.update_idletasks()
        self.splash_frame.lift()

        self.page_shadow = tk.Frame(self.root, background="#768195")
        self.page_shadow.place(
            x=self.page_width - 8,
            y=0,
            width=16,
            height=self.page_height,
        )
        self.page_shadow.lift()
        self.animate_page_turn(0)

    def animate_page_turn(self, frame: int) -> None:
        total_frames = 36
        progress = min(1.0, frame / total_frames)
        eased = 0.5 - 0.5 * math.cos(math.pi * progress)
        page_width = max(1, int(self.page_width * (1.0 - eased)))
        shadow_width = max(3, int(8 + 20 * math.sin(math.pi * progress)))

        self.splash_frame.place_configure(width=page_width)
        self.page_shadow.place_configure(
            x=max(0, page_width - shadow_width),
            width=shadow_width,
        )
        self.splash_frame.lift()
        self.page_shadow.lift()

        if frame < total_frames:
            self.root.after(25, lambda: self.animate_page_turn(frame + 1))
            return

        self.page_shadow.destroy()
        self.splash_frame.destroy()
        self.root.configure(background=BACKGROUND)

    def show_game(self, keep_splash: bool = False) -> None:
        self.splash_typing_after_id = None
        if not keep_splash:
            self.clear_root()
        shell = tk.Frame(self.root, background=BACKGROUND)
        self.game_shell = shell
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        topbar = tk.Frame(shell, background=NAVY, height=70)
        topbar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        topbar.grid_propagate(False)
        tabs = tk.Frame(topbar, background=NAVY)
        tabs.pack(side="left", fill="y", padx=(4, 0))
        self.alpha_tab = BrowserTab(
            tabs,
            text="AlphaCube  ·  3×3",
            command=lambda: self.switch_mode("alpha"),
            icon_grid=3,
            icon_image=self.alpha_tab_icon,
        )
        self.alpha_tab.pack(side="left", pady=(10, 0), padx=(0, 4))
        self.beta_tab = BrowserTab(
            tabs,
            text="BetaCube  ·  2×2",
            command=lambda: self.switch_mode("beta"),
            icon_grid=2,
            icon_image=self.beta_tab_icon,
        )
        self.beta_tab.pack(side="left", pady=(10, 0))

        self.settings_button = BrowserTab(
            tabs,
            text=self.t("settings"),
            command=self.open_settings,
        )
        self.settings_button.pack(
            side="left", pady=(10, 0), padx=(4, 0)
        )

        sidebar = tk.Frame(
            shell,
            background=CARD,
            width=330,
            highlightbackground=LINE,
            highlightthickness=1,
        )
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(12, weight=1)

        self.mode_title = tk.Label(
            sidebar,
            text="AlphaCube",
            foreground=TEXT,
            background=CARD,
            font=("TkDefaultFont", 24, "bold"),
        )
        self.mode_title.grid(row=0, column=0, sticky="w", padx=24, pady=(28, 0))
        self.mode_subtitle = tk.Label(
            sidebar,
            text="3×3 beam + database solver",
            foreground=MUTED,
            background=CARD,
            font=("TkDefaultFont", 11),
        )
        self.mode_subtitle.grid(
            row=1,
            column=0,
            sticky="w",
            padx=24,
            pady=(3, 24),
        )

        self.scramble_button = self.sidebar_button(
            sidebar,
            self.t("scramble"),
            self.scramble,
            GREEN,
            row=2,
        )
        self.solve_button = self.sidebar_button(
            sidebar,
            self.t("solve"),
            self.solve,
            BLUE,
            row=3,
        )
        self.reset_button = self.sidebar_button(
            sidebar,
            self.t("reset"),
            self.reset_cube,
            "#e8ecf3",
            row=4,
            foreground=TEXT,
        )

        tk.Frame(sidebar, background=LINE, height=1).grid(
            row=5,
            column=0,
            sticky="ew",
            padx=24,
            pady=22,
        )
        self.solver_status_heading = tk.Label(
            sidebar,
            text=self.t("solver_status"),
            foreground=MUTED,
            background=CARD,
            font=("TkDefaultFont", 9, "bold"),
        )
        self.solver_status_heading.grid(
            row=6, column=0, sticky="w", padx=24
        )
        self.thinking_label = tk.Label(
            sidebar,
            textvariable=self.thinking_var,
            foreground=BLUE,
            background=CARD,
            wraplength=280,
            justify="left",
            font=("TkDefaultFont", 17, "bold"),
        )
        self.thinking_label.grid(
            row=7,
            column=0,
            sticky="w",
            padx=24,
            pady=(8, 5),
        )
        tk.Label(
            sidebar,
            textvariable=self.detail_var,
            foreground=MUTED,
            background=CARD,
            wraplength=280,
            justify="left",
            font=("TkDefaultFont", 10),
        ).grid(row=8, column=0, sticky="w", padx=24)

        self.command_heading = tk.Label(
            sidebar,
            text=self.t("command"),
            foreground=MUTED,
            background=CARD,
            font=("TkDefaultFont", 9, "bold"),
        )
        self.command_heading.grid(
            row=9,
            column=0,
            sticky="w",
            padx=24,
            pady=(22, 5),
        )
        tk.Label(
            sidebar,
            textvariable=self.command_var,
            foreground="#3f4b61",
            background="#f3f5f9",
            wraplength=270,
            justify="left",
            font=("TkFixedFont", 9),
            padx=10,
            pady=9,
        ).grid(row=10, column=0, sticky="ew", padx=24)

        tk.Label(
            sidebar,
            textvariable=self.status_var,
            foreground=TEXT,
            background="#f3f5f9",
            wraplength=270,
            justify="left",
            anchor="nw",
            font=("TkDefaultFont", 10),
            padx=12,
            pady=12,
        ).grid(
            row=13,
            column=0,
            sticky="sew",
            padx=24,
            pady=(12, 24),
        )

        stage_holder = tk.Frame(shell, background="#eef2f7")
        stage_holder.grid(
            row=1,
            column=1,
            sticky="nsew",
            padx=(18, 18),
            pady=(0, 18),
        )
        stage_holder.grid_columnconfigure(0, weight=1)
        stage_holder.grid_rowconfigure(0, weight=1)
        self.stage = CubeStage(stage_holder, self.animation_finished)
        self.stage.grid(row=0, column=0, sticky="nsew")
        self.stage.set_cube("alpha", self.alpha_cube)
        self.stage.set_language(self.language)
        self.refresh_language()

    @staticmethod
    def sidebar_button(
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        background: str,
        row: int,
        foreground: str = "#000000",
    ) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            foreground=foreground,
            background=background,
            activeforeground=foreground,
            activebackground=background,
            disabledforeground="#aab1bf",
            relief="flat",
            cursor="hand2",
            font=("TkDefaultFont", 12, "bold"),
            pady=13,
        )
        button.grid(
            row=row,
            column=0,
            sticky="ew",
            padx=24,
            pady=(0, 10),
        )
        return button

    def open_settings(self) -> None:
        if self.solver_running or self.stage.animating:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(self.t("settings_title"))
        dialog.configure(background=CARD)
        dialog.resizable(False, False)
        dialog.transient(self.root)

        panel = tk.Frame(dialog, background=CARD, padx=28, pady=24)
        panel.pack(fill="both", expand=True)
        tk.Label(
            panel,
            text=self.t("settings_title"),
            foreground=TEXT,
            background=CARD,
            font=("TkDefaultFont", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            panel,
            text=self.t("language"),
            foreground=MUTED,
            background=CARD,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", pady=(20, 8))

        selected_language = tk.StringVar(value=self.language)
        for label, value in (("English", "en"), ("简体中文", "zh")):
            tk.Radiobutton(
                panel,
                text=label,
                value=value,
                variable=selected_language,
                foreground=TEXT,
                background=CARD,
                activebackground=CARD,
                selectcolor="#eef2f7",
                font=("TkDefaultFont", 12),
                anchor="w",
            ).pack(fill="x", pady=3)

        actions = tk.Frame(panel, background=CARD)
        actions.pack(fill="x", pady=(24, 0))

        def apply_choice() -> None:
            self.set_language(selected_language.get())
            dialog.destroy()

        tk.Button(
            actions,
            text=self.t("cancel"),
            command=dialog.destroy,
            foreground=TEXT,
            background="#e8ecf3",
            relief="flat",
            padx=16,
            pady=8,
        ).pack(side="right")
        tk.Button(
            actions,
            text=self.t("apply"),
            command=apply_choice,
            foreground=TEXT,
            background=GREEN,
            relief="flat",
            padx=16,
            pady=8,
        ).pack(side="right", padx=(0, 8))

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.grab_set()

    def set_language(self, language: str) -> None:
        if language not in TRANSLATIONS:
            return
        self.language = language
        self.scramble_button.configure(text=self.t("scramble"))
        self.solve_button.configure(text=self.t("solve"))
        self.reset_button.configure(text=self.t("reset"))
        self.solver_status_heading.configure(text=self.t("solver_status"))
        self.command_heading.configure(text=self.t("command"))
        self.settings_button.set_text(self.t("settings"))
        self.stage.set_language(language)
        self.thinking_var.set(self.t("ready_play"))
        self.status_var.set(self.t("ready_prompt"))
        self.refresh_mode_ui()

    def refresh_language(self) -> None:
        self.set_language(self.language)

    def refresh_mode_ui(self) -> None:
        alpha_active = self.active_mode == "alpha"
        self.alpha_tab.set_active(alpha_active)
        self.beta_tab.set_active(not alpha_active)
        if alpha_active:
            self.mode_title.configure(text="AlphaCube")
            self.mode_subtitle.configure(text=self.t("alpha_subtitle"))
            self.detail_var.set(self.t("alpha_detail"))
            self.command_var.set(" ".join(ALPHA_SOLVE_COMMAND))
        else:
            self.mode_title.configure(text="BetaCube")
            self.mode_subtitle.configure(text=self.t("beta_subtitle"))
            self.detail_var.set(self.t("beta_detail"))
            self.command_var.set(" ".join(BETA_SOLVE_COMMAND))

    def switch_mode(self, mode: str) -> None:
        if self.solver_running or self.stage.animating or mode == self.active_mode:
            return
        self.active_mode = mode
        cube: CubeObject = self.alpha_cube if mode == "alpha" else self.beta_cube
        self.stage.set_cube(mode, cube)
        self.thinking_var.set(self.t("ready_play"))
        self.status_var.set(self.t("ready_prompt"))
        self.refresh_mode_ui()

    def set_controls_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in (
            self.scramble_button,
            self.solve_button,
            self.reset_button,
        ):
            button.configure(state=state)
        self.alpha_tab.set_enabled(enabled)
        self.beta_tab.set_enabled(enabled)
        self.settings_button.set_enabled(enabled)

    def scramble(self) -> None:
        if self.solver_running or self.stage.animating:
            return
        seed = secrets.randbits(64)
        random_source = random.Random(seed)
        if self.active_mode == "alpha":
            sequence: list[str] = []
            previous_face: str | None = None
            for _ in range(ALPHA_SCRAMBLE_LENGTH):
                choices = [
                    move
                    for move in ALPHA_MOVE_NAMES
                    if ALPHA_MOVE_FACES[move] != previous_face
                ]
                move = random_source.choice(choices)
                sequence.append(move)
                previous_face = ALPHA_MOVE_FACES[move]
            target = AlphaCube3x3()
            target.apply_sequence(sequence)
            payload = target.to_json_dict()
            payload.update(
                {
                    "format": "3x3-rubiks-cube-scramble",
                    "seed": seed,
                    "scramble_length": len(sequence),
                    "scramble_sequence": sequence,
                }
            )
            ALPHA_DATA.mkdir(parents=True, exist_ok=True)
            (ALPHA_DATA / "scrambled_state.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            self.alpha_cube.reset()
        else:
            sequence = []
            previous_move: str | None = None
            for _ in range(BETA_SCRAMBLE_LENGTH):
                choices = [
                    move
                    for move in BETA_MOTIONS
                    if previous_move is None
                    or move != BETA_INVERSES[previous_move]
                ]
                move = random_source.choice(choices)
                sequence.append(move)
                previous_move = move
            target = BetaCube2x2()
            target.apply_sequence(sequence)
            payload = {
                "format": "2x2-rubiks-cube-scramble",
                "version": 1,
                "seed": seed,
                "scramble_length": len(sequence),
                "scramble_sequence": sequence,
                "stickers": [
                    {"position": position, "color": color}
                    for position, color in target.as_pairs()
                ],
            }
            BETA_SOLVER.mkdir(parents=True, exist_ok=True)
            (BETA_SOLVER / "scrambled_state.json").write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            self.beta_cube.reset()

        self.last_scramble[self.active_mode] = sequence
        self.animation_purpose = "scramble"
        self.thinking_var.set(self.t("scrambling"))
        self.status_var.set(
            self.t("scramble_progress", seed=seed, count=len(sequence))
        )
        self.set_controls_enabled(False)
        self.stage.animate(sequence)

    def current_cube_solved(self) -> bool:
        return (
            self.alpha_cube.is_solved()
            if self.active_mode == "alpha"
            else self.beta_cube.is_solved()
        )

    def solve(self) -> None:
        if self.solver_running or self.stage.animating:
            return
        if self.current_cube_solved():
            self.thinking_var.set(self.t("already_solved"))
            self.status_var.set(self.t("new_game"))
            return

        command = (
            ALPHA_SOLVE_COMMAND
            if self.active_mode == "alpha"
            else BETA_SOLVE_COMMAND
        )
        self.solver_running = True
        self.solver_mode = self.active_mode
        self.solver_started_at = time.perf_counter()
        self.animation_purpose = ""
        self.command_var.set(" ".join(command))
        self.status_var.set(self.t("solver_running"))
        self.set_controls_enabled(False)
        self.update_thinking_timer()

        threading.Thread(
            target=self.run_solver_process,
            args=(command, self.solver_mode),
            daemon=True,
        ).start()

    def update_thinking_timer(self) -> None:
        if not self.solver_running:
            return
        elapsed = time.perf_counter() - self.solver_started_at
        self.thinking_var.set(self.t("thinking", seconds=elapsed))
        self.timer_after_id = self.root.after(
            100,
            self.update_thinking_timer,
        )

    def run_solver_process(
        self,
        command: tuple[str, ...],
        mode: str,
    ) -> None:
        try:
            self.solver_process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = self.solver_process.communicate()
            return_code = self.solver_process.returncode
        except OSError as error:
            stdout = ""
            stderr = str(error)
            return_code = -1
        self.root.after(
            0,
            lambda: self.solver_finished(
                mode,
                return_code,
                stdout,
                stderr,
            ),
        )

    def solver_finished(
        self,
        mode: str,
        return_code: int,
        stdout: str,
        stderr: str,
    ) -> None:
        elapsed = time.perf_counter() - self.solver_started_at
        self.solver_running = False
        self.solver_process = None
        if self.timer_after_id is not None:
            try:
                self.root.after_cancel(self.timer_after_id)
            except tk.TclError:
                pass
            self.timer_after_id = None

        if mode != self.active_mode:
            self.set_controls_enabled(True)
            return
        if return_code != 0:
            self.thinking_var.set(self.t("no_solution", seconds=elapsed))
            diagnostic = stderr.strip() or "\n".join(stdout.splitlines()[-4:])
            self.status_var.set(
                self.t("solver_failed")
                + (f"\n\n{diagnostic}" if diagnostic else "")
            )
            self.set_controls_enabled(True)
            return

        try:
            solution = parse_solution_sequence(stdout)
        except ValueError as error:
            self.thinking_var.set(self.t("solver_output_error"))
            self.status_var.set(str(error))
            self.set_controls_enabled(True)
            return

        self.thinking_var.set(self.t("solved_in", seconds=elapsed))
        self.status_var.set(
            self.t("found_solution", count=len(solution))
        )
        self.animation_purpose = "solution"
        if solution:
            self.stage.animate(solution)
        else:
            self.animation_finished()

    def animation_finished(self) -> None:
        purpose = self.animation_purpose
        self.animation_purpose = ""
        if purpose == "scramble":
            self.thinking_var.set(self.t("scramble_ready"))
            self.status_var.set(self.t("solve_prompt"))
        elif purpose == "solution":
            solved = self.current_cube_solved()
            self.thinking_var.set(
                self.t("cube_solved")
                if solved
                else self.t("animation_complete")
            )
            self.status_var.set(
                self.t("verified")
                if solved
                else self.t("returned_failed")
            )
        self.set_controls_enabled(True)

    def reset_cube(self) -> None:
        if self.solver_running:
            return
        self.stage.cancel_animation()
        if self.active_mode == "alpha":
            self.alpha_cube.reset()
        else:
            self.beta_cube.reset()
        self.last_scramble[self.active_mode] = []
        self.animation_purpose = ""
        self.thinking_var.set(self.t("ready_play"))
        self.status_var.set(self.t("cube_reset"))
        self.stage.draw()
        self.set_controls_enabled(True)

    def close(self) -> None:
        if self.solver_process is not None and self.solver_process.poll() is None:
            self.solver_process.terminate()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    CubeZeroGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
