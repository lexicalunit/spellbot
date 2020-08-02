import re
from os import chdir
from subprocess import run

import toml

from .constants import REPO_ROOT, SRC_DIRS  # type:ignore


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

    def test_readme_commands(self, client, channel_maker):
        """Checks that all commands are documented in our readme."""
        with open(REPO_ROOT / "README.md") as f:
            readme = f.read()

        documented = set(re.findall("^- `!([a-z]+)`: .*$", readme, re.MULTILINE))
        implemented = set(client._commands.values())

        assert sorted(documented) == sorted(implemented)

    def test_pyproject_dependencies(self):
        """Checks that pyproject.toml dependencies are sorted."""
        pyproject = toml.load("pyproject.toml")

        dev_deps = list(pyproject["tool"]["poetry"]["dev-dependencies"].keys())
        assert dev_deps == sorted(dev_deps)

        deps = list(pyproject["tool"]["poetry"]["dependencies"].keys())
        assert deps == sorted(deps)
