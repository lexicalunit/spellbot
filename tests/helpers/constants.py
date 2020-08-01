from pathlib import Path
from unittest.mock import Mock

import spellbot

##############################
# Test Suite Constants
##############################

CLIENT_TOKEN = "my-token"
CLIENT_AUTH = "my-auth"

TST_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_ROOT = TST_ROOT / "fixtures"
REPO_ROOT = TST_ROOT.parent
SRC_ROOT = REPO_ROOT / "src"

SRC_DIRS = [REPO_ROOT / "tests", SRC_ROOT / "spellbot", REPO_ROOT / "scripts"]

S_SPY = Mock(wraps=spellbot.s)

SNAPSHOTS_USED = set()
