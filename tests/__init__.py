from __future__ import annotations

from pathlib import Path

CLIENT_TOKEN = "my-token"
CLIENT_AUTH = "my-auth"

TST_ROOT = Path(__file__).resolve().parent
TEST_DATA_ROOT = TST_ROOT / "_test_data"  # some static files used by tests
REPO_ROOT = TST_ROOT.parent
SRC_ROOT = REPO_ROOT / "src"

SRC_DIRS = [
    REPO_ROOT / "scripts",
    REPO_ROOT / "tests",
    SRC_ROOT / "spellbot",
]
