import factory

from spellbot.models.play import Play


class PlayFactory(factory.alchemy.SQLAlchemyModelFactory):
    points = factory.Faker("random_int", max=10)

    class Meta:
        model = Play
