# pylint: disable=attribute-defined-outside-init
from __future__ import annotations

from functools import partial
from typing import Any, Awaitable, Callable, Literal, ParamSpec, TypeVar, Union, cast, overload

import discord
import pytest
from discord.app_commands import Command
from discord.ext import commands

from spellbot import SpellBot
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Game, Guild, User
from spellbot.settings import Settings
from tests.fixtures import Factories
from tests.mocks import build_message


class BaseMixin:
    @pytest.fixture(autouse=True)
    def use_bot(self, bot: SpellBot) -> None:
        self.bot = bot

    @pytest.fixture(autouse=True)
    def use_settings(self, settings: Settings) -> None:
        self.settings = settings

    @pytest.fixture(autouse=True)
    def use_factories(self, factories: Factories) -> None:
        self.factories = factories


CogT = TypeVar("CogT", bound=commands.Cog)
CogCallbackP = ParamSpec("CogCallbackP")


class InteractionMixin(BaseMixin):
    interaction: discord.Interaction

    @pytest.fixture(autouse=True, name="interaction")
    def use_interaction(self, interaction: discord.Interaction) -> discord.Interaction:
        self.interaction = interaction
        return self.interaction

    @pytest.fixture
    def add_guild(self, factories: Factories) -> Callable[..., Guild]:
        return factories.guild.create

    @pytest.fixture(autouse=True, name="guild")
    def _guild(self, add_guild: Callable[..., Guild], interaction: discord.Interaction) -> Guild:
        assert interaction.guild is not None
        self.guild = add_guild(xid=interaction.guild_id, name=interaction.guild.name)
        return self.guild

    @pytest.fixture
    def add_channel(self, factories: Factories, guild: Guild) -> Callable[..., Channel]:
        return partial(factories.channel.create, guild=guild)

    @pytest.fixture(name="channel")
    def _channel(
        self,
        interaction: discord.Interaction,
        add_channel: Callable[..., Channel],
    ) -> Channel:
        assert interaction.channel is not None
        assert hasattr(interaction.channel, "name")
        channel_name = getattr(interaction.channel, "name")
        self.channel = add_channel(xid=interaction.channel_id, name=channel_name)
        return self.channel

    @pytest.fixture
    def add_user(self, factories: Factories) -> Callable[..., User]:
        return factories.user.create

    @pytest.fixture(name="user")
    def _user(self, interaction: discord.Interaction, add_user: Callable[..., User]) -> User:
        self.user = add_user(xid=interaction.user.id)
        return self.user

    @pytest.fixture(name="message")
    def _message(self, interaction: discord.Interaction) -> discord.Message:
        assert interaction.guild is not None
        assert interaction.channel is not None
        assert isinstance(interaction.channel, discord.TextChannel)
        self.message = build_message(interaction.guild, interaction.channel, interaction.user)
        return self.message

    @pytest.fixture(name="game")
    def _game(
        self,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        message: discord.Message,
    ) -> Game:
        self.game = factories.game.create(guild=guild, channel=channel, message_xid=message.id)
        return self.game

    @pytest.fixture
    def player(self, user: User, game: Game) -> User:
        """Puts self.user into a game."""
        user.game = game
        DatabaseSession.commit()
        return user

    @pytest.fixture
    def add_player(self, game: Game, add_user: Callable[..., User]) -> Callable[..., User]:
        return partial(add_user, game=game)

    @overload
    def last_send_message(self, kwarg: Literal["embed"]) -> dict[str, Any]:  # pragma: no cover
        ...

    @overload
    def last_send_message(self, kwarg: Literal["view"]) -> list[dict[str, Any]]:  # pragma: no cover
        ...

    @overload
    def last_send_message(self, kwarg: str) -> Any:  # pragma: no cover
        ...

    def last_send_message(self, kwarg: str) -> Union[dict[str, Any], list[dict[str, Any]], Any]:
        send_message = self.interaction.response.send_message
        send_message.assert_called_once()
        send_message_call = send_message.call_args_list[0]
        actual = send_message_call.kwargs[kwarg]
        if kwarg == "embed":
            actual = actual.to_dict()
        if kwarg == "view":
            actual = actual.to_components()
        return actual

    @overload
    def last_edit_message(self, kwarg: Literal["embed"]) -> dict[str, Any]:  # pragma: no cover
        ...

    @overload
    def last_edit_message(self, kwarg: Literal["view"]) -> list[dict[str, Any]]:  # pragma: no cover
        ...

    def last_edit_message(self, kwarg: str) -> Union[dict[str, Any], list[dict[str, Any]], Any]:
        edit_message = self.interaction.edit_original_response
        edit_message.assert_called_once()
        edit_message_call = edit_message.call_args_list[0]
        actual = edit_message_call.kwargs[kwarg]
        if kwarg == "embed":
            actual = actual.to_dict()
        if kwarg == "view":
            actual = actual.to_components()
        return actual

    # Note: I don't know if there's a better way to use CogCallbackP's .args and .kwargs
    #       here, but everything I've tried seems to run afoul of pyright type checker.
    #       So I'm just using `...` here for now, even though it sucks.
    async def run(self, command: Command[CogT, CogCallbackP, None], **kwargs: Any) -> None:
        interaction = kwargs.get("interaction", None)
        if not interaction:
            kwargs["interaction"] = self.interaction
        callback = command.callback
        if command.binding:
            callback = partial(callback, command.binding)
        callback = cast(Callable[..., Awaitable[None]], callback)
        return await callback(**kwargs)


class ContextMixin(BaseMixin):
    @pytest.fixture(autouse=True, name="context")
    def _context(self, context: commands.Context[SpellBot]) -> commands.Context[SpellBot]:
        self.context = context
        return self.context
