from __future__ import annotations

import dunamai as _dunamai


def version_from_git() -> str | None:
    try:
        choice = _dunamai.Version.from_any_vcs
        version = _dunamai.get_version("spellbot", first_choice=choice).serialize()
    except Exception:
        return None
    return version if version is not None and version != "0.0.0" else None


def version_from_package() -> str | None:
    try:
        choice = _dunamai.Version.from_any_vcs
        version = _dunamai.get_version("spellbot", third_choice=choice).serialize()
    except Exception:
        return None
    return version if version is not None and version != "0.0.0" else None


def version_from_toml() -> str | None:
    from os.path import realpath
    from pathlib import Path

    import toml

    try:
        pkg_root = Path(realpath(__file__)).parent
        src_root = Path(pkg_root).parent
        repo_root = src_root.parent
        pyproject = toml.load(repo_root / "pyproject.toml")
    except Exception:
        return None

    project = pyproject.get("project", {})
    version = project.get("version", None)
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
