# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from scripts.packed_brackets import Packed, find_packed, main, unpack

if TYPE_CHECKING:
    from pathlib import Path


def lines_of(source: str) -> list[int]:
    """Return the lines on which `source` has packed elements."""
    return [packed.line for packed in find_packed(dedent(source).encode())]


class TestFindPacked:
    @pytest.mark.parametrize(
        ("source", "line"),
        [
            pytest.param(
                """\
                call(
                    first, second=2
                )
                """,
                2,
                id="call",
            ),
            pytest.param(
                """\
                @decorator(
                    "arg"
                )
                def f(
                    self, a: int = 1, *args: int, b: str = "", **kwargs: int
                ) -> None: ...
                """,
                5,
                id="decorated-def",
            ),
            pytest.param(
                """\
                async def f(
                    a: int, b: int
                ) -> None: ...
                """,
                2,
                id="async-def",
            ),
            pytest.param(
                """\
                class C(
                    Base, metaclass=Meta
                ): ...
                """,
                2,
                id="class",
            ),
            pytest.param("x = [\n    1, 2\n]\n", 2, id="list"),
            pytest.param("x = {\n    1, 2\n}\n", 2, id="set"),
            pytest.param("x = (\n    1, 2\n)\n", 2, id="tuple"),
            pytest.param("x = {\n    'a': 1, **rest\n}\n", 2, id="dict"),
            pytest.param("from m import (\n    a, b\n)\n", 2, id="import"),
            pytest.param("T = Callable[\n    [int], str\n]\n", 2, id="subscript"),
            pytest.param("call(\n    a, b  # why\n)\n", 2, id="comment-after-last"),
            pytest.param("call(\n    a, other(\n        b\n    )\n)\n", 2, id="last-spans-lines"),
        ],
    )
    def test_finds_packed_elements(self, source: str, line: int) -> None:
        assert lines_of(source) == [line]

    def test_finds_nested_packed_lists(self) -> None:
        source = """\
            outer(
                x, inner(
                    a, b
                )
            )
            """
        assert lines_of(source) == [3, 2]

    @pytest.mark.parametrize(
        "source",
        [
            pytest.param("call(a, b)\n", id="one-line"),
            pytest.param("call(\n    a,\n    b,\n)\n", id="one-per-line"),
            pytest.param("call(\n    only_one\n)\n", id="one-element"),
            pytest.param("call(a,\n     b)\n", id="starts-on-bracket-line"),
            pytest.param("call(\n    a, b)\n", id="closes-on-last-line"),
            pytest.param("call(\n    a, b,\n)\n", id="trailing-comma"),
            pytest.param("x = 1, 2\n", id="bare-tuple"),
            pytest.param(
                "def f(\n    a: int,\n    b: int,\n) -> None: ...\n",
                id="def-one-per-line",
            ),
        ],
    )
    def test_leaves_other_shapes_alone(self, source: str) -> None:
        assert lines_of(source) == []


class TestUnpack:
    def test_adds_a_trailing_comma_after_the_last_element(self) -> None:
        source = 'call(\n    "—", second\n)\n'.encode()
        assert unpack(source) == 'call(\n    "—", second,\n)\n'.encode()

    def test_is_idempotent(self) -> None:
        source = b"call(\n    a, b\n)\n"
        assert unpack(unpack(source)) == unpack(source)


class TestMain:
    def test_check_reports_packed_lists(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        packed = tmp_path / "packed.py"
        packed.write_text("call(\n    a, b\n)\n")
        clean = tmp_path / "clean.py"
        clean.write_text("call(a, b)\n")

        assert main(["--check", str(packed), str(clean)]) == 1

        assert capsys.readouterr().out == f"{packed}:2: elements packed onto one line\n"
        assert packed.read_text() == "call(\n    a, b\n)\n"

    def test_check_passes_clean_files(self, tmp_path: Path) -> None:
        clean = tmp_path / "clean.py"
        clean.write_text("call(a, b)\n")
        assert main(["--check", str(clean)]) == 0

    def test_fixes_and_formats(self, tmp_path: Path) -> None:
        packed = tmp_path / "packed.py"
        packed.write_text("call(\n    a, b\n)\n")

        assert main([str(packed)]) == 0

        assert packed.read_text() == "call(\n    a,\n    b,\n)\n"
        assert find_packed(packed.read_bytes()) == []

    def test_finds_report_their_offsets(self) -> None:
        assert find_packed(b"call(\n    a, b\n)\n") == [Packed(line=2, offset=14)]
