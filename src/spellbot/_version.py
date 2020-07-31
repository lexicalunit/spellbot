import dunamai as _dunamai  # type: ignore


def version_from_git():
    try:
        choice = _dunamai.Version.from_any_vcs
        version = _dunamai.get_version("spellbot", first_choice=choice).serialize()
        return version if version is not None and version != "0.0.0" else None
    except RuntimeError:
        return None


def version_from_package():
    try:
        choice = _dunamai.Version.from_any_vcs
        version = _dunamai.get_version("spellbot", third_choice=choice).serialize()
        return version if version is not None and version != "0.0.0" else None
    except RuntimeError:
        return None


def version_from_toml():
    from os.path import dirname, realpath
    from pathlib import Path

    import toml

    try:
        PKG_ROOT = dirname(realpath(__file__))
        SRC_ROOT = Path(PKG_ROOT).parent
        REPO_ROOT = SRC_ROOT.parent
        pyproject = toml.load(REPO_ROOT / "pyproject.toml")
    except:
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
