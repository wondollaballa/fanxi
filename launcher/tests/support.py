"""Add the launcher package to sys.path for the tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "launcher"
if str(LAUNCHER) not in sys.path:
    sys.path.insert(0, str(LAUNCHER))
