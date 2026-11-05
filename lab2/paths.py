"""Repository paths independent of the terminal working directory."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
