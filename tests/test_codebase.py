from __future__ import annotations

import ast
import re
import sys
import tomllib
from os import chdir
from pathlib import Path
from subprocess import getoutput, run
from typing import TYPE_CHECKING, cast

import pytest
import yaml
from git.repo import Repo

from . import REPO_ROOT, SRC_DIRS, SRC_ROOT

if TYPE_CHECKING:
    from collections.abc import Generator

    from git.objects import Tree


class TestCodebase:
    def test_annotations(self) -> None:  # pragma: no cover
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

    def test_pyright(self) -> None:  # pragma: no cover
        """Checks that the Python codebase passes pyright static analysis checks."""
        chdir(REPO_ROOT)
        cmd = ["pyright", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        assert exitcode == 0, f"pyright issues:\n{proc.stdout.decode('utf-8')}"

    def test_ruff(self) -> None:  # pragma: no cover
        """Checks that the Python codebase passes configured ruff checks."""
        chdir(REPO_ROOT)
        cmd = ["ruff", "check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        assert exitcode == 0, (
            f"ruff issues:\n{proc.stderr.decode('utf-8')}\n{proc.stdout.decode('utf-8')}"
        )

    def test_ruff_format(self) -> None:  # pragma: no cover
        """Checks that the Python codebase passes configured ruff format checks."""
        chdir(REPO_ROOT)
        cmd = ["ruff", "format", "--check", *SRC_DIRS]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        assert exitcode == 0, f"ruff format issues:\n{proc.stderr.decode('utf-8')}"

    def test_pylic(self) -> None:  # pragma: no cover
        """Checks that the Python codebase passes configured pylic checks."""
        chdir(REPO_ROOT)
        cmd = ["pylic", "check", "--allow-extra-safe-licenses"]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        assert exitcode == 0, f"pylic issues:\n{proc.stdout.decode('utf-8')}"

    def test_deadcode(self) -> None:  # pragma: no cover
        """
        Checks that the Python codebase is free of dead code (via vulture).

        Configuration (paths, allowlist, ignores) lives in `[tool.vulture]` in pyproject.toml.
        Genuine findings should be deleted; unavoidable false positives belong in
        `.vulture_allowlist.py`.
        """
        chdir(REPO_ROOT)
        cmd = ["vulture"]
        print("running:", " ".join(str(part) for part in cmd))  # noqa: T201
        proc = run(cmd, capture_output=True, check=False)  # noqa: S603
        exitcode: int = cast("int", proc.returncode)
        out = proc.stdout.decode("utf-8")
        err = proc.stderr.decode("utf-8")
        assert exitcode == 0, f"vulture found dead code:\n{out}\n{err}"

    def test_no_unused_translation_keys(self) -> None:  # pragma: no cover
        """
        Checks that every key in `en.yaml` is referenced somewhere in the codebase.

        Flattens the English catalog into dotted keys, then confirms each appears in the
        source tree. Two shapes need special handling:

        - Pluralization groups (a mapping whose children are exactly plural forms like
          `{one, many, other}`) collapse to their parent, since that parent is the key
          code actually passes to `t(..., count=n)` — the plural leaves are never named.
        - Keys reached only through an f-string prefix (e.g. `t(f"service.{...}")`) can't
          be seen statically, so the whole prefix is treated as used.

        A failure means the key is either dead (delete it from every `translations/*.yaml`)
        or built dynamically in a way this check can't see (extend the detection below).
        """
        plural_forms = {"zero", "one", "two", "few", "many", "other"}
        catalog = yaml.safe_load((SRC_ROOT / "spellbot" / "translations" / "en.yaml").read_text())
        root = next(iter(catalog.values()))  # unwrap the top-level locale key (`en:`)

        keys: list[str] = []

        def collect(node: object, prefix: str) -> None:
            if isinstance(node, dict):
                children = set(node.keys())
                if children and children <= plural_forms:
                    keys.append(prefix)  # plural group -> parent is the referenced key
                    return
                for name, value in node.items():
                    collect(value, f"{prefix}.{name}" if prefix else str(name))
            else:
                keys.append(prefix)

        collect(root, "")

        # Concatenate the source tree (excluding the translation catalogs themselves).
        scan_suffixes = {".py", ".j2", ".js", ".html", ".css", ".txt", ".md"}
        blob = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for src_dir in SRC_DIRS
            for path in src_dir.rglob("*")
            if path.is_file() and "translations" not in path.parts and path.suffix in scan_suffixes
        )

        dynamic_prefixes = set(re.findall(r"""t\(\s*f["']([a-z0-9_.]+)\{""", blob))
        unused = sorted(
            key
            for key in keys
            if key not in blob and not any(key.startswith(p) for p in dynamic_prefixes)
        )
        assert not unused, (
            "these en.yaml keys are referenced nowhere; delete them from every "
            "translations/*.yaml (or extend dynamic-key detection):\n" + "\n".join(unused)
        )

    def test_translation_locales_match_en(self) -> None:  # pragma: no cover
        """
        Checks that every `translations/<locale>.yaml` defines exactly the keys `en.yaml` does.

        `en` is the source of truth and the runtime fallback, so any locale that is missing a
        key silently falls back to English, and any extra key is dead weight that no lookup will
        ever reach. Enforcing an exact 1-to-1 key set keeps every catalog structurally in lockstep.
        """
        translations = SRC_ROOT / "spellbot" / "translations"

        def key_set(path: Path) -> set[str]:
            catalog = yaml.safe_load(path.read_text())
            root = next(iter(catalog.values()))  # unwrap the top-level locale key
            found: set[str] = set()

            def flatten(node: object, prefix: str) -> None:
                if isinstance(node, dict):
                    for name, value in node.items():
                        flatten(value, f"{prefix}.{name}" if prefix else str(name))
                else:
                    found.add(prefix)

            flatten(root, "")
            return found

        en_keys = key_set(translations / "en.yaml")
        problems: list[str] = []
        for path in sorted(translations.glob("*.yaml")):
            if path.name == "en.yaml":
                continue
            keys = key_set(path)
            missing = sorted(en_keys - keys)
            extra = sorted(keys - en_keys)
            if missing or extra:
                problems.append(f"{path.name}: missing={missing} extra={extra}")
        assert not problems, "locale catalogs must match en.yaml key-for-key:\n" + "\n".join(
            problems
        )

    def test_translation_values_are_consistent_by_source_string(self) -> None:  # pragma: no cover
        """
        Checks that keys sharing an English value also share one translation in every locale.

        The English string is the identity of a piece of text: if two keys read the same in
        `en.yaml` they mean the same thing, so a locale must not translate them differently
        (e.g. `game.field.bracket` and `web.field.bracket` are both "Bracket" and must render
        the same Commander power-tier word — one input value, one translation per language).

        Pluralization forms are exempt: `many` and `other` frequently coincide in English yet
        are distinct grammatical categories that legitimately diverge in languages like Polish,
        so leaf keys whose final segment is a plural form are left out of the grouping.
        """
        plural_forms = {"zero", "one", "two", "few", "many", "other"}
        translations = SRC_ROOT / "spellbot" / "translations"

        def flatten(path: Path) -> dict[str, str]:
            catalog = yaml.safe_load(path.read_text())
            root = next(iter(catalog.values()))
            out: dict[str, str] = {}

            def walk(node: object, prefix: str) -> None:
                if isinstance(node, dict):
                    for name, value in node.items():
                        walk(value, f"{prefix}.{name}" if prefix else str(name))
                elif prefix.rsplit(".", 1)[-1] not in plural_forms:
                    out[prefix] = str(node)

            walk(root, "")
            return out

        # Group English keys by their shared source string; only groups with >1 key matter.
        english = flatten(translations / "en.yaml")
        groups: dict[str, list[str]] = {}
        for key, value in english.items():
            groups.setdefault(value, []).append(key)
        shared = [keys for keys in groups.values() if len(keys) > 1]

        problems: list[str] = []
        for path in sorted(translations.glob("*.yaml")):
            catalog = flatten(path)
            for keys in shared:
                rendered = {catalog[k] for k in keys if k in catalog}
                if len(rendered) > 1:
                    problems.append(
                        f"{path.name}: {sorted(keys)} share an English value but render as "
                        f"{sorted(rendered)}"
                    )
        assert not problems, (
            "keys with the same English value must share one translation per locale:\n"
            + "\n".join(problems)
        )

    def test_pyproject_dependencies(self) -> None:  # pragma: no cover
        """Checks that pyproject.toml dependencies are sorted."""
        with Path("pyproject.toml").open("rb") as fp:
            pyproject = tomllib.load(fp)

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

        def paths(tree: Tree, path: Path) -> Generator[Path]:
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
            try:
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
            except FileNotFoundError:
                return  # file has been deleted, so obviously we don't need to check it

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

    def test_no_inline_imports(self) -> None:  # noqa: C901 # pragma: no cover
        """
        Checks that all imports are at module level, not inside functions.

        To allow an inline import, add a comment containing 'allow_inline' on the same
        line or the line before the import statement.
        """
        errors: list[str] = []

        def check_file(filepath: Path) -> None:
            try:
                source = filepath.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(filepath))
            except SyntaxError:
                return

            source_lines = source.splitlines()

            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                for child in ast.walk(node):
                    if not isinstance(child, ast.Import | ast.ImportFrom):
                        continue
                    lineno = child.lineno
                    current_line = source_lines[lineno - 1] if lineno <= len(source_lines) else ""
                    prev_line = source_lines[lineno - 2] if lineno > 1 else ""
                    if (
                        "allow_inline" in current_line.lower()
                        or "allow_inline" in prev_line.lower()
                    ):
                        continue
                    rel_path = filepath.relative_to(REPO_ROOT)
                    errors.append(f"{rel_path}:{lineno} - inline import in '{node.name}'")

        for src_dir in SRC_DIRS:
            for filepath in src_dir.rglob("*.py"):
                check_file(filepath)

        if errors:
            print("Files with inline imports:", file=sys.stderr)  # noqa: T201
            for error in sorted(errors):
                print(f"\t{error}", file=sys.stderr)  # noqa: T201
            pytest.fail("Inline imports require an 'allow_inline' comment.")
