import factory

from spellbot.models.guild import Guild


class GuildFactory(factory.alchemy.SQLAlchemyModelFactory):
    xid = factory.Sequence(lambda n: 1000 + n)
    name = factory.Faker("company")
    motd = factory.Faker("sentence")

    class Meta:
        model = Guild
