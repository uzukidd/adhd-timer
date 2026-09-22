#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

if [[ -x /d/miniconda3/Scripts/conda.exe ]]; then
  CONDA_EXE=/d/miniconda3/Scripts/conda.exe
elif [[ -f /mnt/d/miniconda3/Scripts/conda.exe ]]; then
  CONDA_EXE=/mnt/d/miniconda3/Scripts/conda.exe
else
  CONDA_EXE="$(command -v conda)"
fi

"$CONDA_EXE" run -n adhd-timer python -m focus_flow.app
