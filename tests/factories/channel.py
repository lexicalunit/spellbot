from __future__ import annotations

import factory

from spellbot.models import Channel


class ChannelFactory(factory.alchemy.SQLAlchemyModelFactory):
    xid = factory.declarations.Sequence(lambda n: 2000 + n)
    name = factory.faker.Faker("color_name")
    motd = factory.faker.Faker("sentence")

    class Meta:
        model = Channel
        sqlalchemy_session_persistence = "flush"
