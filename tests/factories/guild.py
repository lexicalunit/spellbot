from __future__ import annotations

import factory
from spellbot.models import Guild


class GuildFactory(factory.alchemy.SQLAlchemyModelFactory):
    xid = factory.Sequence(lambda n: 1000 + n)
    name = factory.Faker("company")
    motd = factory.Faker("sentence")

    class Meta:
        model = Guild
        sqlalchemy_session_persistence = "flush"
