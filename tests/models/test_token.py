from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.fixtures import Factories


class TestModelToken:
    def test_token(self, factories: Factories) -> None:
        token = factories.token.create()

        assert token.to_dict() == {
            "id": token.id,
            "created_at": token.created_at,
            "updated_at": token.updated_at,
            "deleted_at": token.deleted_at,
            "key": token.key,
        }
