# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Decoy-backed builders for discord.py objects, mirroring the `build_*` helpers in `tests.mocks`.

Unlike `MagicMock`, a decoy keeps the real discord.py type, so calls can be verified with full
type checking: `decoy.verify(await message.delete())`. Plain attributes are assigned directly;
read-only properties must be stubbed with `decoy.when(obj.prop).then_return(...)`.
Decoy never invents behavior, so anything the code under test reads that isn't set up here comes
back as a bare mock: stub it in the test.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, NoReturn

import discord
from decoy import matchers
from discord.state import ConnectionState

from tests.mocks.ids import CLIENT_USER_ID, OWNER_USER_ID

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from decoy import Decoy
    from discord.types.emoji import Emoji as EmojiPayload
    from discord.types.role import Role as RolePayload

    from spellbot.models import Guild, User


class AnyValue:
    """A decoy matcher for any value, `None` included (decoy's own `Anything()` rejects `None`)."""

    def __eq__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "<ANY>"


# A wildcard stands in for an argument of any type, so `Any` is its true type, as it is for
# decoy's own `matchers.Anything()`.
ANY: Any = AnyValue()


def captured[T](captor: matchers.ValueCaptor[T], kind: type[T]) -> T:
    """Return what `captor` caught, checked to be a `kind` (decoy types the value as `object`)."""
    value = captor.value
    assert isinstance(value, kind), value
    return value


def guild(decoy: Decoy, offset: int = 1) -> discord.Guild:
    guild = decoy.mock(cls=discord.Guild)
    guild.id = 2000 + offset
    guild.name = f"guild-{guild.id}"
    guild.owner_id = OWNER_USER_ID
    guild.preferred_locale = discord.Locale.american_english
    decoy.when(guild.icon).then_return(None)
    decoy.when(guild.bitrate_limit).then_return(64000.0)
    return guild


def channel(decoy: Decoy, guild: discord.Guild, offset: int = 1) -> discord.TextChannel:
    channel = decoy.mock(cls=discord.TextChannel)
    channel.id = 3000 + offset
    channel.name = f"channel-{channel.id}"
    channel.guild = guild
    decoy.when(channel.type).then_return(discord.ChannelType.text)
    decoy.when(channel.permissions_for(matchers.IsA(discord.Member))).then_return(
        discord.Permissions(),
    )
    return channel


def member(decoy: Decoy, offset: int = 1) -> discord.Member:
    member = decoy.mock(cls=discord.Member)
    member.id = 1000 + offset
    decoy.when(member.display_name).then_return(f"user-{member.id}")
    decoy.when(member.mention).then_return(f"<@{member.id}>")
    decoy.when(member.roles).then_return([])
    return member


def message(
    decoy: Decoy,
    guild: discord.Guild,
    channel: discord.TextChannel,
    author: discord.Member,
    offset: int = 1,
) -> discord.Message:
    message = decoy.mock(cls=discord.Message)
    message.id = 4000 + offset
    message.content = "content"
    message.guild = guild
    message.channel = channel
    message.author = author
    return message


def partial_object(**attrs: object) -> Any:
    """
    Build a stand-in carrying only `attrs`.

    It's for the guards that handle discord.py objects missing an attribute, which typed
    code can't build, hence `Any`.
    """
    return SimpleNamespace(**attrs)


def guild_with(
    decoy: Decoy,
    me: discord.Member | None = None,
    *,
    owner_id: int = 2,
) -> discord.Guild:
    """Build a guild owned by `owner_id`, where the bot is `me`."""
    guild = decoy.mock(cls=discord.Guild)
    guild.id = 2000
    guild.owner_id = owner_id
    # discord.py types `me` as always set, but the bot's checks guard against it missing.
    decoy.when(guild.me).then_return(me)  # ty: ignore[invalid-argument-type]
    return guild


def bot_with(decoy: Decoy, *flags: int) -> discord.Member:
    """Build the bot's member, with the guild wide permissions `flags`."""
    permissions = discord.Permissions()
    for flag in flags:
        permissions.value |= flag
    me = decoy.mock(cls=discord.Member)
    me.id = CLIENT_USER_ID
    decoy.when(me.guild_permissions).then_return(permissions)
    return me


def text_channel(
    decoy: Decoy,
    guild: discord.Guild | None = None,
    permissions: discord.Permissions | None = None,
    channel_type: discord.ChannelType = discord.ChannelType.text,
) -> discord.TextChannel:
    """Build a channel in `guild` where everyone has `permissions` (none when unset)."""
    channel = decoy.mock(cls=discord.TextChannel)
    if guild is not None:
        channel.guild = guild
    # discord.py narrows a text channel's `type`, but the checks also handle private channels.
    decoy.when(channel.type).then_return(channel_type)  # ty: ignore[invalid-argument-type]
    if permissions is not None:
        decoy.when(channel.permissions_for(matchers.Anything())).then_return(permissions)
    return channel


def role(decoy: Decoy, guild: discord.Guild, *, role_id: int, name: str) -> discord.Role:
    """Build a real role in `guild`."""
    data: RolePayload = {
        "id": role_id,
        "name": name,
        "color": 0,
        "colors": {"primary_color": 0, "secondary_color": None, "tertiary_color": None},
        "hoist": False,
        "position": 0,
        "permissions": "0",
        "managed": False,
        "mentionable": False,
        "flags": 0,
    }
    return discord.Role(guild=guild, state=decoy.mock(cls=ConnectionState), data=data)


async def interaction(
    decoy: Decoy,
    guild: discord.Guild,
    channel: discord.TextChannel,
    user: discord.Member,
) -> discord.Interaction:
    """
    Build an interaction from `user` in `channel`.

    Its original response, and what it sends through its followup webhook, come back as a
    message in that channel.
    """
    found = decoy.mock(cls=discord.Interaction)
    found.user = user
    found.guild_id = guild.id
    found.channel = channel
    decoy.when(found.guild).then_return(guild)
    decoy.when(found.channel_id).then_return(channel.id)
    decoy.when(found.response).then_return(decoy.mock(cls=discord.InteractionResponse))
    original = message(decoy, guild, channel, user)
    decoy.when(await found.original_response()).then_return(original)
    followup = decoy.mock(cls=discord.Webhook)
    decoy.when(found.followup).then_return(followup)
    sent = decoy.mock(cls=discord.WebhookMessage)
    sent.id = original.id
    sent.guild = guild
    sent.channel = channel
    sent.author = user
    decoy.when(await followup.send(wait=True), ignore_extra_args=True).then_return(sent)
    return found


def from_user(decoy: Decoy, user: User) -> discord.Member:
    """Build the Discord member for a database user."""
    member = decoy.mock(cls=discord.Member)
    member.id = user.xid
    decoy.when(member.display_name).then_return(user.name)
    decoy.when(member.mention).then_return(f"<@{user.xid}>")
    return member


def from_guild(decoy: Decoy, guild: Guild) -> discord.Guild:
    """Build the Discord guild for a database guild."""
    found = decoy.mock(cls=discord.Guild)
    found.id = guild.xid
    found.name = guild.name or ""
    found.preferred_locale = discord.Locale.american_english
    decoy.when(found.icon).then_return(None)
    decoy.when(found.bitrate_limit).then_return(64000.0)
    return found


def emoji(decoy: Decoy, name: str, emoji_id: int = 9001) -> discord.Emoji:
    """Build a real emoji, which renders in text as `<:name:id>`."""
    state = decoy.mock(cls=ConnectionState)
    data: EmojiPayload = {"id": emoji_id, "name": name}
    return discord.Emoji(guild=discord.Object(id=1), state=state, data=data)


def async_returning[T](value: T) -> Callable[..., Coroutine[Any, Any, T]]:
    """Build an async stand-in that returns `value` for any call, to swap in with monkeypatch."""

    async def fake(*_: object, **__: object) -> T:
        return value

    return fake


def async_raising(error: BaseException) -> Callable[..., Coroutine[Any, Any, NoReturn]]:
    """Build an async stand-in that raises `error` for any call, to swap in with monkeypatch."""

    async def fake(*_: object, **__: object) -> NoReturn:
        raise error

    return fake
