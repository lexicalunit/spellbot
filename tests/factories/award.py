from __future__ import annotations

import factory

from spellbot.models import GuildAward, UserAward


class GuildAwardFactory(factory.alchemy.SQLAlchemyModelFactory):
    id = factory.declarations.Sequence(lambda n: n + 1)
    message = factory.faker.Faker("sentence")
    count = factory.faker.Faker("random_int", min=1, max=100)
    role = factory.faker.Faker("color_name")
    remove = False

    class Meta:
        model = GuildAward
        sqlalchemy_session_persistence = "flush"


class UserAwardFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = UserAward
        sqlalchemy_session_persistence = "flush"
