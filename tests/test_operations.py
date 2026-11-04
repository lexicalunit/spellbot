# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp
import discord
import pytest
from aiohttp.client_exceptions import ClientOSError
from decoy import Decoy, matchers
from discord.errors import DiscordException
from discord.utils import MISSING

from spellbot import operations
from spellbot.operations import (
    VoiceChannelSuggestion,
    retry,
    safe_add_role,
    safe_channel_reply,
    safe_create_category_channel,
    safe_create_channel_invite,
    safe_create_voice_channel,
    safe_defer_interaction,
    safe_delete_channel,
    safe_delete_message,
    safe_ensure_voice_category,
    safe_fetch_guild,
    safe_fetch_text_channel,
    safe_fetch_user,
    safe_followup_channel,
    safe_get_partial_message,
    safe_original_response,
    safe_send_channel,
    safe_send_user,
    safe_suggest_voice_channel,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.utils import CANT_SEND_CODE, NO_MUTUAL_GUILDS_CODE, UNKNOWN_CHANNEL_CODE
from tests.mocks import decoys, mock_client
from tests.mocks.decoys import bot_with, guild_with, partial_object, text_channel

if TYPE_CHECKING:
    from tests.fixtures import Stub

READ = discord.Permissions(
    discord.Permissions.read_messages.flag | discord.Permissions.read_message_history.flag,
)
SEND = discord.Permissions(discord.Permissions.send_messages.flag)
MANAGE_CHANNELS = discord.Permissions(discord.Permissions.manage_channels.flag)
MANAGE_MESSAGES = discord.Permissions.manage_messages.flag
MANAGE_ROLES = discord.Permissions.manage_roles.flag


def response(decoy: Decoy, status: int = 400) -> aiohttp.ClientResponse:
    """Build the HTTP response that a discord.py error is raised for."""
    found = decoy.mock(cls=aiohttp.ClientResponse)
    found.status = status
    return found


@pytest.mark.asyncio
class TestOperationsRetry:
    @pytest.fixture(autouse=True)
    def no_sleep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(operations, "sleep", decoys.async_returning(None))

    async def test_happy_path(self) -> None:
        async def func() -> int:
            return 1

        assert await retry(func) == 1

    async def test_failure(self) -> None:
        async def func() -> int:
            raise ClientOSError

        with pytest.raises(ClientOSError):
            await retry(func)

    async def test_retries(self) -> None:
        tried_once = False

        async def func() -> int:
            nonlocal tried_once
            if not tried_once:
                tried_once = True
                raise ClientOSError
            return 1

        assert await retry(func) == 1
        assert tried_once

    async def test_discord_server_error_marked_as_warning(self, decoy: Decoy) -> None:
        error = discord.errors.DiscordServerError(response(decoy, 503), "server error")

        async def func() -> int:
            raise error

        with pytest.raises(discord.errors.DiscordServerError):
            await retry(func)

    async def test_rate_limited_marked_as_warning(self, decoy: Decoy, stub: Stub) -> None:
        error = discord.errors.HTTPException(
            response(decoy, 429),
            {"code": 40062, "message": "Service resource is being rate limited."},
        )

        async def func() -> int:
            raise error

        ignore = stub(operations, "ignore_exception_on_all_spans")
        with pytest.raises(discord.errors.HTTPException):
            await retry(func)

        decoy.verify(ignore(error, warning_type="discord_rate_limited"), times=1)

    async def test_rate_limited_exception_marked_as_warning(
        self,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        error = discord.errors.RateLimited(retry_after=1.5)

        async def func() -> int:
            raise error

        ignore = stub(operations, "ignore_exception_on_all_spans")
        with pytest.raises(discord.errors.RateLimited):
            await retry(func)

        decoy.verify(ignore(error, warning_type="discord_rate_limited"), times=1)

    async def test_other_http_error_is_not_a_rate_limit_warning(
        self,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        error = discord.errors.HTTPException(
            response(decoy, 400),
            {"code": 50035, "message": "bad"},
        )

        async def func() -> int:
            raise error

        ignore = stub(operations, "ignore_exception_on_all_spans")
        with pytest.raises(discord.errors.HTTPException):
            await retry(func)

        decoy.verify(ignore(error), times=0, ignore_extra_args=True)


@pytest.mark.asyncio
class TestOperationsDeferInteraction:
    async def test_happy_path(self, decoy: Decoy, interaction: discord.Interaction) -> None:
        assert await safe_defer_interaction(interaction)
        decoy.verify(await interaction.response.defer(), times=1)

    @pytest.mark.parametrize(
        ("kind", "status", "code"),
        [
            pytest.param(discord.errors.NotFound, 404, 10062, id="unknown-interaction"),
            pytest.param(discord.errors.NotFound, 404, 99999, id="not-found-other-code"),
            pytest.param(discord.errors.HTTPException, 400, 40060, id="already-acknowledged"),
            pytest.param(discord.errors.HTTPException, 400, 99999, id="http-other-code"),
        ],
    )
    async def test_discord_errors(
        self,
        decoy: Decoy,
        interaction: discord.Interaction,
        kind: type[discord.errors.HTTPException],
        status: int,
        code: int,
    ) -> None:
        error = kind(response(decoy, status), {"code": code})
        decoy.when(await interaction.response.defer()).then_raise(error)
        assert await safe_defer_interaction(interaction) is False

    async def test_discord_exception(self, decoy: Decoy, interaction: discord.Interaction) -> None:
        decoy.when(await interaction.response.defer()).then_raise(DiscordException())
        assert await safe_defer_interaction(interaction) is False


@pytest.mark.asyncio
class TestOperationsOriginalResponse:
    async def test_happy_path(self, decoy: Decoy, interaction: discord.Interaction) -> None:
        original = decoy.mock(cls=discord.InteractionMessage)
        decoy.when(await interaction.original_response()).then_return(original)
        assert await safe_original_response(interaction) is original

    async def test_unknown_message(self, decoy: Decoy, interaction: discord.Interaction) -> None:
        error = discord.errors.NotFound(response(decoy, 404), {"code": 10008})
        decoy.when(await interaction.original_response()).then_raise(error)
        assert await safe_original_response(interaction) is None


@pytest.mark.asyncio
class TestOperationsFetchUser:
    async def test_cached(self, decoy_member: discord.Member) -> None:
        client = mock_client(users=[decoy_member])
        assert await safe_fetch_user(client, decoy_member.id) is decoy_member

    async def test_uncached(
        self,
        decoy_member: discord.Member,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(users=[decoy_member])
        monkeypatch.setattr(client, "get_user", lambda _: None)
        assert await safe_fetch_user(client, decoy_member.id) is decoy_member


@pytest.mark.asyncio
class TestOperationsFetchGuild:
    async def test_cached(self, decoy_guild: discord.Guild) -> None:
        client = mock_client(guilds=[decoy_guild])
        assert await safe_fetch_guild(client, decoy_guild.id) is decoy_guild

    async def test_uncached(
        self,
        decoy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(guilds=[decoy_guild])
        monkeypatch.setattr(client, "get_guild", lambda _: None)
        assert await safe_fetch_guild(client, decoy_guild.id) is decoy_guild


@pytest.mark.asyncio
class TestOperationsFetchTextChannel:
    @pytest.fixture
    def guild(self, decoy: Decoy) -> discord.Guild:
        """Build a guild where the bot can read messages."""
        return guild_with(decoy, bot_with(decoy, discord.Permissions.read_messages.flag))

    @pytest.fixture
    def channel(self, decoy: Decoy, guild: discord.Guild) -> discord.TextChannel:
        channel = text_channel(decoy, guild)
        channel.id = 3001
        return channel

    def uncached_client(
        self,
        monkeypatch: pytest.MonkeyPatch,
        channels: list[discord.TextChannel],
        guilds: list[discord.Guild] | None = None,
    ) -> discord.Client:
        """Build a client that has to fetch `channels`, since none of them are cached."""
        client = mock_client(channels=channels, guilds=guilds or [])
        monkeypatch.setattr(client, "get_channel", lambda _: None)
        return client

    async def test_cached(self, channel: discord.TextChannel) -> None:
        client = mock_client(channels=[channel])
        assert await safe_fetch_text_channel(client, 0, channel.id) is channel

    async def test_uncached(
        self,
        channel: discord.TextChannel,
        guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = self.uncached_client(monkeypatch, [channel], [guild])
        assert await safe_fetch_text_channel(client, guild.id, channel.id) is channel

    async def test_uncached_no_guild(
        self,
        channel: discord.TextChannel,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = self.uncached_client(monkeypatch, [channel])
        assert await safe_fetch_text_channel(client, 0, channel.id) is None

    async def test_non_text(self, decoy: Decoy) -> None:
        channel = decoy.mock(cls=discord.DMChannel)
        channel.id = 3002
        client = mock_client(channels=[channel])
        assert await safe_fetch_text_channel(client, 0, channel.id) is None

    async def test_uncached_non_text(
        self,
        decoy: Decoy,
        guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        channel = decoy.mock(cls=discord.VoiceChannel)
        channel.id = 3003
        client = mock_client(channels=[channel], guilds=[guild])
        monkeypatch.setattr(client, "get_channel", lambda _: None)
        assert await safe_fetch_text_channel(client, guild.id, channel.id) is None

    async def test_uncached_with_no_read_permissions(
        self,
        decoy: Decoy,
        channel: discord.TextChannel,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        guild = guild_with(decoy, bot_with(decoy))
        client = self.uncached_client(monkeypatch, [channel], [guild])
        assert await safe_fetch_text_channel(client, guild.id, channel.id) is None

    async def test_uncached_with_no_permissions(
        self,
        decoy: Decoy,
        channel: discord.TextChannel,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bad_guild = guild_with(decoy, None)
        client = self.uncached_client(monkeypatch, [channel], [bad_guild])
        assert await safe_fetch_text_channel(client, bad_guild.id, channel.id) is None

    async def test_unknown_channel(
        self,
        decoy: Decoy,
        channel: discord.TextChannel,
        guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.INFO)
        client = self.uncached_client(monkeypatch, [channel], [guild])
        error = discord.errors.NotFound(response(decoy, 404), {"code": UNKNOWN_CHANNEL_CODE})
        monkeypatch.setattr(client, "fetch_channel", decoys.async_raising(error))

        assert await safe_fetch_text_channel(client, guild.id, channel.id) is None

        assert "already deleted" in caplog.text
        assert not [record for record in caplog.records if record.levelno >= logging.WARNING]

    async def test_not_found_other_code(
        self,
        decoy: Decoy,
        channel: discord.TextChannel,
        guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        client = self.uncached_client(monkeypatch, [channel], [guild])
        error = discord.errors.NotFound(response(decoy, 404), {"code": 99999})
        monkeypatch.setattr(client, "fetch_channel", decoys.async_raising(error))

        assert await safe_fetch_text_channel(client, guild.id, channel.id) is None

        assert "could not fetch channel" in caplog.text


@pytest.mark.asyncio
class TestOperationsGetPartialMessage:
    @pytest.fixture
    def guild(self, decoy: Decoy) -> discord.Guild:
        return guild_with(decoy, bot_with(decoy))

    @pytest.fixture
    def message(self, decoy: Decoy) -> discord.PartialMessage:
        message = decoy.mock(cls=discord.PartialMessage)
        message.id = 4001
        return message

    async def test_happy_path(
        self,
        decoy: Decoy,
        guild: discord.Guild,
        message: discord.PartialMessage,
    ) -> None:
        channel = text_channel(decoy, guild, READ)
        decoy.when(channel.get_partial_message(message.id)).then_return(message)
        assert safe_get_partial_message(channel, guild.id, message.id) is message

    async def test_not_text(
        self,
        decoy: Decoy,
        guild: discord.Guild,
        message: discord.PartialMessage,
    ) -> None:
        channel = decoy.mock(cls=discord.VoiceChannel)
        channel.guild = guild
        decoy.when(channel.type).then_return(discord.ChannelType.voice)
        decoy.when(channel.permissions_for(matchers.Anything())).then_return(READ)
        assert not safe_get_partial_message(channel, guild.id, message.id)

    async def test_no_permissions(
        self,
        decoy: Decoy,
        guild: discord.Guild,
        message: discord.PartialMessage,
    ) -> None:
        channel = text_channel(decoy, guild, discord.Permissions())
        assert not safe_get_partial_message(channel, guild.id, message.id)


@pytest.mark.asyncio
class TestOperationsUpdateEmbed:
    @pytest.fixture
    def message(self, decoy: Decoy) -> discord.Message:
        message = decoy.mock(cls=discord.Message)
        message.id = 123
        message.guild = guild_with(decoy)
        return message

    async def test_happy_path(self, decoy: Decoy, message: discord.Message) -> None:
        edited = decoy.mock(cls=discord.Message)
        decoy.when(await message.edit(content="content", embed=None)).then_return(edited)
        assert await safe_update_embed(message, content="content", embed=None) is edited

    async def test_exception(self, decoy: Decoy, message: discord.Message) -> None:
        decoy.when(await message.edit(content="content", embed=None)).then_raise(DiscordException())
        assert not await safe_update_embed(message, content="content", embed=None)

    async def test_not_found(self, decoy: Decoy, message: discord.Message) -> None:
        error = discord.errors.NotFound(response(decoy, 404), "msg")
        decoy.when(await message.edit(content="content", embed=None)).then_raise(error)
        assert not await safe_update_embed(message, content="content", embed=None)

    async def test_unknown_message(self, decoy: Decoy, message: discord.Message) -> None:
        error = discord.errors.NotFound(response(decoy, 404), {"code": 10008})
        decoy.when(await message.edit(content="content", embed=None)).then_raise(error)
        assert await safe_update_embed(message, content="content", embed=None) is None


@pytest.mark.asyncio
class TestOperationsUpdateEmbedOrigin:
    async def test_happy_path(
        self,
        decoy: Decoy,
        interaction: discord.Interaction,
        message: discord.Message,
    ) -> None:
        interaction.message = message
        edited = decoy.mock(cls=discord.InteractionMessage)
        edit = interaction.edit_original_response(content="content", embed=None)
        decoy.when(await edit).then_return(edited)
        assert await safe_update_embed_origin(interaction, content="content", embed=None)

    async def test_exception(
        self,
        decoy: Decoy,
        interaction: discord.Interaction,
        message: discord.Message,
    ) -> None:
        interaction.message = message
        edit = interaction.edit_original_response(content="content", embed=None)
        decoy.when(await edit).then_raise(DiscordException())
        assert not await safe_update_embed_origin(interaction, content="content", embed=None)


@pytest.mark.asyncio
class TestOperationsCreateCategoryChannel:
    async def test_happy_path(self, decoy: Decoy, decoy_guild: discord.Guild) -> None:
        client = mock_client(guilds=[decoy_guild])
        await safe_create_category_channel(client, decoy_guild.id, "name")
        decoy.verify(await decoy_guild.create_category_channel("name"))

    async def test_no_permissions(
        self,
        decoy: Decoy,
        decoy_guild: discord.Guild,
        stub: Stub,
    ) -> None:
        bot_can_manage_channels_fake = stub(operations, "bot_can_manage_channels")
        decoy.when(bot_can_manage_channels_fake(decoy_guild)).then_return(False)
        client = mock_client(guilds=[decoy_guild])
        response = await safe_create_category_channel(client, decoy_guild.id, "name")
        decoy.verify(
            await decoy_guild.create_category_channel(matchers.Anything()),
            times=0,
            ignore_extra_args=True,
        )
        assert response is None

    async def test_uncached(
        self,
        decoy: Decoy,
        decoy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(guilds=[decoy_guild])
        monkeypatch.setattr(client, "get_guild", lambda _: None)
        await safe_create_category_channel(client, decoy_guild.id, "name")
        decoy.verify(await decoy_guild.create_category_channel("name"))

    async def test_not_found(self, decoy: Decoy, decoy_guild: discord.Guild) -> None:
        client = mock_client()
        await safe_create_category_channel(client, decoy_guild.id, "name")
        decoy.verify(
            await decoy_guild.create_category_channel(matchers.Anything()),
            times=0,
            ignore_extra_args=True,
        )


@pytest.mark.asyncio
class TestOperationsCreateChannelInvite:
    async def test_happy_path(self, decoy: Decoy) -> None:
        channel = decoy.mock(cls=discord.TextChannel)
        await safe_create_channel_invite(channel)
        decoy.verify(await channel.create_invite())

    async def test_exception(self, decoy: Decoy) -> None:
        channel = decoy.mock(cls=discord.TextChannel)
        decoy.when(await channel.create_invite()).then_raise(DiscordException())
        invite = await safe_create_channel_invite(channel)
        assert invite is None


@pytest.mark.asyncio
class TestOperationsCreateVoiceChannel:
    async def test_happy_path(self, decoy: Decoy, decoy_guild: discord.Guild) -> None:
        category = decoy.mock(cls=discord.CategoryChannel)
        client = mock_client(guilds=[decoy_guild])
        await safe_create_voice_channel(client, decoy_guild.id, "name", category=category)
        decoy.verify(
            await decoy_guild.create_voice_channel(
                "name",
                category=category,
                bitrate=MISSING,
            ),
        )

    async def test_uncached(
        self,
        decoy: Decoy,
        decoy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        category = decoy.mock(cls=discord.CategoryChannel)
        decoy.when(decoy_guild.bitrate_limit).then_return(96000.0)
        client = mock_client(guilds=[decoy_guild])
        monkeypatch.setattr(client, "get_guild", lambda _: None)
        await safe_create_voice_channel(
            client,
            decoy_guild.id,
            "name",
            category=category,
            use_max_bitrate=True,
        )
        decoy.verify(
            await decoy_guild.create_voice_channel(
                "name",
                category=category,
                bitrate=96000,
            ),
        )

    async def test_not_found(self, decoy: Decoy, decoy_guild: discord.Guild) -> None:
        category = decoy.mock(cls=discord.CategoryChannel)
        client = mock_client()
        await safe_create_voice_channel(
            client,
            decoy_guild.id,
            "name",
            category=category,
            use_max_bitrate=False,
        )
        decoy.verify(
            await decoy_guild.create_voice_channel(matchers.Anything()),
            times=0,
            ignore_extra_args=True,
        )


@pytest.mark.asyncio
class TestOperationsSendChannel:
    async def test_happy_path(self, decoy: Decoy, interaction: discord.Interaction) -> None:
        original = decoy.mock(cls=discord.InteractionMessage)
        decoy.when(await interaction.original_response()).then_return(original)

        # The sent message is the interaction's original response.
        assert await safe_send_channel(interaction, "content") is original
        decoy.verify(await interaction.response.send_message("content"), times=1)

    async def test_error_during_send(
        self,
        decoy: Decoy,
        interaction: discord.Interaction,
    ) -> None:
        error = discord.errors.NotFound(response(decoy, 404), "not found")
        decoy.when(await interaction.response.send_message("content")).then_raise(error)
        assert await safe_send_channel(interaction, "content") is None


@pytest.mark.asyncio
class TestOperationsFollowupChannel:
    async def test_happy_path(self, decoy: Decoy, interaction: discord.Interaction) -> None:
        sent = decoy.mock(cls=discord.WebhookMessage)
        decoy.when(await interaction.followup.send("content", wait=True)).then_return(sent)
        assert await safe_followup_channel(interaction, "content") is sent

    async def test_remove_view(self, decoy: Decoy, interaction: discord.Interaction) -> None:
        sent = decoy.mock(cls=discord.WebhookMessage)
        followup = interaction.followup.send("content", view=MISSING, wait=True)
        decoy.when(await followup).then_return(sent)
        assert await safe_followup_channel(interaction, "content", view=None) is sent


@pytest.mark.asyncio
class TestOperationsDeleteChannel:
    @pytest.fixture
    def guild(self, decoy: Decoy) -> discord.Guild:
        return guild_with(decoy, bot_with(decoy))

    async def test_happy_path(self, decoy: Decoy, guild: discord.Guild) -> None:
        channel = text_channel(decoy, guild, MANAGE_CHANNELS)
        channel.id = 3
        assert await safe_delete_channel(channel, guild.id)
        decoy.verify(await channel.delete(), times=1)

    async def test_not_found(self, decoy: Decoy, guild: discord.Guild) -> None:
        channel = text_channel(decoy, guild, MANAGE_CHANNELS)
        channel.id = 3
        error = discord.errors.NotFound(response(decoy, 404), "msg")
        decoy.when(await channel.delete()).then_raise(error)
        assert not await safe_delete_channel(channel, guild.id)

    async def test_missing_channel_id(self, guild: discord.Guild) -> None:
        channel = partial_object(
            type=discord.ChannelType.text,
            guild=guild,
            permissions_for=lambda _: MANAGE_CHANNELS,
            delete=decoys.async_raising(AssertionError("deleted a channel without an id")),
        )
        assert not await safe_delete_channel(channel, guild.id)

    async def test_missing_channel_delete(self, guild: discord.Guild) -> None:
        channel = partial_object(
            id=3,
            type=discord.ChannelType.text,
            guild=guild,
            permissions_for=lambda _: MANAGE_CHANNELS,
        )
        assert not await safe_delete_channel(channel, guild.id)

    async def test_missing_permissions(self, decoy: Decoy, guild: discord.Guild) -> None:
        channel = text_channel(decoy, guild, discord.Permissions())
        assert not await safe_delete_channel(channel, guild.id)
        decoy.verify(await channel.delete(), times=0, ignore_extra_args=True)


@pytest.mark.asyncio
class TestOperationsChannelReply:
    async def test_happy_path(self, decoy: Decoy) -> None:
        channel = text_channel(decoy, guild_with(decoy, bot_with(decoy)), SEND)
        embed = discord.Embed()
        await safe_channel_reply(channel, "content", embed=embed)
        decoy.verify(await channel.send("content", embed=embed), times=1)

    async def test_can_not_send(self, decoy: Decoy, stub: Stub) -> None:
        channel = text_channel(decoy, guild_with(decoy, bot_with(decoy)), SEND)
        bot_can_send_messages_fake = stub(operations, "bot_can_send_messages")
        decoy.when(bot_can_send_messages_fake(channel)).then_return(False)
        assert not await safe_channel_reply(channel, "content", embed=discord.Embed())
        decoy.verify(await channel.send(), times=0, ignore_extra_args=True)


@pytest.mark.asyncio
class TestOperationsSendUser:
    @pytest.fixture
    def user(self, decoy: Decoy) -> discord.Member:
        user = decoy.mock(cls=discord.Member)
        user.id = 1234
        return user

    async def test_happy_path(self, decoy: Decoy, user: discord.Member) -> None:
        embed = discord.Embed()
        await safe_send_user(user, "content", embed=embed)
        decoy.verify(await user.send("content", embed=embed), times=1)

    async def test_not_sendable(self, caplog: pytest.LogCaptureFixture) -> None:
        user = partial_object(id=1234)
        await safe_send_user(user, "content")
        assert f"no send method on user {user} 1234" in caplog.text

    async def test_forbidden_no_mutual_guilds(
        self,
        decoy: Decoy,
        user: discord.Member,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.INFO)
        exception = discord.errors.Forbidden(response(decoy, 403), "msg")
        exception.code = NO_MUTUAL_GUILDS_CODE
        decoy.when(await user.send("content")).then_raise(exception)
        await safe_send_user(user, "content")
        assert f"not allowed to send message to {user} 1234" in caplog.text

    async def test_forbidden_no_mutual_guilds_without_an_id(
        self,
        decoy: Decoy,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.INFO)
        exception = discord.errors.Forbidden(response(decoy, 403), "msg")
        exception.code = NO_MUTUAL_GUILDS_CODE
        user = partial_object(send=decoys.async_raising(exception))
        await safe_send_user(user, "content")
        assert f"not allowed to send message to {user} None" in caplog.text

    async def test_forbidden_other_code(
        self,
        decoy: Decoy,
        user: discord.Member,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        error = discord.errors.Forbidden(response(decoy, 403), "msg")
        decoy.when(await user.send("content")).then_raise(error)
        await safe_send_user(user, "content")
        assert f"failed to send message to user {user} 1234" in caplog.text

    async def test_cant_send(
        self,
        decoy: Decoy,
        user: discord.Member,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.INFO)
        exception = discord.errors.HTTPException(response(decoy), "msg")
        exception.code = CANT_SEND_CODE
        decoy.when(await user.send("content")).then_raise(exception)
        await safe_send_user(user, "content")
        assert f"not allowed to send message to {user} 1234" in caplog.text

    async def test_http_failure(
        self,
        decoy: Decoy,
        user: discord.Member,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        error = discord.errors.HTTPException(response(decoy), "msg")
        decoy.when(await user.send("content")).then_raise(error)
        await safe_send_user(user, "content")
        assert f"failed to send message to user {user} 1234" in caplog.text

    async def test_server_error(
        self,
        decoy: Decoy,
        user: discord.Member,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        error = discord.errors.DiscordServerError(response(decoy, 500), "msg")
        decoy.when(await user.send("content")).then_raise(error)
        await safe_send_user(user, "content")
        assert f"discord server error sending to user {user} 1234" in caplog.text

    async def test_client_error(
        self,
        decoy: Decoy,
        user: discord.Member,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(operations, "sleep", decoys.async_returning(None))
        decoy.when(await user.send("content")).then_raise(ClientOSError())
        await safe_send_user(user, "content")
        assert f"client error sending to user {user} 1234" in caplog.text

    @pytest.mark.no_dm_limiter_patch
    async def test_rate_limit_denies_send(
        self,
        caplog: pytest.LogCaptureFixture,
        decoy: Decoy,
        stub: Stub,
        user: discord.Member,
    ) -> None:
        caplog.set_level(logging.INFO)
        try_consume_dm_slot_fake = stub(operations, "try_consume_dm_slot")
        decoy.when(await try_consume_dm_slot_fake("notification")).then_return(False)

        await safe_send_user(user, "content", kind="notification")

        decoy.verify(await user.send(), times=0, ignore_extra_args=True)
        assert "dm rate limit reached" in caplog.text


@pytest.mark.asyncio
class TestOperationsAddRole:
    def guild(
        self,
        decoy: Decoy,
        role_names: list[str],
        *,
        flags: tuple[int, ...] = (MANAGE_ROLES,),
        top_role: str | None = None,
    ) -> tuple[discord.Guild, list[discord.Role]]:
        """Build a guild with the given roles, where the bot's own top role is `top_role`."""
        me = bot_with(decoy, *flags)
        guild = guild_with(decoy, me)
        guild.id = 201
        guild.name = "guild"
        roles = [
            decoys.role(decoy, guild, role_id=i, name=name)
            for i, name in enumerate(role_names, start=2)
        ]
        decoy.when(guild.roles).then_return(roles)
        if top_role is not None:
            decoy.when(me.top_role).then_return(next(r for r in roles if r.name == top_role))
        return guild, roles

    def member(self, decoy: Decoy) -> discord.Member:
        member = decoy.mock(cls=discord.Member)
        member.id = 101
        decoy.when(member.roles).then_return([])
        return member

    async def test_happy_path(self, decoy: Decoy) -> None:
        member = self.member(decoy)
        guild, [role] = self.guild(decoy, ["role"], top_role="role")
        await safe_add_role(member, guild, "role")
        decoy.verify(await member.add_roles(role), times=1)

    async def test_add_everyone_role(self, decoy: Decoy) -> None:
        member = self.member(decoy)
        guild, _ = self.guild(decoy, ["@everyone"])
        await safe_add_role(member, guild, "@everyone")
        decoy.verify(await member.add_roles(), times=0, ignore_extra_args=True)

    async def test_remove(self, decoy: Decoy) -> None:
        member = self.member(decoy)
        guild, [role] = self.guild(decoy, ["role"], top_role="role")
        await safe_add_role(member, guild, "role", remove=True)
        decoy.verify(await member.remove_roles(role), times=1)

    async def test_user_cached_member(self, decoy: Decoy) -> None:
        user = partial_object(id=101)  # a user, rather than a member, has no roles
        member = self.member(decoy)
        guild, [role] = self.guild(decoy, ["role"], top_role="role")
        decoy.when(guild.get_member(user.id)).then_return(member)
        await safe_add_role(user, guild, "role")
        decoy.verify(await guild.fetch_member(user.id), times=0)
        decoy.verify(await member.add_roles(role), times=1)

    async def test_user_fetched_member(self, decoy: Decoy) -> None:
        user = partial_object(id=101)
        member = self.member(decoy)
        guild, [role] = self.guild(decoy, ["role"], top_role="role")
        decoy.when(await guild.fetch_member(user.id)).then_return(member)
        await safe_add_role(user, guild, "role")
        decoy.verify(await member.add_roles(role), times=1)

    async def test_no_member(self, decoy: Decoy, caplog: pytest.LogCaptureFixture) -> None:
        user = partial_object(id=101)
        guild, _ = self.guild(decoy, [])
        error = discord.errors.NotFound(response(decoy, 404), "Unknown Member")
        decoy.when(await guild.fetch_member(user.id)).then_raise(error)
        await safe_add_role(user, guild, "role")
        assert (
            "warning: in guild guild (201), could not manage role role:"
            f" could not find member: {user}"
        ) in caplog.text

    async def test_no_role(self, decoy: Decoy, caplog: pytest.LogCaptureFixture) -> None:
        guild, _ = self.guild(decoy, [])
        await safe_add_role(self.member(decoy), guild, "role")
        assert (
            "warning: in guild guild (201), could not manage role: could not find role: role"
        ) in caplog.text

    async def test_no_permissions(self, decoy: Decoy, caplog: pytest.LogCaptureFixture) -> None:
        guild, _ = self.guild(decoy, ["role"], flags=())
        await safe_add_role(self.member(decoy), guild, "role")
        assert (
            "warning: in guild guild (201), could not manage role:"
            " no permissions to manage role: role"
        ) in caplog.text

    async def test_bad_role_hierarchy(self, decoy: Decoy, caplog: pytest.LogCaptureFixture) -> None:
        guild, _ = self.guild(decoy, ["admin_role", "user_role"], top_role="user_role")
        await safe_add_role(self.member(decoy), guild, "admin_role")
        assert (
            "warning: in guild guild (201), could not manage role:"
            " no permissions to manage role: admin_role"
        ) in caplog.text

    async def test_forbidden(self, decoy: Decoy, caplog: pytest.LogCaptureFixture) -> None:
        member = self.member(decoy)
        guild, [role] = self.guild(decoy, ["role"], top_role="role")
        error = discord.errors.Forbidden(response(decoy, 403), "msg")
        decoy.when(await member.add_roles(role)).then_raise(error)
        await safe_add_role(member, guild, "role")
        assert f"warning: in guild guild (201), could not add role to member {member}" in (
            caplog.text
        )


@pytest.mark.asyncio
class TestOperationsDeleteMessage:
    def message(self, decoy: Decoy, *flags: int) -> discord.Message:
        """Build a message in a guild where the bot has the permissions `flags`."""
        message = decoy.mock(cls=discord.Message)
        message.id = 123
        message.guild = guild_with(decoy, bot_with(decoy, *flags))
        return message

    async def test_happy_path(self, decoy: Decoy) -> None:
        message = self.message(decoy, MANAGE_MESSAGES)
        assert await safe_delete_message(message)
        decoy.verify(await message.delete(), times=1)

    async def test_bad_permissions(self, decoy: Decoy) -> None:
        message = self.message(decoy, discord.Permissions.read_messages.flag)
        assert not await safe_delete_message(message)
        decoy.verify(await message.delete(), times=0, ignore_extra_args=True)

    async def test_own_message_skips_permission_check(self, decoy: Decoy) -> None:
        message = self.message(decoy, discord.Permissions.read_messages.flag)
        assert await safe_delete_message(message, own_message=True)
        decoy.verify(await message.delete(), times=1)

    @pytest.mark.parametrize(
        ("kind", "status", "code"),
        [
            pytest.param(discord.errors.Forbidden, 403, 99999, id="forbidden-other-code"),
            pytest.param(discord.errors.NotFound, 404, 99999, id="not-found-other-code"),
            pytest.param(discord.errors.Forbidden, 403, 50001, id="missing-access"),
            pytest.param(discord.errors.NotFound, 404, 10008, id="unknown-message"),
        ],
    )
    async def test_discord_errors(
        self,
        decoy: Decoy,
        kind: type[discord.errors.HTTPException],
        status: int,
        code: int,
    ) -> None:
        message = self.message(decoy, MANAGE_MESSAGES)
        decoy.when(await message.delete()).then_raise(kind(response(decoy, status), {"code": code}))
        assert not await safe_delete_message(message)

    async def test_discord_exception(self, decoy: Decoy) -> None:
        message = self.message(decoy, MANAGE_MESSAGES)
        decoy.when(await message.delete()).then_raise(DiscordException())
        assert not await safe_delete_message(message)


@pytest.mark.asyncio
class TestEnsureVoiceCategory:
    def category(self, decoy: Decoy, name: str, channels: int = 0) -> discord.CategoryChannel:
        category = decoy.mock(cls=discord.CategoryChannel)
        category.name = name
        voice = decoy.mock(cls=discord.VoiceChannel)
        decoy.when(category.channels).then_return([voice] * channels)
        return category

    def guild(self, decoy: Decoy, categories: list[discord.CategoryChannel]) -> discord.Guild:
        """Build a guild with `categories`, where the bot may manage channels."""
        guild = guild_with(decoy, bot_with(decoy, discord.Permissions.manage_channels.flag))
        guild.id = 101
        decoy.when(guild.categories).then_return(categories)
        return guild

    async def test_available_exists(self, decoy: Decoy) -> None:
        category = self.category(decoy, "voice-channels", channels=1)
        guild = self.guild(decoy, [category])
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is category
        decoy.verify(
            await guild.create_category_channel(matchers.Anything()),
            times=0,
            ignore_extra_args=True,
        )

    async def test_none_exists(self, decoy: Decoy) -> None:
        new_category = self.category(decoy, "voice-channels")
        guild = self.guild(decoy, [])
        decoy.when(await guild.create_category_channel("voice-channels")).then_return(new_category)
        client = mock_client(guilds=[guild])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category

    async def test_none_available(self, decoy: Decoy) -> None:
        new_category = self.category(decoy, "voice-channels 2")
        category = self.category(decoy, "voice-channels", channels=50)
        guild = self.guild(decoy, [category])
        decoy.when(await guild.create_category_channel("voice-channels 2")).then_return(
            new_category,
        )
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category

    async def test_create_failure(self, decoy: Decoy) -> None:
        guild = self.guild(decoy, [])
        decoy.when(await guild.create_category_channel("voice-channels")).then_raise(
            DiscordException(),
        )
        client = mock_client(guilds=[guild])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is None

    async def test_missing_numbered_category(self, decoy: Decoy) -> None:
        new_category = self.category(decoy, "voice-channels 2")
        category1 = self.category(decoy, "voice-channels 1", channels=50)
        category3 = self.category(decoy, "voice-channels 3", channels=1)
        guild = self.guild(decoy, [category1, category3])
        decoy.when(await guild.create_category_channel("voice-channels 2")).then_return(
            new_category,
        )
        client = mock_client(guilds=[guild], categories=[category1, category3])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category

    async def test_available_has_bad_name(self, decoy: Decoy) -> None:
        new_category = self.category(decoy, "voice-channels")
        category = self.category(decoy, "voice-channels xyz", channels=1)
        guild = self.guild(decoy, [category])
        decoy.when(await guild.create_category_channel("voice-channels")).then_return(new_category)
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category

    async def test_no_guild(self) -> None:
        client = mock_client()
        result = await safe_ensure_voice_category(client, 404, "voice-channels")
        assert result is None


class TestSuggestVoiceChannel:
    def guild(self, decoy: Decoy, *channels: discord.VoiceChannel) -> discord.Guild:
        guild = decoy.mock(cls=discord.Guild)
        decoy.when(guild.voice_channels).then_return(list(channels))
        return guild

    def voice_channel(
        self,
        decoy: Decoy,
        members: list[discord.Member],
        *,
        category: str = "LFG Voice",
        xid: int = 6001,
    ) -> discord.VoiceChannel:
        found = decoy.mock(cls=discord.CategoryChannel)
        found.name = category
        channel = decoy.mock(cls=discord.VoiceChannel)
        channel.id = xid
        decoy.when(channel.category).then_return(found)
        decoy.when(channel.members).then_return(members)
        return channel

    def player(self, decoy: Decoy, xid: int) -> discord.Member:
        player = decoy.mock(cls=discord.Member)
        player.id = xid
        return player

    def test_when_empty(self, decoy: Decoy) -> None:
        channel = self.voice_channel(decoy, [])
        result = safe_suggest_voice_channel(
            guild=self.guild(decoy, channel),
            category="lfg voice",
            player_xids=[],
        )
        assert result == VoiceChannelSuggestion(None, channel.id)

    def test_when_picked(self, decoy: Decoy) -> None:
        player = self.player(decoy, 1)
        channel = self.voice_channel(decoy, [player])
        result = safe_suggest_voice_channel(
            guild=self.guild(decoy, channel),
            category="lfg voice",
            player_xids=[player.id],
        )
        assert result == VoiceChannelSuggestion(channel.id, None)

    def test_when_occupied(self, decoy: Decoy) -> None:
        channel = self.voice_channel(decoy, [self.player(decoy, 2)])
        result = safe_suggest_voice_channel(
            guild=self.guild(decoy, channel),
            category="lfg voice",
            player_xids=[1],
        )
        assert result == VoiceChannelSuggestion(None, None)

    def test_when_no_channels(self, decoy: Decoy) -> None:
        result = safe_suggest_voice_channel(
            guild=self.guild(decoy),
            category="lfg voice",
            player_xids=[],
        )
        assert result == VoiceChannelSuggestion(None, None)

    def test_when_guild_is_none(self) -> None:
        result = safe_suggest_voice_channel(guild=None, category="lfg voice", player_xids=[])
        assert result == VoiceChannelSuggestion(None, None)

    def test_when_channel_category_doesnt_match(self, decoy: Decoy) -> None:
        channel = self.voice_channel(decoy, [], category="other category")
        result = safe_suggest_voice_channel(
            guild=self.guild(decoy, channel),
            category="lfg voice",
            player_xids=[],
        )
        assert result == VoiceChannelSuggestion(None, None)
