# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import factory

from spellbot.models import Play
from tests.factories.session import factory_session


class PlayFactory(factory.alchemy.SQLAlchemyModelFactory):
    og_guild_xid = factory.faker.Faker("random_int")

    class Meta:
        model = Play
        sqlalchemy_session_factory = factory_session
        sqlalchemy_session_persistence = "flush"
