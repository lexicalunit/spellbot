# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import factory

from spellbot.models import Post
from tests.factories.session import factory_session


class PostFactory(factory.alchemy.SQLAlchemyModelFactory):
    message_xid = factory.faker.Faker("random_int")

    class Meta:
        model = Post
        sqlalchemy_session_factory = factory_session
        sqlalchemy_session_persistence = "flush"
