"""CubeZero Three.js desktop application.

Run from the CubeZeroApp directory with either:

    .venv/bin/python app.py
    .venv-windows\Scripts\python.exe app.py

The browser-based renderer communicates with the existing Python cube
models and solvers through pywebview's local JavaScript bridge.
"""

from __future__ import annotations

import json
import random
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Final


APP_DIRECTORY: Final[Path] = Path(__file__).resolve().parent
PROJECT_ROOT: Final[Path] = APP_DIRECTORY.parent
WEB_DIRECTORY: Final[Path] = APP_DIRECTORY / "web"
ALPHA_DIRECTORY: Final[Path] = PROJECT_ROOT / "AlphaCube"
ALPHA_CORE: Final[Path] = ALPHA_DIRECTORY / "core"
ALPHA_DATA: Final[Path] = ALPHA_DIRECTORY / "data"
BETA_DIRECTORY: Final[Path] = PROJECT_ROOT / "BetaCube"
BETA_SETUP: Final[Path] = BETA_DIRECTORY / "Setup"
BETA_SOLVER: Final[Path] = BETA_DIRECTORY / "Solver"

sys.path.insert(0, str(ALPHA_CORE))
from cube_3x3 import Cube3x3 as AlphaCube3x3  # noqa: E402
from motion_database_3x3 import (  # noqa: E402
    MOVE_FACES as ALPHA_MOVE_FACES,
    MOVE_NAMES as ALPHA_MOVE_NAMES,
)

sys.path.insert(0, str(BETA_SETUP))
from cube_2x2 import Cube2x2 as BetaCube2x2  # noqa: E402
from motion_database import (  # noqa: E402
    INVERSE_MOTIONS as BETA_INVERSES,
    MOTIONS as BETA_MOTIONS,
)


ALPHA_SCRAMBLE_LENGTH: Final[int] = 40
BETA_SCRAMBLE_LENGTH: Final[int] = 20
PYTHON_COMMAND_LABEL: Final[str] = (
    "python" if sys.platform == "win32" else "python3"
)
ALPHA_SOLVE_ARGUMENTS: Final[tuple[str, ...]] = (
    "AlphaCube/tools/beam_database_solver.py",
    "--beam-width",
    "20000",
    "--depth",
    "100",
)
BETA_SOLVE_ARGUMENTS: Final[tuple[str, ...]] = (
    "BetaCube/Solver/color_evaluation_solver.py",
    "--no-fallback",
)
ALPHA_SOLVE_COMMAND: Final[tuple[str, ...]] = (
    sys.executable,
    *ALPHA_SOLVE_ARGUMENTS,
)
BETA_SOLVE_COMMAND: Final[tuple[str, ...]] = (
    sys.executable,
    *BETA_SOLVE_ARGUMENTS,
)
ALPHA_DISPLAY_COMMAND: Final[tuple[str, ...]] = (
    PYTHON_COMMAND_LABEL,
    *ALPHA_SOLVE_ARGUMENTS,
)
BETA_DISPLAY_COMMAND: Final[tuple[str, ...]] = (
    PYTHON_COMMAND_LABEL,
    *BETA_SOLVE_ARGUMENTS,
)


def parse_solution_sequence(output: str) -> list[str]:
    for line in output.splitlines():
        if line.strip().lower().startswith("solution sequence:"):
            sequence = line.split(":", 1)[1].strip()
            if sequence == "(already solved)":
                return []
            return sequence.split()
    raise ValueError("The solver output did not contain a solution sequence.")


class CubeZeroAPI:
    """Thread-safe bridge exposed to the Three.js interface."""

    def __init__(self) -> None:
        self.alpha_cube = AlphaCube3x3()
        self.beta_cube = BetaCube2x2()
        self.lock = threading.RLock()

    @staticmethod
    def _alpha_scramble(random_source: random.Random) -> list[str]:
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
        return sequence

    @staticmethod
    def _beta_scramble(random_source: random.Random) -> list[str]:
        sequence: list[str] = []
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
        return sequence

    def get_config(self) -> dict[str, Any]:
        return {
            "alpha_scramble_length": ALPHA_SCRAMBLE_LENGTH,
            "beta_scramble_length": BETA_SCRAMBLE_LENGTH,
            "alpha_command": " ".join(ALPHA_DISPLAY_COMMAND),
            "beta_command": " ".join(BETA_DISPLAY_COMMAND),
        }

    def reset(self, mode: str) -> dict[str, Any]:
        with self.lock:
            if mode == "alpha":
                self.alpha_cube.reset()
            elif mode == "beta":
                self.beta_cube.reset()
            else:
                raise ValueError(f"Unknown cube mode: {mode}")
        return {"ok": True, "mode": mode}

    def scramble(self, mode: str) -> dict[str, Any]:
        seed = secrets.randbits(64)
        random_source = random.Random(seed)

        with self.lock:
            if mode == "alpha":
                sequence = self._alpha_scramble(random_source)
                self.alpha_cube.reset()
                self.alpha_cube.apply_sequence(sequence)
                payload = self.alpha_cube.to_json_dict()
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
                colors = self.alpha_cube.as_list()
            elif mode == "beta":
                sequence = self._beta_scramble(random_source)
                self.beta_cube.reset()
                self.beta_cube.apply_sequence(sequence)
                payload = {
                    "format": "2x2-rubiks-cube-scramble",
                    "version": 1,
                    "seed": seed,
                    "scramble_length": len(sequence),
                    "scramble_sequence": sequence,
                    "stickers": [
                        {"position": position, "color": color}
                        for position, color in self.beta_cube.as_pairs()
                    ],
                }
                BETA_SOLVER.mkdir(parents=True, exist_ok=True)
                (BETA_SOLVER / "scrambled_state.json").write_text(
                    json.dumps(payload, indent=2) + "\n",
                    encoding="utf-8",
                )
                colors = [
                    color for _position, color in self.beta_cube.as_pairs()
                ]
            else:
                raise ValueError(f"Unknown cube mode: {mode}")

        return {
            "ok": True,
            "mode": mode,
            "seed": seed,
            "moves": sequence,
            "colors": colors,
        }

    def solve(self, mode: str) -> dict[str, Any]:
        with self.lock:
            cube = self.alpha_cube if mode == "alpha" else self.beta_cube
            if mode not in {"alpha", "beta"}:
                raise ValueError(f"Unknown cube mode: {mode}")
            if cube.is_solved():
                return {
                    "ok": True,
                    "mode": mode,
                    "moves": [],
                    "elapsed": 0.0,
                    "already_solved": True,
                }

            command = (
                ALPHA_SOLVE_COMMAND
                if mode == "alpha"
                else BETA_SOLVE_COMMAND
            )
            started_at = time.perf_counter()
            result = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            elapsed = time.perf_counter() - started_at

            if result.returncode != 0:
                diagnostic = result.stderr.strip() or "\n".join(
                    result.stdout.splitlines()[-5:]
                )
                return {
                    "ok": False,
                    "mode": mode,
                    "elapsed": elapsed,
                    "error": diagnostic or "The solver did not find a solution.",
                    "return_code": result.returncode,
                }

            try:
                solution = parse_solution_sequence(result.stdout)
            except ValueError as error:
                return {
                    "ok": False,
                    "mode": mode,
                    "elapsed": elapsed,
                    "error": str(error),
                    "return_code": result.returncode,
                }

            if mode == "alpha":
                self.alpha_cube.apply_sequence(solution)
                solved = self.alpha_cube.is_solved()
                colors = self.alpha_cube.as_list()
            else:
                self.beta_cube.apply_sequence(solution)
                solved = self.beta_cube.is_solved()
                colors = [
                    color for _position, color in self.beta_cube.as_pairs()
                ]

            if not solved:
                return {
                    "ok": False,
                    "mode": mode,
                    "elapsed": elapsed,
                    "error": "The returned sequence failed verification.",
                }

            return {
                "ok": True,
                "mode": mode,
                "moves": solution,
                "elapsed": elapsed,
                "colors": colors,
                "already_solved": False,
            }


def main() -> None:
    try:
        import webview
    except ImportError as error:
        raise SystemExit(
            "pywebview is not installed. Install the requirements with: "
            "python -m pip install -r requirements.txt"
        ) from error

    index_path = WEB_DIRECTORY / "index.html"
    if not index_path.is_file():
        raise SystemExit(f"Missing web interface: {index_path}")

    api = CubeZeroAPI()
    webview.create_window(
        "CubeZero 3D",
        url=str(index_path),
        js_api=api,
        width=1320,
        height=840,
        min_size=(1040, 700),
        background_color="#eef2f7",
        text_select=False,
    )
    webview.start(
        debug=False,
        http_server=True,
        private_mode=False,
        storage_path=str(APP_DIRECTORY / ".webview"),
    )


if __name__ == "__main__":
    main()
