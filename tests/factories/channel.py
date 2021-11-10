import factory

from spellbot.models import Channel


class ChannelFactory(factory.alchemy.SQLAlchemyModelFactory):
    xid = factory.Sequence(lambda n: 2000 + n)
    name = factory.Faker("color_name")
    motd = factory.Faker("sentence")

    class Meta:
        model = Channel
        sqlalchemy_session_persistence = "flush"
