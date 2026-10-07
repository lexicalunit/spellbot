# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import factory

from spellbot.models import Token
from tests.factories.session import factory_session


class TokenFactory(factory.alchemy.SQLAlchemyModelFactory):
    key = factory.faker.Faker("numerify")

    class Meta:
        model = Token
        sqlalchemy_session_factory = factory_session
        sqlalchemy_session_persistence = "flush"
