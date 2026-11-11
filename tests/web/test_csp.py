# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import re
from itertools import count
from typing import TYPE_CHECKING

import pytest

from spellbot.web import builder
from spellbot.web.builder import (
    TEMPLATES_ROOT,
    content_security_policy,
    external_scripts,
    new_csp_nonce,
)

if TYPE_CHECKING:
    from pathlib import Path

    from aiohttp.client import ClientSession

pytestmark = pytest.mark.use_db

SCRIPT_TAG = re.compile(r"<script\b([^>]*)>")
INLINE_HANDLER = re.compile(r"""\son[a-z]+\s*=\s*["']""", re.IGNORECASE)
TEMPLATES = sorted(TEMPLATES_ROOT.glob("*.j2"))


def directives(policy: str) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for directive in policy.split(";"):
        name, *values = directive.split()
        parsed[name] = values
    return parsed


class TestContentSecurityPolicy:
    def test_restricts_scripts(self) -> None:
        policy = directives(content_security_policy("abc"))
        assert policy["script-src"][:2] == ["'self'", "'nonce-abc'"]
        assert "'unsafe-inline'" not in policy["script-src"]
        assert "'unsafe-eval'" not in policy["script-src"]
        assert policy["object-src"] == ["'none'"]
        assert policy["base-uri"] == ["'none'"]
        assert policy["frame-ancestors"] == ["'none'"]
        assert policy["form-action"] == ["'self'"]

    def test_without_nonce(self) -> None:
        policy = directives(content_security_policy(None))
        assert not any(source.startswith("'nonce-") for source in policy["script-src"])

    def test_allows_only_the_pinned_cdn_files(self) -> None:
        cdn = directives(content_security_policy(None))["script-src"][1:]
        assert "https://cdn.jsdelivr.net/npm/chart.js@4.6.1/dist/chart.umd.min.js" in cdn
        # `record_base` writes its script tags across several lines.
        assert "https://cdnjs.cloudflare.com/ajax/libs/moment.js/2.29.1/moment.min.js" in cdn
        assert all(source.startswith("https://") and not source.endswith("/") for source in cdn)


class TestExternalScripts:
    def test_reads_script_sources(self, tmp_path: Path) -> None:
        (tmp_path / "a.html.j2").write_text(
            '<script src="https://b.example/x.js"></script>\n'
            '<script\n    src="https://a.example/y.js"\n    integrity="sha384-z"></script>\n'
            '<script src="/local.js"></script>\n'
            '<script nonce="{{ csp_nonce }}">var s = "<b>";</script>\n'
            '<img src="https://c.example/z.png">\n',
        )
        (tmp_path / "b.html.j2").write_text('<script src="https://b.example/x.js"></script>')
        (tmp_path / "ignored.txt").write_text('<script src="https://d.example/w.js"></script>')
        assert external_scripts(tmp_path) == ("https://a.example/y.js", "https://b.example/x.js")


class TestTemplatesFollowThePolicy:
    @pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.name)
    def test_inline_scripts_carry_the_nonce(self, template: Path) -> None:
        for attributes in SCRIPT_TAG.findall(template.read_text(encoding="utf-8")):
            assert "src=" in attributes or 'nonce="{{ csp_nonce }}"' in attributes

    @pytest.mark.parametrize(
        "template",
        [*TEMPLATES, *TEMPLATES_ROOT.glob("*.js")],
        ids=lambda path: path.name,
    )
    def test_no_inline_event_handlers(self, template: Path) -> None:
        assert not INLINE_HANDLER.search(template.read_text(encoding="utf-8"))


class TestNonce:
    def test_new_nonces_are_random(self) -> None:
        first, second = new_csp_nonce(), new_csp_nonce()
        assert first != second
        assert len(first) >= 22

    @pytest.mark.asyncio
    async def test_each_page_gets_its_own_nonce(
        self,
        client: ClientSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        numbers = count()
        monkeypatch.setattr(builder, "new_csp_nonce", lambda: f"nonce{next(numbers)}")
        for expected in ("nonce0", "nonce1"):
            resp = await client.get("/status")
            assert resp.status == 200
            policy = directives(resp.headers["Content-Security-Policy"])
            assert f"'nonce-{expected}'" in policy["script-src"]
            assert f'<script nonce="{expected}">' in await resp.text()
