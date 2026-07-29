#!/bin/zsh

cd -- "$(dirname -- "$0")"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "CubeZero's local Python environment is missing."
  echo "Create it with: /opt/homebrew/bin/python3.11 -m venv .venv"
  echo "Then install: .venv/bin/python -m pip install -r requirements.txt"
  read -r "?Press Return to close..."
  exit 1
fi

exec ".venv/bin/python" "app.py"
