import factory

from spellbot.models.game import Game


class GameFactory(factory.alchemy.SQLAlchemyModelFactory):
    id = factory.Sequence(lambda n: n + 1)
    message_xid = factory.Faker("random_int")
    seats = 4

    class Meta:
        model = Game
