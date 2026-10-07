# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import factory

from spellbot.models import Game
from tests.factories.session import factory_session


class GameFactory(factory.alchemy.SQLAlchemyModelFactory):
    seats = 4
    deleted_at = None

    class Meta:
        model = Game
        sqlalchemy_session_factory = factory_session
        sqlalchemy_session_persistence = "flush"
