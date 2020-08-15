class TestMigrations:
    def test_alembic(self, tmp_path):
        from sqlalchemy import create_engine

        from spellbot import get_db_url
        from spellbot.data import create_all, reverse_all

        db_file = tmp_path / "spellbot.db"
        connection_string = f"sqlite:///{db_file}"
        db_url = get_db_url("TEST_SPELLBOT_DB_URL", connection_string)

        engine = create_engine(db_url)
        connection = engine.connect()
        create_all(connection, db_url)
        reverse_all(connection, db_url)
