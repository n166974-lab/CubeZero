# CubeZero

**CubeZero** is an algorithm-based Rubik's Cube solver designed to solve both the **3×3×3** and **2×2×2** Rubik's Cubes.

## Getting Started

### AlphaCube — 3×3×3

1. Navigate to:

   ```text
   AlphaCube/tools/scrambler.py
   ```

2. Run `scrambler.py` to generate a new scrambled cube state. The generated state will be saved to:

   ```text
   AlphaCube/data/scrambled_state.json
   ```

3. Navigate to:

   ```text
   AlphaCube/tools/beam_database_solver.py
   ```

4. Run `beam_database_solver.py` to solve the scrambled cube:

 ```text
   python3 "AlphaCube/tools/beam_database_solver.py" \
  --beam-width 20000 \
  --depth 100
  ```

### BetaCube — 2×2×2

1. Navigate to:

   ```text
   BetaCube/Solver/scrambler.py
   ```

2. Run `scrambler.py` to generate a new scrambled cube state. The generated state will be saved to:

   ```text
   BetaCube/Solver/scrambled_state.json
   ```

3. Navigate to:

   ```text
   BetaCube/Solver/color_evaluation_solver.py
   ```

4. Run `color_evaluation_solver.py` to solve the scrambled cube.

## Project Structure

| Folder      | Description                                                       |
| ----------- | ----------------------------------------------------------------- |
| `AlphaCube` | Core algorithms and setup for solving the **3×3×3 Rubik's Cube**. |
| `BetaCube`  | Core algorithms and setup for solving the **2×2×2 Rubik's Cube**. |

## How does it Work

https://docs.google.com/document/d/1r_lkJdez0JtvTfN2Ho2z_Eb2aMEn3r4ieiU4jmYbCEs/edit?usp=sharing




