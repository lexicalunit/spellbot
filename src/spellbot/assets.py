from os.path import dirname, realpath
from pathlib import Path
from string import Template

from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:  # pragma: no cover
    from yaml import Loader

PACKAGE_ROOT = Path(dirname(realpath(__file__)))
ASSETS_DIR = PACKAGE_ROOT / "assets"
STRINGS_DATA_FILE = ASSETS_DIR / "strings.yaml"
ASSET_FILES = [STRINGS_DATA_FILE]


def load_strings():
    with open(STRINGS_DATA_FILE) as f:
        return load(f, Loader=Loader)


def s(key, **kwargs):
    """Returns a string from strings.yaml asset with subsitutions."""
    if not s.strings:
        s.strings = load_strings()

    data = s.strings.get(key, "")
    assert data, f"error: missing strings key: {key}"
    return Template(data).substitute(kwargs)


s.strings = None
