import re
import sys
from os import chdir, sep
from subprocess import run

import toml
from git import Repo  # type: ignore

from .constants import REPO_ROOT, SRC_DIRS


class TestCodebase:
    def test_mypy(self):
        """Checks that the Python codebase passes mypy static analysis checks."""
        chdir(REPO_ROOT)
        cmd = ["mypy", *SRC_DIRS, "--warn-unused-configs"]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, f"mypy issues:\n{proc.stdout.decode('utf-8')}"

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

    def test_sort_strings(self):
        """Checks that the strings data is correctly sorted."""
        chdir(REPO_ROOT)
        cmd = ["python", "scripts/sort_strings.py", "--check"]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T001
        proc = run(cmd, capture_output=True)
        assert proc.returncode == 0, (
            f"sort strings issues:\n{proc.stdout.decode('utf-8')}\n\n"
            "Please run `poetry run scripts/sort_strings.py` to resolve this issue."
        )

    def test_snapshots_size(self):
        """Checks that none of the snapshots files are unreasonably small."""
        snapshots_dir = REPO_ROOT / "tests" / "snapshots"
        small_snapshots = []
        for f in snapshots_dir.glob("*.txt"):
            if f.stat().st_size <= 150:
                small_snapshots.append(f"- {f.name}")
        if small_snapshots:
            offenders = "\n".join(small_snapshots)
            assert False, (
                "Very small snapshot files are problematic.\n"
                "Offending snapshot files:\n"
                f"{offenders}\n"
                "Consider refacotring them to avoid using snapshots. Tests that use "
                "snapshots are harder to reason about when they fail. Whenever possible "
                "a test with inline data is much easier to reason about and refactor."
            )

    def test_readme_commands(self, client):
        """Checks that all commands are documented in our readme."""
        with open(REPO_ROOT / "README.md") as f:
            readme = f.read()

        documented = set(re.findall(r"^- `!([a-z]+)`: .*$", readme, re.MULTILINE))
        implemented = set(client.commands)

        assert documented == implemented

    def test_index_commands(self, client):
        """Checks that all commands are documented on our webpage."""
        with open(REPO_ROOT / "docs" / "index.html") as f:
            index = f.read()

        documented = set(
            re.findall(r"^ *<li><code>!([a-z]+)</code>: .*$", index, re.MULTILINE)
        )
        implemented = set(client.commands)

        assert documented == implemented

    def test_subcommands_documented(self, client):
        """Checks that all subcommands are documented in the spellbot() docstring."""
        documented = set(
            re.findall(
                r"^ *\* `([a-z]+) ?[^`]*`: .*$", client.spellbot.__doc__, re.MULTILINE
            )
        )
        implemented = set(client.subcommands)

        assert implemented == documented

    def test_readme_subcommands(self, client):
        """Checks that all subcommands are documented in our readme."""
        with open(REPO_ROOT / "README.md") as f:
            readme = f.read()

        documented = set(re.findall(r"^  - `([a-z]+)`: .*$", readme, re.MULTILINE))
        implemented = set(client.subcommands)

        assert documented == implemented

    def test_index_subcommands(self, client):
        """Checks that all subcommands are documented on our webpage."""
        with open(REPO_ROOT / "docs" / "index.html") as f:
            index = f.read()

        documented = set(
            re.findall(r"^ *<li><code>([a-z]+)</code>: .*$", index, re.MULTILINE)
        )
        implemented = set(client.subcommands)

        assert documented == implemented

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
            if rels.startswith(f"tests{sep}snapshots{sep}"):
                return
            with open(path) as file:
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
