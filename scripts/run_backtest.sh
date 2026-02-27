#!/bin/bash
# Helper script to run backtest with correct environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Path to virtual environment python
PYTHON_EXEC="$PROJECT_ROOT/.venv/bin/python"

# Check if venv exists
if [ ! -f "$PYTHON_EXEC" ]; then
    echo "❌ Virtual environment not found at $PROJECT_ROOT/.venv"
    echo "Please run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Run the backtest command
# Passes all arguments to the CLI
echo "🚀 Running SniperSight Backtest..."
"$PYTHON_EXEC" -m backend.cli backtest "$@"
