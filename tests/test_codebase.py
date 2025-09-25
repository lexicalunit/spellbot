from __future__ import annotations

import re
import sys
from os import chdir
from pathlib import Path
from subprocess import getoutput, run
from typing import TYPE_CHECKING, cast

import pytest
import toml
from git.repo import Repo

from . import REPO_ROOT, SRC_DIRS

if TYPE_CHECKING:
    from collections.abc import Generator

    from git.objects import Tree


class TestCodebase:
    def test_annotations(self) -> None:
        """Checks that all python modules import annotations from future."""
        chdir(REPO_ROOT)
        output = getoutput(  # noqa: S605
            (
                r"/usr/bin/find . -type d \( "
                r"    -path ./env -o "
                r"    -path ./venv -o "
                r"    -path ./.venv -o "
                r"    -path ./.git -o "
                r"    -path ./src/spellbot/migrations/versions "
                r"\) -prune -o -name '*.py' "
                r" -exec grep -HEoc 'from __future__ import annotations' {} \; "
                r" | grep ':0'"
            ),
        )
        assert output == "", "ensure that these files import annotations from __future__"

    def test_pyright(self) -> None:
        """Checks that the Python codebase passes pyright static analysis checks."""
        chdir(REPO_ROOT)
        cmd = ["pyright", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        assert exitcode == 0, f"pyright issues:\n{proc.stdout.decode('utf-8')}"

    def test_ruff(self) -> None:
        """Checks that the Python codebase passes configured ruff checks."""
        chdir(REPO_ROOT)
        cmd = ["ruff", "check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        assert exitcode == 0, (
            f"ruff issues:\n{proc.stderr.decode('utf-8')}\n{proc.stdout.decode('utf-8')}"
        )

    def test_ruff_format(self) -> None:
        """Checks that the Python codebase passes configured ruff format checks."""
        chdir(REPO_ROOT)
        cmd = ["ruff", "format", "--check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        assert exitcode == 0, f"ruff format issues:\n{proc.stderr.decode('utf-8')}"

    def test_pylic(self) -> None:
        """Checks that the Python codebase passes configured pylic checks."""
        chdir(REPO_ROOT)
        cmd = ["pylic", "check"]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        assert exitcode == 0, f"pylic issues:\n{proc.stdout.decode('utf-8')}"

    def test_pyproject_dependencies(self) -> None:
        """Checks that pyproject.toml dependencies are sorted."""
        pyproject = toml.load("pyproject.toml")

        dev_deps = list(pyproject["project"]["dependencies"])
        assert dev_deps == sorted(dev_deps)

        deps = list(pyproject["dependency-groups"]["dev"])
        assert deps == sorted(deps)

    def test_whitespace(self) -> None:  # noqa: C901 # pragma: no cover
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
                if not rels.endswith("CNAME") and lastline and not lastline.endswith("\n"):
                    errors.add(f"\t{key} - missing endline")

        for path in paths(repo.tree(), REPO_ROOT):
            check(path)
        for change in repo.index.diff(None):
            if change.a_path is not None:
                check(REPO_ROOT / change.a_path)

        if errors:
            print("Files with trailing whitespace:", file=sys.stderr)  # noqa: T201
            for error in sorted(errors):
                print(error, file=sys.stderr)  # noqa: T201
            pytest.fail("Trailing whitespace is not allowed.")
