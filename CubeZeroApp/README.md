# CubeZero 3D

CubeZero 3D replaces the original Tkinter polygon renderer with a
GPU-accelerated Three.js scene while retaining the existing Python cube
models, scramble files, and solver commands.

## Start on macOS

Double-click `run_cubezero.command`, or run:

```bash
cd "/Users/jackson/Documents/CubeZero/CubeZeroApp"
./run_cubezero.command
```

## Start on Windows

Keep `AlphaCube`, `BetaCube`, and `CubeZeroApp` together inside the same
`CubeZero` folder. Then double-click:

```text
run_cubezero_windows.bat
```

On its first run, the launcher:

1. Finds Python using `py -3` or `python`.
2. Creates a Windows-only environment named `.venv-windows`.
3. Installs the packages from `requirements.txt`.
4. Opens CubeZero.

Python 3.11 or newer is recommended. Windows 11 normally includes the
Microsoft Edge WebView2 runtime needed by pywebview. The macOS `.venv` folder
is ignored by the Windows launcher.

## Folder structure

```text
CubeZero/
├── AlphaCube/       3×3 model, database, and solver
├── BetaCube/        2×2 model and solver
└── CubeZeroApp/     Game interface and everything it needs to run
    ├── app.py
    ├── run_cubezero.command
    ├── run_cubezero_windows.bat
    ├── requirements.txt
    ├── web/
    ├── .venv/
    ├── .venv-windows/  created automatically on Windows
    └── legacy/
```

## Renderer

- AlphaCube uses 26 rounded, independently animated cubies.
- BetaCube uses eight rounded, independently animated cubies.
- Sticker meshes move with their cubies during every layer rotation.
- The scene includes perspective projection, antialiasing, soft shadows,
  physical lighting, orbit controls, and scroll zoom.
- Scramble and solution animations use the existing Python move sequences.

## Solver bridge

The AlphaCube Solve button uses these unchanged solver settings:

```text
AlphaCube/tools/beam_database_solver.py --beam-width 20000 --depth 100
```

It runs with `python3` on macOS and the active Windows Python environment on
Windows. The backend uses pywebview's local JavaScript bridge. Three.js is
stored locally in `web/node_modules`, so the renderer does not depend on a CDN
while the game is running.

The earlier Tkinter viewer is preserved in `legacy/` as a fallback.
