from __future__ import annotations

import factory
from spellbot.models import Play


class PlayFactory(factory.alchemy.SQLAlchemyModelFactory):
    points = factory.Faker("random_int", max=10)
    og_guild_xid = factory.Faker("random_int")

    class Meta:
        model = Play
        sqlalchemy_session_persistence = "flush"
