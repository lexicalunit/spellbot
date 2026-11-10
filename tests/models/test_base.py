# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot.models import Game, User, column_max

if TYPE_CHECKING:
    from sqlalchemy.orm import QueryableAttribute


class TestColumnMax:
    @pytest.mark.parametrize(
        ("column", "expected"),
        [
            pytest.param(User.xid, 2**63 - 1, id="bigint"),
            pytest.param(Game.id, 2**31 - 1, id="int"),
            pytest.param(Game.seats, 2**31 - 1, id="int-not-a-key"),
        ],
    )
    def test_integer_columns(self, column: QueryableAttribute[int], expected: int) -> None:
        assert column_max(column) == expected

    def test_not_an_integer_column(self) -> None:
        with pytest.raises(TypeError, match="not an integer column"):
            # Deliberately the wrong column type, to check the guard for untyped callers.
            column_max(Game.rules)  # ty: ignore[invalid-argument-type]
