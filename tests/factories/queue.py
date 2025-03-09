from __future__ import annotations

import factory

from spellbot.models import Queue


class QueueFactory(factory.alchemy.SQLAlchemyModelFactory):
    og_guild_xid = factory.faker.Faker("random_int")

    class Meta:
        model = Queue
        sqlalchemy_session_persistence = "flush"
