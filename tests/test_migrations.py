class TestMigrations:
    def test_alembic(self, tmp_path):
        from sqlalchemy import create_engine

        from spellbot.data import create_all, reverse_all

        db_file = tmp_path / "spellbot.db"
        connection_url = f"sqlite:///{db_file}"
        engine = create_engine(connection_url)
        connection = engine.connect()
        create_all(connection, connection_url)
        reverse_all(connection, connection_url)
