# pylint: disable=attribute-defined-outside-init

import pytest
from discord_slash.context import ComponentContext, InteractionContext, MenuContext

from spellbot import SpellBot
from spellbot.settings import Settings
from tests.fixtures import Factories


class BaseMixin:
    @pytest.fixture(autouse=True)
    def base_before_each(self, bot: SpellBot, settings: Settings, factories: Factories):
        self.bot = bot
        self.settings = settings
        self.factories = factories


class InteractionContextMixin(BaseMixin):
    @pytest.fixture(autouse=True)
    def context_before_each(self, ctx: InteractionContext):
        self.ctx = ctx


class ComponentContextMixin(BaseMixin):
    @pytest.fixture(autouse=True)
    def context_before_each(self, origin_ctx: ComponentContext):
        self.ctx = origin_ctx


class MenuContextMixin(BaseMixin):
    @pytest.fixture(autouse=True)
    def context_before_each(self, ctx: MenuContext):
        self.ctx = ctx
