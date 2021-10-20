import pytest


class TestMigrations:
    @pytest.mark.nosession
    def test_alembic(self, settings):
        from spellbot.models import create_all, reverse_all

        create_all(settings.DATABASE_URL)
        reverse_all(settings.DATABASE_URL)
