from __future__ import annotations

import factory

from spellbot.models import Token


class TokenFactory(factory.alchemy.SQLAlchemyModelFactory):
    key = factory.Faker("numerify")

    class Meta:
        model = Token
        sqlalchemy_session_persistence = "flush"
