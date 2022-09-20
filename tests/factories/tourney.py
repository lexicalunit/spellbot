from __future__ import annotations

import factory

from spellbot.models import Tourney


class TourneyFactory(factory.alchemy.SQLAlchemyModelFactory):
    id = factory.Sequence(lambda n: n + 1)
    message_xid = factory.Faker("random_int")
    deleted_at = None

    class Meta:
        model = Tourney
        sqlalchemy_session_persistence = "flush"
