from __future__ import annotations

from random import randint
from typing import Any

import factory

from spellbot.models import Game, Play, Post, Queue, User


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    xid = factory.declarations.Sequence(lambda n: 3000 + n)
    name = factory.faker.Faker("name")

    @classmethod
    def _create(cls, model_class: Any, *args: Any, **kwargs: Any) -> Any:
        session = cls._meta.sqlalchemy_session  # type: ignore
        if session is None:  # pragma: no cover
            raise RuntimeError("No session provided.")

        if "game" in kwargs:
            game: Game = kwargs.pop("game")
            if game.started_at is None:
                queue = Queue(game_id=game.id, user_xid=kwargs["xid"], og_guild_xid=game.guild_xid)
                session.add(queue)
            else:
                play = Play(game_id=game.id, user_xid=kwargs["xid"], og_guild_xid=game.guild_xid)
                session.add(play)
            with session.no_autoflush:
                if not game.posts:
                    post = Post(
                        game_id=game.id,
                        guild_xid=game.guild_xid,
                        channel_xid=game.channel_xid,
                        message_xid=randint(1000, 9999),  # noqa: S311
                    )
                    session.add(post)
                    game.posts = [post]  # type: ignore

        return super()._create(model_class, *args, **kwargs)

    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"
