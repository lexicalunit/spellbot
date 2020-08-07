from typing import Set
from unittest.mock import Mock
from warnings import warn

import spellbot
from spellbot.assets import load_strings

from .constants import REPO_ROOT

S_SPY = Mock(wraps=spellbot.s)
SNAPSHOTS_USED: Set[str] = set()


class TestMeta:
    # Tracks the usage of string keys over the entire test session.
    # It can fail for two reasons:
    #
    # 1. There's a key in strings.yaml that's not being used at all.
    # 2. There's a key in strings.yaml that isn't being used in the tests.
    #
    # For situation #1 the solution is to remove the key from the config.
    # As for #2, there should be a new test which utilizes this key.
    def test_strings(self):
        """Assures that there are no missing or unused strings data."""
        used_keys = set(s_call[0][0] for s_call in S_SPY.call_args_list)
        config_keys = set(load_strings().keys())
        if "did_you_mean" not in used_keys:
            warn('strings.yaml key "did_you_mean" is unused in test suite')
            used_keys.add("did_you_mean")
        assert config_keys - used_keys == set()

    # Tracks the usage of snapshot files over the entire test session.
    # When it fails it means you probably need to clear out any unused snapshot files.
    def test_snapshots(self):
        """Checks that all of the snapshots files are being used."""
        snapshots_dir = REPO_ROOT / "tests" / "snapshots"
        snapshot_files = set(f.name for f in snapshots_dir.glob("*.txt"))
        assert snapshot_files == SNAPSHOTS_USED
