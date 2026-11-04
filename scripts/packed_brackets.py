#!/usr/bin/env python
# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Find, and fix, bracketed lists whose elements are packed together between their brackets.

When a bracketed list doesn't fit on one line, every element goes on its own line with a
trailing comma. `ruff format` won't do that on its own: whenever the elements fit on one
line between the brackets, it packs them there, as in

    def f(
        a: int, b: int
    ) -> None:

and only a trailing comma after the last element makes it put one element per line.

Spotting this in arbitrary Python would be hard, but the codebase is already `ruff format`
clean, so each list has one of three shapes: all on one line, packed, or one element per
line. Packed is unambiguous in the syntax tree: two or more elements all starting on one
line, after the opening bracket's line, with the closing bracket on a later line.

Usage: `packed_brackets.py [--check] FILE...`. With `--check`, report what's packed and exit
non-zero if anything is; otherwise add the trailing commas and run `ruff format` on the files.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# After the last element: nothing but an optional comment, then a newline, then the closing
# bracket (on its own line, as `ruff format` lays it out).
CLOSES_ON_LATER_LINE = re.compile(rb"\A[ \t]*(?:#[^\n]*)?\n\s*[)\]}]")

type Positioned = ast.expr | ast.keyword | ast.arg | ast.alias


@dataclass(frozen=True)
class Packed:
    """A packed list, and the byte offset just after its last element."""

    line: int
    offset: int


def byte_offset(lines: list[bytes], lineno: int, col: int) -> int:
    """Convert an AST position (1-based line, UTF-8 byte column) to an offset in the source."""
    return sum(len(line) for line in lines[: lineno - 1]) + col


def elements(node: ast.AST) -> tuple[list[Positioned], int] | None:
    """
    Return a bracketed list's elements, and how many there are, or None for other nodes.

    For a signature the count is its parameters; their defaults are included as elements only
    because a default ends after the parameter it belongs to.
    """
    items: list[Positioned]
    match node:
        case ast.Call(args=args, keywords=keywords):
            items = [*args, *keywords]
        case ast.ClassDef(bases=bases, keywords=keywords):
            items = [*bases, *keywords]
        case ast.FunctionDef(args=a) | ast.AsyncFunctionDef(args=a):
            params: list[Positioned] = [*a.posonlyargs, *a.args]
            params += [a.vararg] if a.vararg else []
            params += a.kwonlyargs
            params += [a.kwarg] if a.kwarg else []
            defaults = [d for d in [*a.defaults, *a.kw_defaults] if d is not None]
            return [*params, *defaults], len(params)
        case ast.List(elts=elts) | ast.Set(elts=elts) | ast.Tuple(elts=elts):
            items = list(elts)
        case ast.Dict(keys=keys, values=values):
            items = [*(k for k in keys if k is not None), *values]
        case ast.ImportFrom(names=names):
            items = list(names)
        case ast.Subscript(slice=ast.Tuple(elts=elts)):
            items = list(elts)
        case _:
            return None
    return items, len(items)


def opening_line(node: ast.expr | ast.stmt) -> int:
    """Return the line of the list's opening bracket."""
    match node:
        case ast.Call(func=func):
            return func.end_lineno or func.lineno
        case ast.Subscript(value=value):
            return value.end_lineno or value.lineno
        case _:
            # A `def` or `class` starts on its own line, after any decorators.
            return node.lineno


def packed_list(node: ast.expr | ast.stmt, source: bytes, lines: list[bytes]) -> Packed | None:
    """Return `node` as a packed list, or None if it isn't one."""
    listed = elements(node)
    if listed is None:
        return None
    items, count = listed
    starts = {item.lineno for item in items[:count]}
    if count < 2 or len(starts) != 1:
        return None  # fewer than two elements, or already one per line
    (line,) = starts
    if line <= opening_line(node):
        # The elements start on the opening bracket's line. This also passes over tuples
        # without brackets of their own, which start at their first element.
        return None
    last = max(items, key=lambda item: (item.end_lineno or 0, item.end_col_offset or 0))
    end = byte_offset(lines, last.end_lineno or last.lineno, last.end_col_offset or 0)
    if source[end : end + 1] == b"," or not CLOSES_ON_LATER_LINE.match(source[end:]):
        return None  # already has a trailing comma, or closes on the same line
    return Packed(line=line, offset=end)


def find_packed(source: bytes) -> list[Packed]:
    """Return every packed list in `source`."""
    lines = source.splitlines(keepends=True)
    found = [
        packed
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.expr | ast.stmt)
        and (packed := packed_list(node, source, lines)) is not None
    ]
    return sorted(found, key=lambda packed: packed.offset)


def unpack(source: bytes) -> bytes:
    """Add a trailing comma to every packed list, so `ruff format` lays it out one per line."""
    for packed in reversed(find_packed(source)):
        source = source[: packed.offset] + b"," + source[packed.offset :]
    return source


def main(argv: list[str]) -> int:
    check = "--check" in argv
    paths = [Path(arg) for arg in argv if arg != "--check"]
    changed: list[Path] = []
    for path in paths:
        source = path.read_bytes()
        packed = find_packed(source)
        if not packed:
            continue
        if check:
            for found in packed:
                print(f"{path}:{found.line}: elements packed onto one line")  # noqa: T201
        else:
            path.write_bytes(unpack(source))
        changed.append(path)
    if changed and not check:
        subprocess.run(["ruff", "format", *map(str, changed)], check=True)  # noqa: S603, S607
    return 1 if check and changed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
