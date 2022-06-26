from __future__ import annotations

from typing import Optional

import dunamai as _dunamai


def version_from_git() -> Optional[str]:
    try:
        choice = _dunamai.Version.from_any_vcs
        version = _dunamai.get_version("spellbot", first_choice=choice).serialize()
        return version if version is not None and version != "0.0.0" else None
    except Exception:
        return None


def version_from_package() -> Optional[str]:
    try:
        choice = _dunamai.Version.from_any_vcs
        version = _dunamai.get_version("spellbot", third_choice=choice).serialize()
        return version if version is not None and version != "0.0.0" else None
    except Exception:
        return None


def version_from_toml() -> Optional[str]:
    from os.path import dirname, realpath
    from pathlib import Path

    import toml

    try:
        pkg_root = dirname(realpath(__file__))
        src_root = Path(pkg_root).parent
        repo_root = src_root.parent
        pyproject = toml.load(repo_root / "pyproject.toml")
    except Exception:
        return None

    tool = pyproject.get("tool", {})
    poetry = tool.get("poetry", {})
    version = poetry.get("version", None)
    return version if version is not None and version != "0.0.0" else None


# Below we attempt to detect the version from git first, and if
# that fails we fallback to getting it from the project, and if
# that fails we'll just try and read it directly from pyproject.toml.
# If we can successfully get it from git, we can get a development
# version name like 5.0.2.post2.dev0+1d15510 for example.

__version__ = version_from_git()
if __version__ is None:
    __version__ = version_from_package()
if __version__ is None:
    __version__ = version_from_toml()
if __version__ is None:
    __version__ = "unknown"
