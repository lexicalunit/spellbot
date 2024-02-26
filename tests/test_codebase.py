from __future__ import annotations

import re
import sys
import warnings
from os import chdir
from pathlib import Path
from subprocess import getoutput, run
from typing import Generator, cast

import pytest
import toml
from git.objects import Tree
from git.repo import Repo

from . import REPO_ROOT, SRC_DIRS


class TestCodebase:
    def test_annotations(self) -> None:
        """Checks that all python modules import annotations from future."""
        chdir(REPO_ROOT)
        output = getoutput(
            (
                r"find . -type d \( "
                r"    -path ./env -o "
                r"    -path ./src/spellbot/migrations/versions -o "
                r"    -path ./src/spellbot/cogs "
                r"\) -prune -o -name '*.py' "
                r" -exec grep -HEoc 'from __future__ import annotations' {} \; "
                r" | grep 0"
            ),
        )
        assert output == "", "ensure that these files import annotations from __future__"

    def test_pyright(self) -> None:
        """Checks that the Python codebase passes pyright static analysis checks."""
        chdir(REPO_ROOT)
        cmd = ["pyright", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True)
        exitcode: int = cast(int, proc.returncode)
        assert exitcode == 0, f"pyright issues:\n{proc.stdout.decode('utf-8')}"

    def test_ruff(self) -> None:
        """Checks that the Python codebase passes configured ruff checks."""
        chdir(REPO_ROOT)
        cmd = ["ruff", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True)
        exitcode: int = cast(int, proc.returncode)
        assert exitcode == 0, f"ruff issues:\n{proc.stderr.decode('utf-8')}\n{proc.stdout.decode('utf-8')}"

    def test_ruff_format(self) -> None:
        """Checks that the Python codebase passes configured ruff format checks."""
        chdir(REPO_ROOT)
        cmd = ["ruff", "format", "--check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True)
        exitcode: int = cast(int, proc.returncode)
        assert exitcode == 0, f"ruff format issues:\n{proc.stderr.decode('utf-8')}"

    @pytest.mark.skip(reason="Disabled until TODOs from v7 refactor are fixed.")
    def test_pylint(self) -> None:  # pragma: no cover
        """Checks that the Python codebase passes configured pylint checks."""
        chdir(REPO_ROOT)
        cmd = ["pylint", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        try:
            proc = run(cmd, capture_output=True)
            exitcode: int = cast(int, proc.returncode)
            assert exitcode == 0, f"pylint issues:\n{proc.stdout.decode('utf-8')}"
        except FileNotFoundError:  # pragma: no cover
            warnings.warn(UserWarning("test skipped: pylint not installed"))

    def test_pylic(self) -> None:
        """Checks that the Python codebase passes configured pylic checks."""
        chdir(REPO_ROOT)
        cmd = ["pylic", "check"]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True)
        exitcode: int = cast(int, proc.returncode)
        assert exitcode == 0, f"pylic issues:\n{proc.stdout.decode('utf-8')}"

    def test_pyproject_dependencies(self) -> None:
        """Checks that pyproject.toml dependencies are sorted."""
        pyproject = toml.load("pyproject.toml")

        dev_deps = list(pyproject["tool"]["poetry"]["group"]["dev"]["dependencies"].keys())
        assert dev_deps == sorted(dev_deps)

        deps = list(pyproject["tool"]["poetry"]["dependencies"].keys())
        assert deps == sorted(deps)

    def test_relative_imports(self) -> None:
        """Checks that relative imports are used in spellbot package."""
        chdir(REPO_ROOT / "src")
        cmd = ["/usr/bin/grep", "-HIRn", "--exclude-dir=migrations", "from spellbot", "."]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True)
        exitcode: int = cast(int, proc.returncode)
        assert exitcode == 1, f"non-relative imports:\n{proc.stdout.decode('utf-8')}"

        chdir(REPO_ROOT / "tests")
        cmd = ["/usr/bin/grep", "-HIRn", "from spellbot.[a-z]*\\.", "."]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True)
        exitcode: int = cast(int, proc.returncode)
        assert exitcode == 1, f"non-exported imports:\n{proc.stdout.decode('utf-8')}"

    def test_whitespace(self) -> None:  # pragma: no cover
        """Checks for problematic trailing whitespace and missing ending newlines."""
        EXCLUDE_EXTS = (".gif", ".ico", ".ics", ".jpg", ".lock", ".svg", ".png")
        repo = Repo(REPO_ROOT)
        errors = set()
        prog = re.compile(r"^.*[ \t]+$")

        # Some sources from beautiful-jekyll have persistent whitespace issues.
        WHITESPACE_EXCEPTIONS = "docs/_includes/head.html"

        def paths(tree: Tree, path: Path) -> Generator[Path, None, None]:
            for blob in tree.blobs:
                yield path / blob.name
            for t in tree.trees:
                yield from paths(t, path / t.name)

        def check(path: Path) -> None:
            if path.suffix.lower() in EXCLUDE_EXTS:
                return
            rels = str(path.relative_to(REPO_ROOT))
            if "__snapshots__" in rels:
                return
            with Path.open(path, encoding="utf-8") as file:
                lastline = None
                key = None
                for i, line in enumerate(file.readlines()):
                    rel_path = f"{path.relative_to(REPO_ROOT)}"
                    key = f"{rel_path}:{i + 1}"
                    if prog.match(line) and rel_path not in WHITESPACE_EXCEPTIONS:
                        errors.add(f"\t{key} - trailing whitespace")
                    lastline = line
                if not rels.endswith("CNAME"):
                    if lastline and not lastline.endswith("\n"):
                        errors.add(f"\t{key} - missing endline")

        for path in paths(repo.tree(), REPO_ROOT):
            check(path)
        for change in repo.index.diff(None):
            check(REPO_ROOT / change.a_path)

        if errors:
            print("Files with trailing whitespace:", file=sys.stderr)  # noqa: T201
            for error in sorted(errors):
                print(error, file=sys.stderr)  # noqa: T201
            pytest.fail("Trailing whitespace is not allowed.")
