# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import factory

from spellbot.models import Verify
from tests.factories.session import factory_session


class VerifyFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Verify
        sqlalchemy_session_factory = factory_session
        sqlalchemy_session_persistence = "flush"
