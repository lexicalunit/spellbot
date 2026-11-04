# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import factory

from spellbot.models import Token
from spellbot.services.apps import hash_api_key
from tests.factories.session import factory_session


class TokenFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Create a token from a plaintext `key`; only its hash reaches the database."""

    class Params:
        key = factory.faker.Faker("numerify")

    key_hash = factory.LazyAttribute(lambda token: hash_api_key(token.key))

    class Meta:
        model = Token
        sqlalchemy_session_factory = factory_session
        sqlalchemy_session_persistence = "flush"
