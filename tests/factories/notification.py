from __future__ import annotations

import random

import factory

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Notification


class NotificationFactory(factory.alchemy.SQLAlchemyModelFactory):
    id = factory.declarations.Sequence(lambda n: n + 1)
    guild = factory.declarations.Sequence(lambda n: 1000 + n)
    channel = factory.declarations.Sequence(lambda n: 2000 + n)
    players = factory.faker.Faker("words", nb=4)
    format = random.choice(list(GameFormat)).value  # noqa: S311
    bracket = random.choice(list(GameBracket)).value  # noqa: S311
    service = random.choice(list(GameService)).value  # noqa: S311
    link = factory.faker.Faker("url")

    class Meta:
        model = Notification
        sqlalchemy_session_persistence = "flush"
