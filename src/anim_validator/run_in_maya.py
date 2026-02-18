# src/anim_validator/run_in_maya.py
from __future__ import annotations

import sys
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parents[1]  # .../src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from anim_validator.app import show  # noqa: E402


def run():
    return show()
