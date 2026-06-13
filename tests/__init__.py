from __future__ import annotations

from pathlib import Path

TST_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TST_ROOT.parent
SRC_ROOT = REPO_ROOT / "src"

SRC_DIRS = [
    REPO_ROOT / "scripts",
    REPO_ROOT / "tests",
    SRC_ROOT / "spellbot",
]
