# 3×3 beam/database solver

## Folder layout

```text
3X3/
├── core/
│   ├── cube_3x3.py
│   └── motion_database_3x3.py
├── tools/
│   ├── scrambler.py
│   ├── beam_database_solver.py
│   ├── generate_depth5_database.py
│   └── rubiks_3d_viewer.py
├── data/
│   ├── solved_cube.json
│   ├── scrambled_state.json
│   └── depth5_database.pkl
└── README.md
```

## Normal workflow

From the main `2X2 cube solver` folder, create a scramble:

```bash
python3 3X3/tools/scrambler.py
```

Run the beam_database solver:

```bash
python3 AlphaCube/tools/beam_database_solver.py --beam-width 20000 --depth 100
```

## Animated 3D viewer

Open the viewer with a solved cube:

```bash
python3 3X3/tools/rubiks_3d_viewer.py
```

Open the saved scrambled state immediately:

```bash
python3 3X3/tools/rubiks_3d_viewer.py \
  --state 3X3/data/scrambled_state.json
```

To animate a solver result:

1. Copy either the moves or the complete terminal line beginning with
   `Solution sequence:`.
2. Click **Paste** in the viewer.
3. Click **Apply** or press Return.
4. The viewer animates the moves one at a time.

The viewer accepts all standard moves:

```text
U U' U2  R R' R2  F F' F2
D D' D2  L L' L2  B B' B2
```

Use **Copy input** to copy the sequence currently in the entry field and
**Copy applied sequence** to copy every move that has finished animating.
JSON files can be loaded from or saved to the `data` folder.

Create a repeatable scramble:

```bash
python3 3X3/tools/scrambler.py --moves 10 --seed 123
```

Inspect the cube model:

```bash
python3 3X3/core/cube_3x3.py R U "R'" "U'"
```

## Database maintenance

The depth-5 database is already generated. To replace it:

```bash
python3 3X3/tools/generate_depth5_database.py --force
```

The database finish is exact. The forward color-value beam is heuristic
and is not guaranteed to reach the database for every scramble.



