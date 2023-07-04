from __future__ import annotations

from typing import Any

import factory
from spellbot.models import Game, Play, Queue, User


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    xid = factory.Sequence(lambda n: 3000 + n)
    name = factory.Faker("name")

    @classmethod
    def _create(cls, model_class: Any, *args: Any, **kwargs: Any) -> Any:
        session = cls._meta.sqlalchemy_session  # type: ignore
        if session is None:  # pragma: no cover
            raise RuntimeError("No session provided.")

        if "game" in kwargs:
            game: Game = kwargs.pop("game")
            if game.started_at is None:
                queue = Queue(game_id=game.id, user_xid=kwargs["xid"])
                session.add(queue)
            else:
                play = Play(game_id=game.id, user_xid=kwargs["xid"])
                session.add(play)

        return super()._create(model_class, *args, **kwargs)

    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"
