# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from spellbot.web.signing import generate_signed_url, validate_signature


@pytest.fixture(autouse=True)
def check_signatures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("spellbot.web.signing.settings.CHECK_SIGNATURE", True)
    monkeypatch.setattr("spellbot.web.signing.settings.SECRET_TOKEN", "secret")


def signed_query(guild_xid: int) -> tuple[int, str]:
    query = parse_qs(urlparse(generate_signed_url(guild_xid)).query)
    return int(query["expires"][0]), query["sig"][0]


class TestValidateSignature:
    def test_accepts_its_own_signature(self) -> None:
        expires, sig = signed_query(1)
        assert validate_signature(1, expires, sig)

    def test_rejects_another_guilds_signature(self) -> None:
        expires, sig = signed_query(1)
        assert not validate_signature(2, expires, sig)

    @pytest.mark.parametrize("sig", ["é", "\u200b" * 64, ""])
    def test_rejects_non_hex_signatures(self, sig: str) -> None:
        expires, _ = signed_query(1)
        assert not validate_signature(1, expires, sig)
