import factory

from spellbot.models.award import GuildAward, UserAward


class GuildAwardFactory(factory.alchemy.SQLAlchemyModelFactory):
    id = factory.Sequence(lambda n: n + 1)
    message = factory.Faker("sentence")
    count = factory.Faker("random_int", min=1, max=100)
    role = factory.Faker("color_name")

    class Meta:
        model = GuildAward
        sqlalchemy_session_persistence = "flush"


class UserAwardFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = UserAward
        sqlalchemy_session_persistence = "flush"
