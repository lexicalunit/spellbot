# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import factory

from spellbot.models import Block
from tests.factories.session import factory_session


class BlockFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Block
        sqlalchemy_session_factory = factory_session
        sqlalchemy_session_persistence = "flush"
