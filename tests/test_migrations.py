from __future__ import annotations

from typing import TYPE_CHECKING

from spellbot.models import create_all, reverse_all

if TYPE_CHECKING:
    from spellbot.settings import Settings


class TestMigrations:
    def test_alembic(self, settings: Settings) -> None:
        create_all(settings.DATABASE_URL)
        reverse_all(settings.DATABASE_URL)
