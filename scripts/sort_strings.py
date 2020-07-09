#!/usr/bin/env python3

import sys
from os.path import dirname, realpath
from pathlib import Path

from yaml import dump, load

SRC_ROOT = Path(dirname(realpath(__file__))).parent
ASSETS_DIR = SRC_ROOT / "src" / "spellbot" / "assets"
STRINGS_DATA_FILE = ASSETS_DIR / "strings.yaml"

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def diff(expected, actual):
    import difflib

    expected = expected.splitlines(1)
    actual = actual.splitlines(1)
    diff = difflib.unified_diff(expected, actual)
    return "".join(diff)


with open(STRINGS_DATA_FILE, "r") as f:
    before = f.read()

with open(STRINGS_DATA_FILE, "r") as f:
    data = load(f, Loader=Loader)

after = dump(data, Dumper=Dumper, sort_keys=True)
changes = diff(after, before)

if changes and len(sys.argv) > 1 and sys.argv[1] == "--check":
    print(changes)  # noqa: T001
else:
    open(STRINGS_DATA_FILE, "w").write(after)

sys.exit(1 if changes else 0)
