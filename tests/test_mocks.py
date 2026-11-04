# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import operator

import httpx
import pytest
from decoy import matchers

from tests.mocks.decoys import ANY, captured
from tests.mocks.http import discord_oauth, in_order, raising, serve_httpx


class TestAnyValue:
    @pytest.mark.parametrize("value", [None, 0, "", "text", [1], object()])
    def test_matches_everything(self, value: object) -> None:
        assert value == ANY
        assert operator.eq(ANY, value)

    def test_is_hashable(self) -> None:
        assert hash(ANY) == hash(ANY)

    def test_repr(self) -> None:
        assert repr(ANY) == "<ANY>"


class TestCaptured:
    def test_returns_the_captured_value(self) -> None:
        captor = matchers.ValueCaptor[str]()
        assert captor.matcher == "caught"
        assert captured(captor, str) == "caught"

    def test_rejects_a_value_of_the_wrong_type(self) -> None:
        captor = matchers.ValueCaptor[str]()
        assert captor.matcher == 42
        with pytest.raises(AssertionError):
            captured(captor, str)


@pytest.mark.asyncio
class TestServeHttpx:
    async def test_discord_oauth_answers_unknown_paths_with_404(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        requests = serve_httpx(monkeypatch, discord_oauth())
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://discord.com/api/elsewhere")
        assert resp.status_code == 404
        assert [r.url.path for r in requests] == ["/api/elsewhere"]

    async def test_in_order_and_raising(self, monkeypatch: pytest.MonkeyPatch) -> None:
        serve_httpx(
            monkeypatch,
            in_order(httpx.Response(201), httpx.ReadTimeout, httpx.Response(202)),
        )
        async with httpx.AsyncClient() as client:
            assert (await client.get("https://example.com/")).status_code == 201
            with pytest.raises(httpx.ReadTimeout):
                await client.get("https://example.com/")
            assert (await client.get("https://example.com/")).status_code == 202
        serve_httpx(monkeypatch, raising())
        async with httpx.AsyncClient() as client:
            with pytest.raises(httpx.ConnectError):
                await client.get("https://example.com/")
