from __future__ import annotations

import factory

from spellbot.models import Record


class RecordFactory(factory.alchemy.SQLAlchemyModelFactory):
    elo = factory.faker.Faker("random_int")

    class Meta:
        model = Record
        sqlalchemy_session_persistence = "flush"
