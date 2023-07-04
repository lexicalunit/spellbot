from __future__ import annotations

import factory
from spellbot.models import Queue


class QueueFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Queue
        sqlalchemy_session_persistence = "flush"
