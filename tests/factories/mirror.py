from __future__ import annotations

import factory
from spellbot.models import Mirror


class MirrorFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Mirror
        sqlalchemy_session_persistence = "flush"
