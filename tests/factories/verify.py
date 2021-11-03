import factory

from spellbot.models.verify import Verify


class VerifyFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Verify
        sqlalchemy_session_persistence = "flush"
