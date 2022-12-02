from __future__ import annotations

import factory
from spellbot.models import User


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    xid = factory.Sequence(lambda n: 3000 + n)
    name = factory.Faker("name")

    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"
