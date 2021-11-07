import pytest

from spellbot import Settings


class TestMigrations:
    @pytest.mark.nosession
    def test_alembic(self, settings: Settings):
        from spellbot.models import create_all, reverse_all

        create_all(settings.DATABASE_URL)
        reverse_all(settings.DATABASE_URL)
