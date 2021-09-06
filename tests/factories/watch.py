import factory

from spellbot.models.watch import Watch


class WatchFactory(factory.alchemy.SQLAlchemyModelFactory):
    note = factory.Faker("sentence")

    class Meta:
        model = Watch
