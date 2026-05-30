from __future__ import annotations

import factory

from spellbot.models import Alert


class AlertFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Alert
        sqlalchemy_session_persistence = "flush"
