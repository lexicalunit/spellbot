import factory

from spellbot.models import Verify


class VerifyFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Verify
        sqlalchemy_session_persistence = "flush"
