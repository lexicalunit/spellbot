from __future__ import annotations

import factory

from spellbot.models import Post


class PostFactory(factory.alchemy.SQLAlchemyModelFactory):
    message_xid = factory.faker.Faker("random_int")

    class Meta:
        model = Post
        sqlalchemy_session_persistence = "flush"
