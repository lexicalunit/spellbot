# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import discord
import pytest
from decoy import matchers
from discord import app_commands
from discord.ext import commands
from discord.state import ConnectionState

from spellbot import utils
from spellbot.errors import AdminOnlyError, GuildOnlyError, ModOnlyError
from spellbot.utils import (
    bot_can_delete_channel,
    bot_can_delete_message,
    bot_can_manage_channels,
    bot_can_read,
    bot_can_role,
    bot_can_send_messages,
    is_admin,
    is_guild,
    is_mod,
    is_moderator,
    log_warning,
    safe_permissions_for,
    traced_interaction,
    user_can_moderate,
)
from spellbot.web import signing
from spellbot.web.signing import generate_signed_url, validate_signature
from tests.mocks.decoys import ANY, bot_with, guild_with, partial_object, text_channel

if TYPE_CHECKING:
    from decoy import Decoy
    from discord.types.role import Role as RolePayload

    from spellbot.settings import Settings
    from tests.fixtures import Stub

TEXT = discord.ChannelType.text
PRIVATE = discord.ChannelType.private


def member(
    decoy: Decoy,
    xid: int = 1,
    *,
    roles: list[discord.Role] | None = None,
    guild_permissions: discord.Permissions | None = None,
    top_role: discord.Role | None = None,
) -> discord.Member:
    user = decoy.mock(cls=discord.Member)
    decoy.when(user.id).then_return(xid)
    decoy.when(user.roles).then_return(roles or [])
    decoy.when(user.guild_permissions).then_return(guild_permissions or discord.Permissions())
    if top_role is not None:
        decoy.when(user.top_role).then_return(top_role)
    return user


def role(
    decoy: Decoy,
    name: str,
    *,
    guild: discord.Guild | None = None,
    position: int = 1,
) -> discord.Role:
    data: RolePayload = {
        "id": 5000 + position,
        "name": name,
        "color": 0,
        "colors": {"primary_color": 0, "secondary_color": None, "tertiary_color": None},
        "hoist": False,
        "position": position,
        "permissions": "0",
        "managed": False,
        "mentionable": False,
        "flags": 0,
    }
    state = decoy.mock(cls=ConnectionState)
    return discord.Role(guild=guild or guild_with(decoy), state=state, data=data)


def interaction(
    decoy: Decoy,
    user: discord.Member,
    guild: discord.Guild | None = None,
    channel: discord.TextChannel | None = None,
) -> discord.Interaction:
    found = decoy.mock(cls=discord.Interaction)
    found.user = user
    found.channel = channel
    decoy.when(found.guild).then_return(guild)
    return found


class TestUtilsLogging:
    def test_log_warning_with_kwargs(self, caplog: pytest.LogCaptureFixture) -> None:
        log_warning("log-line %(foo)s", foo="foo")
        assert "log-line foo" in caplog.text
        assert "warning:" in caplog.text

    def test_log_warning_without_kwargs(self, caplog: pytest.LogCaptureFixture) -> None:
        log_warning("simple log message")
        assert "simple log message" in caplog.text
        assert "warning:" in caplog.text


@pytest.mark.asyncio
class TestUtilsPermissionsFor:
    async def test_happy_path(self, decoy: Decoy) -> None:
        permissions = discord.Permissions(discord.Permissions.send_messages.flag)
        channel = text_channel(decoy, permissions=permissions)
        assert safe_permissions_for(channel, member(decoy)) == permissions

    async def test_exception(self, decoy: Decoy) -> None:
        channel = decoy.mock(cls=discord.TextChannel)
        decoy.when(channel.permissions_for(matchers.Anything())).then_raise(RuntimeError("oh no"))
        assert safe_permissions_for(channel, member(decoy)) is None


class TestUtilsBotCanRole:
    def test_happy_path(self, decoy: Decoy) -> None:
        guild = guild_with(decoy, bot_with(decoy, discord.Permissions.manage_roles.flag))
        assert bot_can_role(guild)

    def test_when_no_me(self, decoy: Decoy) -> None:
        assert not bot_can_role(guild_with(decoy, None))

    def test_when_no_permissions(self, decoy: Decoy) -> None:
        assert not bot_can_role(guild_with(decoy, bot_with(decoy)))

    def test_when_role_greater_than_my_top_role(self, decoy: Decoy) -> None:
        guild = guild_with(decoy)
        my_top_role = role(decoy, "bot", guild=guild, position=1)
        me = member(
            decoy,
            guild_permissions=discord.Permissions(discord.Permissions.manage_roles.flag),
            top_role=my_top_role,
        )
        decoy.when(guild.me).then_return(me)
        assert not bot_can_role(guild, role(decoy, "higher", guild=guild, position=10))
        assert bot_can_role(guild, role(decoy, "lower", guild=guild, position=0))


class TestUtilsBotCanManageChannels:
    def test_happy_path(self, decoy: Decoy) -> None:
        guild = guild_with(decoy, bot_with(decoy, discord.Permissions.manage_channels.flag))
        assert bot_can_manage_channels(guild)

    def test_missing_me(self, decoy: Decoy) -> None:
        assert not bot_can_manage_channels(guild_with(decoy, None))

    def test_bad_permissions(self, decoy: Decoy) -> None:
        guild = guild_with(decoy, bot_with(decoy, discord.Permissions.read_messages.flag))
        assert not bot_can_manage_channels(guild)


class TestUtilsBotCanDeleteMessage:
    def test_happy_path(self, decoy: Decoy) -> None:
        message = decoy.mock(cls=discord.Message)
        message.guild = guild_with(decoy, bot_with(decoy, discord.Permissions.manage_messages.flag))
        assert bot_can_delete_message(message)

    def test_missing_guild(self) -> None:
        assert not bot_can_delete_message(partial_object())

    def test_missing_me(self, decoy: Decoy) -> None:
        message = decoy.mock(cls=discord.Message)
        message.guild = guild_with(decoy, None)
        assert not bot_can_delete_message(message)

    def test_bad_permissions(self, decoy: Decoy) -> None:
        message = decoy.mock(cls=discord.Message)
        message.guild = guild_with(decoy, bot_with(decoy, discord.Permissions.read_messages.flag))
        assert not bot_can_delete_message(message)


class TestUtilsBotCanSendMessages:
    def test_happy_path(self, decoy: Decoy) -> None:
        can_send = discord.Permissions(discord.Permissions.send_messages.flag)
        channel = text_channel(decoy, guild_with(decoy, bot_with(decoy)), can_send)
        assert bot_can_send_messages(channel)

    def test_missing_type(self, decoy: Decoy) -> None:
        assert not bot_can_send_messages(partial_object(guild=guild_with(decoy, bot_with(decoy))))

    def test_private_channel_type(self, decoy: Decoy) -> None:
        assert not bot_can_send_messages(text_channel(decoy, channel_type=PRIVATE))

    def test_no_guild(self) -> None:
        assert not bot_can_send_messages(partial_object(type=TEXT))

    def test_no_permissions(self, decoy: Decoy, stub: Stub) -> None:
        safe_permissions_for_fake = stub(utils, "safe_permissions_for")
        decoy.when(safe_permissions_for_fake(ANY), ignore_extra_args=True).then_return(None)
        channel = text_channel(decoy, guild_with(decoy, bot_with(decoy)))
        assert not bot_can_send_messages(channel)

    def test_bad_permissions(self, decoy: Decoy) -> None:
        channel = text_channel(decoy, guild_with(decoy, bot_with(decoy)), discord.Permissions())
        assert not bot_can_send_messages(channel)


READ = discord.Permissions(
    discord.Permissions.read_messages.flag | discord.Permissions.read_message_history.flag,
)
MANAGE_CHANNELS = discord.Permissions(discord.Permissions.manage_channels.flag)


class TestUtilsBotCanRead:
    def test_happy_path(self, decoy: Decoy) -> None:
        assert bot_can_read(text_channel(decoy, guild_with(decoy, bot_with(decoy)), READ))

    def test_missing_channel_type(self, decoy: Decoy) -> None:
        assert not bot_can_read(partial_object(guild=guild_with(decoy, bot_with(decoy))))

    def test_private_channel_type(self, decoy: Decoy) -> None:
        assert bot_can_read(text_channel(decoy, channel_type=PRIVATE))

    def test_missing_guild(self) -> None:
        assert bot_can_read(partial_object(type=TEXT))

    def test_bad_permissions(self, decoy: Decoy) -> None:
        channel = text_channel(decoy, guild_with(decoy, bot_with(decoy)), discord.Permissions())
        assert not bot_can_read(channel)


class TestUtilsBotCanDeleteChannel:
    def test_happy_path(self, decoy: Decoy) -> None:
        channel = text_channel(decoy, guild_with(decoy, bot_with(decoy)), MANAGE_CHANNELS)
        assert bot_can_delete_channel(channel)

    def test_missing_channel_type(self, decoy: Decoy) -> None:
        assert not bot_can_delete_channel(partial_object(guild=guild_with(decoy, bot_with(decoy))))

    def test_private_channel_type(self, decoy: Decoy) -> None:
        assert not bot_can_delete_channel(text_channel(decoy, channel_type=PRIVATE))

    def test_missing_guild(self) -> None:
        assert not bot_can_delete_channel(partial_object(type=TEXT))

    def test_bad_permissions(self, decoy: Decoy) -> None:
        channel = text_channel(decoy, guild_with(decoy, bot_with(decoy)), discord.Permissions())
        assert not bot_can_delete_channel(channel)

    def test_none_permissions(self, decoy: Decoy) -> None:
        # `permissions_for` is left unstubbed, so it answers `None`.
        assert not bot_can_delete_channel(text_channel(decoy, guild_with(decoy, bot_with(decoy))))


ADMIN = discord.Permissions(discord.Permissions.administrator.flag)


class TestUtilsIsAdmin:
    def test_happy_path(self, decoy: Decoy, settings: Settings) -> None:
        guild = guild_with(decoy)
        user = member(decoy, 1, roles=[role(decoy, settings.ADMIN_ROLE)])
        assert is_admin(interaction(decoy, user, guild, text_channel(decoy, guild, ADMIN)))

    def test_missing_guild(self, decoy: Decoy) -> None:
        with pytest.raises(AdminOnlyError):
            is_admin(interaction(decoy, member(decoy), None, text_channel(decoy)))

    def test_missing_channel(self, decoy: Decoy) -> None:
        with pytest.raises(AdminOnlyError):
            is_admin(interaction(decoy, member(decoy), guild_with(decoy), None))

    def test_when_user_is_owner(self, decoy: Decoy) -> None:
        guild = guild_with(decoy, owner_id=1)
        assert is_admin(interaction(decoy, member(decoy, 1), guild, text_channel(decoy, guild)))

    def test_when_user_has_admin_role(self, decoy: Decoy, settings: Settings) -> None:
        guild = guild_with(decoy)
        channel = text_channel(decoy, guild, discord.Permissions())
        user = member(decoy, 1, roles=[role(decoy, settings.ADMIN_ROLE)])
        assert is_admin(interaction(decoy, user, guild, channel))

    def test_when_user_does_not_have_admin_role(self, decoy: Decoy, settings: Settings) -> None:
        guild = guild_with(decoy)
        channel = text_channel(decoy, guild, discord.Permissions())
        user = member(decoy, 1, roles=[role(decoy, f"not-{settings.ADMIN_ROLE}")])
        with pytest.raises(AdminOnlyError):
            is_admin(interaction(decoy, user, guild, channel))

    def test_user_has_no_roles(self, decoy: Decoy) -> None:
        guild = guild_with(decoy)
        channel = text_channel(decoy, guild, discord.Permissions())
        found = interaction(decoy, member(decoy), guild, channel)
        found.user = partial_object(id=1)  # a user, rather than a member, has no roles
        with pytest.raises(AdminOnlyError):
            is_admin(found)

    def test_when_user_is_bot_owner(self, decoy: Decoy, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(utils.settings, "OWNER_XID", 12345)
        # No guild or channel needed - owner bypasses all checks
        assert is_admin(interaction(decoy, member(decoy, 12345)))


class TestUtilsIsMod:
    def test_happy_path(self, decoy: Decoy, stub: Stub) -> None:
        fake = stub(utils, "user_can_moderate")
        guild = guild_with(decoy)
        channel = text_channel(decoy, guild)
        user = member(decoy)
        decoy.when(fake(user, guild, channel)).then_return(True)
        assert is_mod(interaction(decoy, user, guild, channel))

    def test_raises_when_user_cannot_moderate(self, decoy: Decoy, stub: Stub) -> None:
        fake = stub(utils, "user_can_moderate")
        decoy.when(fake(ANY, ANY, ANY)).then_return(False)
        guild = guild_with(decoy)
        with pytest.raises(ModOnlyError):
            is_mod(interaction(decoy, member(decoy), guild, text_channel(decoy, guild)))

    def test_when_user_is_bot_owner(self, decoy: Decoy, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(utils.settings, "OWNER_XID", 12345)
        # No guild or channel needed - owner bypasses all checks
        assert is_mod(interaction(decoy, member(decoy, 12345)))


class TestUtilsIsGuild:
    def test_happy_path(self, decoy: Decoy) -> None:
        assert is_guild(interaction(decoy, member(decoy), guild_with(decoy)))

    def test_missing_guild(self, decoy: Decoy) -> None:
        with pytest.raises(GuildOnlyError):
            is_guild(interaction(decoy, member(decoy), None))


class TestUtilsIsModerator:
    def test_guild_owner(self) -> None:
        assert is_moderator(
            is_guild_owner=True,
            has_admin=False,
            has_ban_members=False,
            role_names=[],
        )

    def test_administrator(self) -> None:
        assert is_moderator(
            is_guild_owner=False,
            has_admin=True,
            has_ban_members=False,
            role_names=[],
        )

    def test_ban_members(self) -> None:
        assert is_moderator(
            is_guild_owner=False,
            has_admin=False,
            has_ban_members=True,
            role_names=[],
        )

    def test_mod_prefix_role(self, settings: Settings) -> None:
        assert is_moderator(
            is_guild_owner=False,
            has_admin=False,
            has_ban_members=False,
            role_names=[f"{settings.MOD_PREFIX} Team"],
        )

    def test_admin_role(self, settings: Settings) -> None:
        assert is_moderator(
            is_guild_owner=False,
            has_admin=False,
            has_ban_members=False,
            role_names=[settings.ADMIN_ROLE],
        )

    def test_plain_member(self) -> None:
        assert not is_moderator(
            is_guild_owner=False,
            has_admin=False,
            has_ban_members=False,
            role_names=["Members", "Verified"],
        )


class TestUtilsUserCanModerate:
    def test_owner_happy_path(self, decoy: Decoy) -> None:
        guild = guild_with(decoy, owner_id=1)
        channel = text_channel(decoy, guild, discord.Permissions())
        assert user_can_moderate(member(decoy, 1), guild, channel)

    def test_bot_owner_bypasses_all_checks(
        self,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(utils.settings, "OWNER_XID", 99)
        guild = guild_with(decoy)
        assert user_can_moderate(member(decoy, 99), guild, text_channel(decoy, guild))

    def test_admin_happy_path(self, decoy: Decoy) -> None:
        guild = guild_with(decoy)
        assert user_can_moderate(member(decoy, 1), guild, text_channel(decoy, guild, ADMIN))

    def test_ban_members_happy_path(self, decoy: Decoy) -> None:
        guild = guild_with(decoy)
        ban = discord.Permissions(discord.Permissions.ban_members.flag)
        assert user_can_moderate(member(decoy, 1), guild, text_channel(decoy, guild, ban))

    def test_user_without_id(self, decoy: Decoy) -> None:
        guild = guild_with(decoy, owner_id=1)
        channel = text_channel(decoy, guild, discord.Permissions())
        assert not user_can_moderate(partial_object(), guild, channel)

    def test_non_admin_happy_path(self, decoy: Decoy, settings: Settings) -> None:
        guild = guild_with(decoy)
        channel = text_channel(decoy, guild, discord.Permissions())
        user = member(decoy, 1, roles=[role(decoy, f"{settings.MOD_PREFIX}-whatever")])
        assert user_can_moderate(user, guild, channel)

    def test_missing_channel(self, decoy: Decoy, settings: Settings) -> None:
        user = member(decoy, 1, roles=[role(decoy, f"{settings.MOD_PREFIX}-whatever")])
        assert not user_can_moderate(user, guild_with(decoy), None)

    def test_missing_guild(self, decoy: Decoy, settings: Settings) -> None:
        user = member(decoy, 1, roles=[role(decoy, f"{settings.MOD_PREFIX}-whatever")])
        channel = text_channel(decoy, permissions=discord.Permissions())
        assert not user_can_moderate(user, None, channel)

    def test_missing_user_roles(self, decoy: Decoy) -> None:
        guild = guild_with(decoy)
        channel = text_channel(decoy, guild, discord.Permissions())
        # A user, rather than a member, has no roles
        assert not user_can_moderate(partial_object(id=1), guild, channel)

    def test_when_user_does_not_have_mod_role(self, decoy: Decoy, settings: Settings) -> None:
        guild = guild_with(decoy)
        channel = text_channel(decoy, guild, discord.Permissions())
        user = member(decoy, 1, roles=[role(decoy, settings.MOD_PREFIX[:2])])
        assert not user_can_moderate(user, guild, channel)


class TestGenerateSignedUrl:
    def test_generates_url_with_signature(self, decoy: Decoy, stub: Stub) -> None:
        time_fake = stub(signing.time, "time")
        decoy.when(time_fake(), ignore_extra_args=True).then_return(1000.0)
        url = generate_signed_url(12345, expires_in_minutes=10)
        assert "/g/12345/analytics?" in url
        assert "expires=1600" in url
        assert "sig=" in url

    def test_valid_signature_roundtrip(self, decoy: Decoy, stub: Stub) -> None:
        time_fake = stub(signing.time, "time")
        decoy.when(time_fake(), ignore_extra_args=True).then_return(1000.0)
        url = generate_signed_url(12345, expires_in_minutes=10)
        # Extract expires and sig from the URL
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        expires = int(params["expires"][0])
        sig = params["sig"][0]
        assert validate_signature(12345, expires, sig)

    def test_validate_expired_signature(self, decoy: Decoy, stub: Stub) -> None:
        time_fake = stub(signing.time, "time")
        decoy.when(time_fake(), ignore_extra_args=True).then_return(2000.0)
        # Expired in the past
        assert not validate_signature(12345, 1000, "anything")

    def test_validate_wrong_signature(self, decoy: Decoy, stub: Stub) -> None:
        time_fake = stub(signing.time, "time")
        decoy.when(time_fake(), ignore_extra_args=True).then_return(1000.0)
        assert not validate_signature(12345, 2000, "bad-sig")

    def test_validate_signature_bypass_when_check_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When CHECK_SIGNATURE is False, validate_signature should always return True."""
        monkeypatch.setattr(signing.settings, "CHECK_SIGNATURE", False)
        # Even with bad/expired signature, should return True
        assert validate_signature(12345, 0, "invalid-sig")


class TestTracedInteraction:
    def test_discord_annotations_still_resolve(self) -> None:
        # `@tracer.wrap` broke commands with `discord.User` parameters because discord.py
        # resolves annotations against the callback's globals.
        class Probe(commands.Cog):
            @app_commands.command(name="probe", description="probe")
            @app_commands.describe(target="who")
            @traced_interaction()
            async def probe(
                self,
                interaction: discord.Interaction,
                target: discord.User | discord.Member,
            ) -> None:  # pragma: no cover
                del interaction, target

        (param,) = Probe.probe.parameters
        assert param.type is discord.AppCommandOptionType.user
        assert param.description == "who"
