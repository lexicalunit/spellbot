import factory

from spellbot.models import Config


class ConfigFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Config
        sqlalchemy_session_persistence = "flush"
