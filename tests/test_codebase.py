import re
import sys
from os import chdir
from subprocess import run

import toml
from git import Repo

from . import REPO_ROOT, SRC_DIRS


class TestCodebase:
    def test_pyright(self):
        """Checks that the Python codebase passes pyright static analysis checks."""
        chdir(REPO_ROOT)
        cmd = ["pyright", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"pyright issues:\n{proc.stdout.decode('utf-8')}"

    def test_flake8(self):
        """Checks that the Python codebase passes configured flake8 checks."""
        chdir(REPO_ROOT)
        cmd = ["flake8", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"flake8 issues:\n{proc.stdout.decode('utf-8')}"

    def test_black(self):
        """Checks that the Python codebase passes configured black checks."""
        chdir(REPO_ROOT)
        cmd = ["black", "--check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"black issues:\n{proc.stderr.decode('utf-8')}"

    def test_isort(self):
        """Checks that the Python codebase imports are correctly sorted."""
        chdir(REPO_ROOT)
        cmd = ["isort", "--df", "-w90", "-c", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"isort issues:\n{proc.stdout.decode('utf-8')}"

    def test_pyproject_dependencies(self):
        """Checks that pyproject.toml dependencies are sorted."""
        pyproject = toml.load("pyproject.toml")

        dev_deps = list(pyproject["tool"]["poetry"]["dev-dependencies"].keys())
        assert dev_deps == sorted(dev_deps)

        deps = list(pyproject["tool"]["poetry"]["dependencies"].keys())
        assert deps == sorted(deps)

    def test_whitespace(self):
        """Checks for problematic trailing whitespace and missing ending newlines."""
        EXCLUDE_EXTS = (".gif", ".ico", ".ics", ".jpg", ".lock", ".svg", ".png")
        repo = Repo(REPO_ROOT)
        errors = set()
        prog = re.compile(r"^.*[ \t]+$")

        # Some sources from beautiful-jekyll have persistent whitespace issues.
        WHITESPACE_EXCEPTIONS = "docs/_includes/head.html"

        def paths(tree, path):
            for blob in tree.blobs:
                yield path / blob.name
            for t in tree.trees:
                yield from paths(t, path / t.name)

        def check(path):
            if path.suffix.lower() in EXCLUDE_EXTS:
                return
            rels = str(path.relative_to(REPO_ROOT))
            if "__snapshots__" in rels:
                return
            with open(path, encoding="utf-8") as file:
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
            print("Files with trailing whitespace:", file=sys.stderr)  # noqa: T001
            for error in sorted(errors):
                print(error, file=sys.stderr)  # noqa: T001
            assert False, "Trailing whitespace is not allowed."
