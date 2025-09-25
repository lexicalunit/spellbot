from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import ANY, AsyncMock, MagicMock, Mock

import discord
import pytest
import pytest_asyncio
from aiohttp.client_exceptions import ClientOSError
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
    safe_message_reply,
    safe_original_response,
    safe_send_channel,
    safe_send_user,
    safe_suggest_voice_channel,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.utils import CANT_SEND_CODE
from tests.mixins import InteractionMixin
from tests.mocks import build_message, mock_client

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.asyncio
class TestOperationsRetry:
    @pytest_asyncio.fixture(autouse=True)
    def mock_sleep(self, mocker: MockerFixture) -> AsyncMock:
        return mocker.patch.object(operations, "sleep", AsyncMock())

    async def test_happy_path(self) -> None:
        async def func() -> int:
            return 1

        assert await retry(lambda: func()) == 1

    async def test_failure(self) -> None:
        async def func() -> int:
            raise ClientOSError

        with pytest.raises(ClientOSError):
            await retry(lambda: func())

    async def test_retries(self) -> None:
        tried_once = False

        async def func() -> int:
            nonlocal tried_once
            if not tried_once:
                tried_once = True
                raise ClientOSError
            return 1

        assert await retry(lambda: func()) == 1
        assert tried_once


@pytest.mark.asyncio
class TestOperationsDeferInteraction:
    async def test_happy_path(self) -> None:
        interaction = AsyncMock()
        await safe_defer_interaction(interaction)
        interaction.response.defer.assert_called_once_with()


@pytest.mark.asyncio
class TestOperationsOriginalResponse:
    async def test_happy_path(self) -> None:
        interaction = AsyncMock()
        original_response = MagicMock()
        interaction.original_response.return_value = original_response
        response = await safe_original_response(interaction)
        interaction.original_response.assert_called_once_with()
        assert response == original_response


@pytest.mark.asyncio
class TestOperationsFetchUser:
    async def test_cached(self, dpy_author: discord.User) -> None:
        client = mock_client(users=[dpy_author])
        assert await safe_fetch_user(client, dpy_author.id) is dpy_author

    async def test_uncached(
        self,
        dpy_author: discord.User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(users=[dpy_author])
        monkeypatch.setattr(client, "get_user", MagicMock(return_value=None))
        assert await safe_fetch_user(client, dpy_author.id) is dpy_author


@pytest.mark.asyncio
class TestOperationsFetchGuild:
    async def test_cached(self, dpy_guild: discord.Guild) -> None:
        client = mock_client(guilds=[dpy_guild])
        assert await safe_fetch_guild(client, dpy_guild.id) is dpy_guild

    async def test_uncached(
        self,
        dpy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(guilds=[dpy_guild])
        monkeypatch.setattr(client, "get_guild", MagicMock(return_value=None))
        assert await safe_fetch_guild(client, dpy_guild.id) is dpy_guild


@pytest.mark.asyncio
class TestOperationsFetchTextChannel:
    async def test_cached(self, dpy_channel: discord.TextChannel) -> None:
        client = mock_client(channels=[dpy_channel])
        assert await safe_fetch_text_channel(client, ANY, dpy_channel.id) is dpy_channel

    async def test_uncached(
        self,
        dpy_channel: discord.TextChannel,
        dpy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(channels=[dpy_channel], guilds=[dpy_guild])
        monkeypatch.setattr(client, "get_channel", MagicMock(return_value=None))
        assert await safe_fetch_text_channel(client, ANY, dpy_channel.id) is dpy_channel

    async def test_uncached_no_guild(
        self,
        dpy_channel: discord.TextChannel,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(channels=[dpy_channel])
        monkeypatch.setattr(client, "get_channel", MagicMock(return_value=None))
        assert await safe_fetch_text_channel(client, ANY, dpy_channel.id) is None

    async def test_non_text(self) -> None:
        channel = MagicMock(spec=discord.DMChannel)
        client = mock_client(channels=[channel])
        assert await safe_fetch_text_channel(client, ANY, channel.id) is None

    async def test_uncached_non_text(
        self,
        dpy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        channel = MagicMock(spec=discord.VoiceChannel)
        client = mock_client(channels=[channel], guilds=[dpy_guild])
        monkeypatch.setattr(client, "get_channel", MagicMock(return_value=None))
        assert await safe_fetch_text_channel(client, ANY, channel.id) is None

    async def test_uncached_with_no_read_permissions(
        self,
        dpy_channel: discord.TextChannel,
        dpy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(channels=[dpy_channel], guilds=[dpy_guild])
        monkeypatch.setattr(client, "get_channel", MagicMock(return_value=None))
        del dpy_guild.me.guild_permissions.read_messages
        assert await safe_fetch_text_channel(client, ANY, dpy_channel.id) is None

    async def test_uncached_with_no_permissions(
        self,
        dpy_channel: discord.TextChannel,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bad_guild = MagicMock(spec=discord.Guild)
        client = mock_client(channels=[dpy_channel], guilds=[bad_guild])
        monkeypatch.setattr(client, "get_channel", MagicMock(return_value=None))
        bad_guild.me = None
        assert await safe_fetch_text_channel(client, ANY, dpy_channel.id) is None


@pytest.mark.asyncio
class TestOperationsGetPartialMessage:
    read_perms = discord.Permissions(
        discord.Permissions.read_messages.flag | discord.Permissions.read_message_history.flag,
    )

    @pytest.fixture(autouse=True)
    def before_each(
        self,
        dpy_guild: discord.Guild,
        dpy_channel: discord.TextChannel,
        dpy_author: discord.User,
    ) -> None:
        self.guild = dpy_guild
        self.channel = dpy_channel
        self.author = dpy_author
        self.message = build_message(self.guild, self.channel, self.author)
        self.channel.get_partial_message = MagicMock(return_value=self.message)

    async def test_happy_path(self) -> None:
        self.channel.permissions_for = MagicMock(return_value=self.read_perms)
        found = safe_get_partial_message(self.channel, self.guild.id, self.message.id)
        assert found is self.message

    async def test_not_text(self) -> None:
        channel = MagicMock(spec=discord.VoiceChannel)
        channel.type = discord.ChannelType.voice
        channel.guild = self.guild
        channel.permissions_for = MagicMock(return_value=self.read_perms)
        assert not safe_get_partial_message(channel, self.guild.id, self.message.id)

    async def test_no_permissions(self) -> None:
        self.channel.permissions_for = MagicMock(return_value=discord.Permissions())
        assert not safe_get_partial_message(self.channel, self.guild.id, self.message.id)


@pytest.mark.asyncio
class TestOperationsUpdateEmbed:
    async def test_happy_path(self) -> None:
        message = MagicMock(spec=discord.Message)
        message.edit = AsyncMock()
        success = await safe_update_embed(message, "content", flags=1)
        message.edit.assert_called_once_with("content", flags=1)
        assert success

    async def test_exception(self) -> None:
        message = MagicMock(spec=discord.Message)
        message.edit = AsyncMock()
        message.edit.side_effect = DiscordException
        success = await safe_update_embed(message, "content", flags=1)
        message.edit.assert_called_once_with("content", flags=1)
        assert not success

    async def test_not_found(self) -> None:
        message = MagicMock(spec=discord.Message)
        message.edit = AsyncMock()
        message.edit.side_effect = discord.errors.NotFound(MagicMock(), "msg")
        message.guild = MagicMock(spec=discord.Guild)
        message.guild.id = 1
        success = await safe_update_embed(message, "content", flags=1)
        message.edit.assert_called_once_with("content", flags=1)
        assert not success


@pytest.mark.asyncio
@pytest.mark.use_db
class TestOperationsUpdateEmbedOrigin(InteractionMixin):
    async def test_happy_path(self) -> None:
        success = await safe_update_embed_origin(self.interaction, "content", flags=1)
        assert success
        self.interaction.edit_original_response.assert_called_once_with("content", flags=1)  # type: ignore

    async def test_exception(self) -> None:
        self.interaction.edit_original_response.side_effect = DiscordException  # type: ignore
        success = await safe_update_embed_origin(self.interaction, "content", flags=1)
        self.interaction.edit_original_response.assert_called_once_with("content", flags=1)  # type: ignore
        assert not success


@pytest.mark.asyncio
class TestOperationsCreateCategoryChannel:
    async def test_happy_path(self, dpy_guild: discord.Guild) -> None:
        client = mock_client(guilds=[dpy_guild])
        await safe_create_category_channel(client, dpy_guild.id, "name")
        dpy_guild.create_category_channel.assert_called_once_with("name")  # type: ignore

    async def test_no_permissions(self, dpy_guild: discord.Guild, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.operations.bot_can_manage_channels", MagicMock(return_value=False))
        client = mock_client(guilds=[dpy_guild])
        response = await safe_create_category_channel(client, dpy_guild.id, "name")
        dpy_guild.create_category_channel.assert_not_called()  # type: ignore
        assert response is None

    async def test_uncached(
        self,
        dpy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        client = mock_client(guilds=[dpy_guild])
        monkeypatch.setattr(client, "get_guild", MagicMock(return_value=None))
        await safe_create_category_channel(client, dpy_guild.id, "name")
        dpy_guild.create_category_channel.assert_called_once_with("name")  # type: ignore

    async def test_not_found(self, dpy_guild: discord.Guild) -> None:
        client = mock_client()
        await safe_create_category_channel(client, dpy_guild.id, "name")
        dpy_guild.create_category_channel.assert_not_called()  # type: ignore


@pytest.mark.asyncio
class TestOperationsCreateChannelInvite:
    async def test_happy_path(self, dpy_channel: discord.TextChannel) -> None:
        await safe_create_channel_invite(dpy_channel)
        dpy_channel.create_invite.assert_called_once()  # type: ignore

    async def test_exception(self, dpy_channel: discord.TextChannel) -> None:
        dpy_channel.create_invite.side_effect = DiscordException  # type: ignore
        invite = await safe_create_channel_invite(dpy_channel)
        assert invite is None


@pytest.mark.asyncio
class TestOperationsCreateVoiceChannel:
    async def test_happy_path(self, dpy_guild: discord.Guild) -> None:
        category = MagicMock(spec=discord.CategoryChannel)
        client = mock_client(guilds=[dpy_guild])
        await safe_create_voice_channel(client, dpy_guild.id, "name", category=category)
        dpy_guild.create_voice_channel.assert_called_once_with(  # type: ignore
            "name",
            category=category,
            bitrate=ANY,
        )

    async def test_uncached(
        self,
        dpy_guild: discord.Guild,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        category = MagicMock(spec=discord.CategoryChannel)
        client = mock_client(guilds=[dpy_guild])
        monkeypatch.setattr(client, "get_guild", MagicMock(return_value=None))
        await safe_create_voice_channel(
            client,
            dpy_guild.id,
            "name",
            category=category,
            use_max_bitrate=True,
        )
        dpy_guild.create_voice_channel.assert_called_once_with(  # type: ignore
            "name",
            category=category,
            bitrate=int(dpy_guild.bitrate_limit),
        )

    async def test_not_found(self, dpy_guild: discord.Guild) -> None:
        category = MagicMock(spec=discord.CategoryChannel)
        client = mock_client()
        await safe_create_voice_channel(
            client,
            dpy_guild.id,
            "name",
            category=category,
            use_max_bitrate=False,
        )
        dpy_guild.create_voice_channel.assert_not_called()  # type: ignore


@pytest.mark.asyncio
class TestOperationsSendChannel:
    async def test_happy_path(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild

        interaction = AsyncMock()
        interaction.channel = channel
        interaction.channel_id = channel.id
        interaction.guild = guild
        interaction.guild_id = guild.id

        await safe_send_channel(interaction, "content")

        interaction.response.send_message.assert_called_once_with("content")
        interaction.original_response.assert_called_once_with()


@pytest.mark.asyncio
class TestOperationsFollowupChannel:
    async def test_happy_path(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild

        interaction = AsyncMock()
        interaction.channel = channel
        interaction.channel_id = channel.id
        interaction.guild = guild
        interaction.guild_id = guild.id

        await safe_followup_channel(interaction, "content")

        interaction.followup.send.assert_called_once_with("content")
        interaction.original_response.assert_called_once_with()

    async def test_remove_view(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild

        interaction = AsyncMock()
        interaction.channel = channel
        interaction.channel_id = channel.id
        interaction.guild = guild
        interaction.guild_id = guild.id

        await safe_followup_channel(interaction, "content", view=None)

        interaction.followup.send.assert_called_once_with("content", view=MISSING)
        interaction.original_response.assert_called_once_with()


@pytest.mark.asyncio
class TestOperationsDeleteChannel:
    delete_perms = discord.Permissions(discord.Permissions.manage_channels.flag)

    async def test_happy_path(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.delete = AsyncMock()
        channel.permissions_for = MagicMock(return_value=self.delete_perms)

        assert await safe_delete_channel(channel, guild.id)
        channel.delete.assert_called_once_with()

    async def test_not_found(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.delete = AsyncMock(side_effect=discord.errors.NotFound(MagicMock(), "msg"))
        channel.permissions_for = MagicMock(return_value=self.delete_perms)

        assert not await safe_delete_channel(channel, guild.id)
        channel.delete.assert_called_once_with()

    async def test_missing_channel_id(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        del channel.id
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.delete = AsyncMock()
        channel.permissions_for = MagicMock(return_value=self.delete_perms)

        assert not await safe_delete_channel(channel, guild.id)
        channel.delete.assert_not_called()

    async def test_missing_channel_delete(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        del channel.delete
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=self.delete_perms)

        assert not await safe_delete_channel(channel, guild.id)

    async def test_missing_permissions(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        del channel.id
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.delete = AsyncMock()
        channel.permissions_for = MagicMock(return_value=discord.Permissions())

        assert not await safe_delete_channel(channel, guild.id)
        channel.delete.assert_not_called()


@pytest.mark.asyncio
class TestOperationsChannelReply:
    async def test_happy_path(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()
        embed = discord.Embed()
        await safe_channel_reply(channel, "content", embed=embed)
        channel.send.assert_called_once_with("content", embed=embed)

    async def test_can_not_send(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.operations.bot_can_send_messages", MagicMock(return_value=False))
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()
        embed = discord.Embed()
        assert not await safe_channel_reply(channel, "content", embed=embed)


@pytest.mark.asyncio
class TestOperationsSendUser:
    @pytest_asyncio.fixture  # type: ignore
    def bad_users(self) -> set[int]:
        return set()

    @pytest_asyncio.fixture(autouse=True)
    def mark_bad_user(self, mocker: MockerFixture, bad_users: set[int]) -> AsyncMock:
        async def mark_bad_user(user_xid: int) -> None:
            bad_users.add(user_xid)

        return mocker.patch.object(operations, "mark_bad_user", mark_bad_user)

    @pytest_asyncio.fixture(autouse=True)
    def is_bad_user(self, mocker: MockerFixture, bad_users: set[int]) -> AsyncMock:
        async def is_bad_user(user_xid: int) -> bool:
            return user_xid in bad_users

        return mocker.patch.object(operations, "is_bad_user", is_bad_user)

    async def test_happy_path(self) -> None:
        user = MagicMock(spec=discord.User | discord.Member)
        user.send = AsyncMock()
        embed = discord.Embed()
        await safe_send_user(user, "content", embed=embed)
        user.send.assert_called_once_with("content", embed=embed)

    async def test_not_sendable(self, caplog: pytest.LogCaptureFixture) -> None:
        user = Mock()
        del user.send
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.id = 1234
        await safe_send_user(user, "content")
        assert "no send method on user user#1234 1234" in caplog.text

    @pytest.mark.parametrize("user_xid", [1234, None])
    async def test_forbidden(
        self,
        caplog: pytest.LogCaptureFixture,
        user_xid: int | None,
    ) -> None:
        caplog.set_level(logging.INFO)
        user = MagicMock(spec=discord.User | discord.Member)
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.id = user_xid
        user.send = AsyncMock(side_effect=discord.errors.Forbidden(MagicMock(), "msg"))
        await safe_send_user(user, "content")
        assert "not allowed to send message to" in caplog.text

    async def test_cant_send(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO)
        exception = discord.errors.HTTPException(MagicMock(), "msg")
        exception.code = CANT_SEND_CODE
        user = MagicMock(spec=discord.User | discord.Member)
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.id = 1234
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "not allowed to send message to user#1234 1234" in caplog.text

        # user should now be on the "bad users" list
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "not sending to bad user user#1234" in caplog.text

    async def test_http_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        exception = discord.errors.HTTPException(MagicMock(), "msg")
        user = MagicMock(spec=discord.User | discord.Member)
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.id = 1234
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "failed to send message to user user#1234 1234" in caplog.text

    async def test_server_error(self, caplog: pytest.LogCaptureFixture) -> None:
        exception = discord.errors.DiscordServerError(MagicMock(), "msg")
        user = MagicMock(spec=discord.User | discord.Member)
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.id = 1234
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "discord server error sending to user user#1234 1234" in caplog.text

    async def test_client_error(self, caplog: pytest.LogCaptureFixture) -> None:
        exception = ClientOSError()
        user = MagicMock(spec=discord.User | discord.Member)
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.id = 1234
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "client error sending to user user#1234 1234" in caplog.text


@pytest.mark.asyncio
class TestOperationsAddRole:
    role_perms = discord.Permissions(discord.Permissions.manage_roles.flag)

    async def test_happy_path(self) -> None:
        member = MagicMock(spec=discord.User | discord.Member)
        member.id = 101
        member.roles = []
        member.add_roles = AsyncMock()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        role = discord.Role(
            guild=guild,
            state=MagicMock(),
            data={"id": 2, "name": "role"},  # type: ignore
        )
        guild.me.top_role = role
        guild.roles = [role]
        await safe_add_role(member, guild, "role")
        member.add_roles.assert_called_once_with(role)

    async def test_add_everyone_role(self) -> None:
        member = MagicMock(spec=discord.User | discord.Member)
        member.id = 101
        member.roles = []
        member.add_roles = AsyncMock()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        role = discord.Role(
            guild=guild,
            state=MagicMock(),
            data={"id": 1, "name": "@everyone"},  # type: ignore
        )
        guild.roles = [role]
        await safe_add_role(member, guild, "@everyone")
        member.add_roles.assert_not_called()

    async def test_remove(self) -> None:
        member = MagicMock(spec=discord.User | discord.Member)
        member.id = 101
        member.roles = []
        member.remove_roles = AsyncMock()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        role = discord.Role(
            guild=guild,
            state=MagicMock(),
            data={"id": 2, "name": "role"},  # type: ignore
        )
        guild.me.top_role = role
        guild.roles = [role]
        await safe_add_role(member, guild, "role", remove=True)
        member.remove_roles.assert_called_once_with(role)

    async def test_no_roles_attribute(self) -> None:
        user = MagicMock(spec=discord.User | discord.Member)
        user.id = 101
        member = MagicMock(spec=discord.User | discord.Member)
        member.id = user.id
        member.roles = []
        member.add_roles = AsyncMock()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        role = discord.Role(
            guild=guild,
            state=MagicMock(),
            data={"id": 2, "name": "role"},  # type: ignore
        )
        guild.me.top_role = role
        guild.get_member = MagicMock(return_value=member)
        guild.roles = [role]
        await safe_add_role(member, guild, "role")
        member.add_roles.assert_called_once_with(role)

    async def test_no_member(self, caplog: pytest.LogCaptureFixture) -> None:
        user = MagicMock(spec=discord.User | discord.Member)
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.id = 101
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        guild.get_member = MagicMock(return_value=None)
        await safe_add_role(user, guild, "role")
        guild.get_member.assert_called_once()
        assert (
            f"warning: in guild {guild.name} ({guild.id}), could not manage role role:"
            " could not find member: user#1234"
        ) in caplog.text

    async def test_no_role(self, caplog: pytest.LogCaptureFixture) -> None:
        member = MagicMock(spec=discord.User | discord.Member)
        member.id = 101
        member.roles = []
        member.add_roles = AsyncMock()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        guild.roles = []
        await safe_add_role(member, guild, "role")
        assert (
            f"warning: in guild {guild.name} ({guild.id}), could not manage role:"
            " could not find role: role"
        ) in caplog.text

    async def test_no_permissions(self, caplog: pytest.LogCaptureFixture) -> None:
        member = MagicMock(spec=discord.User | discord.Member)
        member.id = 101
        member.roles = []
        member.add_roles = AsyncMock()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = discord.Permissions()
        role = discord.Role(
            guild=guild,
            state=MagicMock(),
            data={"id": 2, "name": "role"},  # type: ignore
        )
        guild.roles = [role]
        await safe_add_role(member, guild, "role")
        assert (
            f"warning: in guild {guild.name} ({guild.id}), could not manage role:"
            " no permissions to manage role: role"
        ) in caplog.text

    async def test_bad_role_hierarchy(self, caplog: pytest.LogCaptureFixture) -> None:
        member = MagicMock(spec=discord.User | discord.Member)
        member.id = 101
        member.roles = []
        member.add_roles = AsyncMock()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        admin_role = discord.Role(
            guild=guild,
            state=MagicMock(),
            data={"id": 3, "name": "admin_role"},  # type: ignore
        )
        user_role = discord.Role(
            guild=guild,
            state=MagicMock(),
            data={"id": 4, "name": "user_role"},  # type: ignore
        )
        guild.me.top_role = user_role
        guild.roles = [user_role, admin_role]
        await safe_add_role(member, guild, "admin_role")
        assert (
            f"warning: in guild {guild.name} ({guild.id}), could not manage role:"
            " no permissions to manage role: admin_role"
        ) in caplog.text

    async def test_forbidden(self, caplog: pytest.LogCaptureFixture) -> None:
        member = MagicMock(spec=discord.User | discord.Member)
        member.id = 101
        member.roles = []
        member.__str__ = lambda self: "user#1234"  # type: ignore
        exception = discord.errors.Forbidden(MagicMock(), "msg")
        member.add_roles = AsyncMock(side_effect=exception)
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        role = discord.Role(
            guild=guild,
            state=MagicMock(),
            data={"id": 2, "name": "role"},  # type: ignore
        )
        guild.me.top_role = role
        guild.roles = [role]
        await safe_add_role(member, guild, "role")
        assert (
            f"warning: in guild {guild.name} ({guild.id}), could not add role to member user#1234"
        ) in caplog.text


@pytest.mark.asyncio
class TestOperationsMessageReply:
    async def test_happy_path(self) -> None:
        send_permisions = discord.Permissions(discord.Permissions.send_messages.flag)
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=send_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        message.reply = AsyncMock()
        embed = MagicMock(spec=discord.Embed)

        await safe_message_reply(message, "content", embed=embed)
        message.reply.assert_called_once_with("content", embed=embed)

    async def test_bad_permissions(self) -> None:
        bad_permisions = discord.Permissions()
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        message.reply = AsyncMock()
        embed = MagicMock(spec=discord.Embed)

        await safe_message_reply(message, "content", embed=embed)
        message.reply.assert_not_called()

    async def test_reply_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG)
        send_permisions = discord.Permissions(discord.Permissions.send_messages.flag)
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=send_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        error = RuntimeError("something-failed")
        message.reply = AsyncMock(side_effect=error)
        embed = MagicMock(spec=discord.Embed)

        await safe_message_reply(message, "content", embed=embed)
        message.reply.assert_called_once_with("content", embed=embed)
        assert "something-failed" in caplog.text


@pytest.mark.asyncio
class TestOperationsDeleteMessage:
    async def test_happy_path(self) -> None:
        permissions = discord.Permissions(discord.Permissions.manage_messages.flag)
        message = MagicMock(spec=discord.Message)
        message.guild = MagicMock(spec=discord.Guild)
        message.guild.id = 101
        message.guild.me = MagicMock()
        message.guild.me.guild_permissions = permissions
        message = MagicMock(spec=discord.Message)
        message.delete = AsyncMock()
        assert await safe_delete_message(message)
        message.delete.assert_called_once_with()

    async def test_bad_permissions(self) -> None:
        permissions = discord.Permissions(discord.Permissions.read_messages.flag)
        message = MagicMock(spec=discord.Message)
        message.guild = MagicMock(spec=discord.Guild)
        message.guild.id = 101
        message.guild.me = MagicMock()
        message.guild.me.guild_permissions = permissions
        message.delete = AsyncMock()
        assert not await safe_delete_message(message)
        message.delete.assert_not_called()


@pytest.mark.asyncio
class TestEnsureVoiceCategory:
    async def test_available_exists(self) -> None:
        channel = MagicMock(spec=discord.VoiceChannel)
        category = MagicMock(spec=discord.CategoryChannel)
        category.name = "voice-channels"
        category.channels = [channel]
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = [category]
        guild.create_category_channel = AsyncMock()
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is category
        guild.create_category_channel.assert_not_called()

    async def test_none_exists(self) -> None:
        new_category = MagicMock(spec=discord.CategoryChannel)
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = []
        guild.create_category_channel = AsyncMock(return_value=new_category)
        client = mock_client(guilds=[guild])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category
        guild.create_category_channel.assert_called_once_with("voice-channels")

    async def test_none_available(self) -> None:
        new_category = MagicMock(spec=discord.CategoryChannel)
        channel = MagicMock(spec=discord.VoiceChannel)
        category = MagicMock(spec=discord.CategoryChannel)
        category.name = "voice-channels"
        category.channels = [channel] * 50
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = [category]
        guild.create_category_channel = AsyncMock(return_value=new_category)
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category
        guild.create_category_channel.assert_called_once_with("voice-channels 2")

    async def test_create_failure(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = []
        guild.create_category_channel = AsyncMock(side_effect=DiscordException())
        client = mock_client(guilds=[guild])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is None
        guild.create_category_channel.assert_called_once_with("voice-channels")

    async def test_missing_numbered_category(self) -> None:
        new_category = MagicMock(spec=discord.CategoryChannel)
        new_category.name = "voice-channels 2"
        channel1 = MagicMock(spec=discord.VoiceChannel)
        category1 = MagicMock(spec=discord.CategoryChannel)
        category1.name = "voice-channels 1"
        category1.channels = [channel1] * 50
        channel3 = MagicMock(spec=discord.VoiceChannel)
        category3 = MagicMock(spec=discord.CategoryChannel)
        category3.name = "voice-channels 3"
        category3.channels = [channel3]
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = [category1, category3]
        guild.create_category_channel = AsyncMock(return_value=new_category)
        client = mock_client(guilds=[guild], categories=[category1, category3])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category
        guild.create_category_channel.assert_called_once_with("voice-channels 2")

    async def test_available_has_bad_name(self) -> None:
        new_category = MagicMock(spec=discord.CategoryChannel)
        new_category.name = "voice-channels"
        channel = MagicMock(spec=discord.VoiceChannel)
        category = MagicMock(spec=discord.CategoryChannel)
        category.name = "voice-channels xyz"
        category.channels = [channel]
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = [category]
        guild.create_category_channel = AsyncMock(return_value=new_category)
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category
        guild.create_category_channel.assert_called_once_with("voice-channels")

    async def test_no_guild(self) -> None:
        client = mock_client()
        result = await safe_ensure_voice_category(client, 404, "voice-channels")
        assert result is None


def test_safe_suggest_voice_channel_when_empty() -> None:
    guild = MagicMock(spec=discord.Guild)
    category = MagicMock(spec=discord.CategoryChannel, guild=guild)
    channel = MagicMock(spec=discord.VoiceChannel, guild=guild, category=category)
    guild.categories = [category]
    guild.voice_channels = [channel]
    result = safe_suggest_voice_channel(guild=guild, category="lfg voice", player_xids=[])
    assert result == VoiceChannelSuggestion(None, channel.id)


def test_safe_suggest_voice_channel_when_picked() -> None:
    guild = MagicMock(spec=discord.Guild)
    category = MagicMock(spec=discord.CategoryChannel, guild=guild)
    player = MagicMock(spec=discord.Member)
    channel = MagicMock(spec=discord.VoiceChannel, guild=guild, category=category, members=[player])
    guild.categories = [category]
    guild.voice_channels = [channel]
    result = safe_suggest_voice_channel(guild=guild, category="lfg voice", player_xids=[player.id])
    assert result == VoiceChannelSuggestion(channel.id, None)


def test_safe_suggest_voice_channel_when_occupied() -> None:
    guild = MagicMock(spec=discord.Guild)
    category = MagicMock(spec=discord.CategoryChannel, guild=guild)
    player = MagicMock(spec=discord.Member, id=1)
    other = MagicMock(spec=discord.Member, id=2)
    channel = MagicMock(spec=discord.VoiceChannel, guild=guild, category=category, members=[other])
    guild.categories = [category]
    guild.voice_channels = [channel]
    result = safe_suggest_voice_channel(guild=guild, category="lfg voice", player_xids=[player.id])
    assert result == VoiceChannelSuggestion(None, None)


def test_safe_suggest_voice_channel_when_no_channels() -> None:
    guild = MagicMock(spec=discord.Guild)
    category = MagicMock(spec=discord.CategoryChannel, guild=guild)
    guild.categories = [category]
    guild.voice_channels = []
    result = safe_suggest_voice_channel(guild=guild, category="lfg voice", player_xids=[])
    assert result == VoiceChannelSuggestion(None, None)
