import factory

from spellbot.models import Game


class GameFactory(factory.alchemy.SQLAlchemyModelFactory):
    id = factory.Sequence(lambda n: n + 1)
    message_xid = factory.Faker("random_int")
    seats = 4
    deleted_at = None

    class Meta:
        model = Game
        sqlalchemy_session_persistence = "flush"
