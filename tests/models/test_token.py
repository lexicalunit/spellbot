from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from spellbot.data import TokenData

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelToken:
    def test_token_to_data(self, factories: Factories) -> None:
        token = factories.token.create()

        token_data = token.to_data()
        assert isinstance(token_data, TokenData)
        assert asdict(token_data) == {
            "id": token.id,
            "created_at": token.created_at,
            "updated_at": token.updated_at,
            "deleted_at": token.deleted_at,
            "key": token.key,
            "note": token.note,
            "scopes": token.scopes,
        }
