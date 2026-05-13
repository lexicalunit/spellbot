from __future__ import annotations

import factory

from spellbot.models import Game


class GameFactory(factory.alchemy.SQLAlchemyModelFactory):
    seats = 4
    deleted_at = None

    class Meta:
        model = Game
        sqlalchemy_session_persistence = "flush"
