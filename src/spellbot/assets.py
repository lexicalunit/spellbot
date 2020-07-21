from os.path import dirname, realpath
from pathlib import Path
from string import Template
from typing import Optional, cast

from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:  # pragma: no cover
    from yaml import Loader  # type: ignore

PACKAGE_ROOT = Path(dirname(realpath(__file__)))
ASSETS_DIR = PACKAGE_ROOT / "assets"
STRINGS_DATA_FILE = ASSETS_DIR / "strings.yaml"
ASSET_FILES = [STRINGS_DATA_FILE]


def load_strings() -> dict:
    with open(STRINGS_DATA_FILE) as f:
        return cast(dict, load(f, Loader=Loader))


__strings: Optional[dict] = None


def s(key: str, **kwargs) -> str:
    """Returns a string from strings.yaml asset with subsitutions."""
    global __strings
    if not __strings:
        __strings = load_strings()

    data = __strings.get(key, "")
    assert data, f"error: missing strings key: {key}"
    return Template(data).substitute(kwargs)
