from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from spellbot.database import DatabaseSession
from spellbot.models import Guild, GuildAward
from spellbot.services import guilds
from tests.factories import ChannelFactory, GuildAwardFactory, GuildFactory

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceGuilds:
    async def test_guilds_upsert(self) -> None:
        discord_guild = MagicMock()
        discord_guild.id = 101
        discord_guild.name = "guild-name"
        discord_guild.icon = None
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        guild = await DatabaseSession.get(Guild, discord_guild.id)
        assert guild
        assert guild.xid == discord_guild.id
        assert guild.name == "guild-name"

        discord_guild.name = "new-name"
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        guild = await DatabaseSession.get(Guild, discord_guild.id)
        assert guild
        assert guild.xid == discord_guild.id
        assert guild.name == "new-name"

    async def test_guilds_get(self) -> None:
        assert not await guilds.get(404)

        GuildFactory.create(xid=404)

        guild_data = await guilds.get(404)
        assert guild_data is not None
        assert guild_data.xid == 404

    async def test_guilds_set_banned(self) -> None:
        guild = GuildFactory.create()

        await guilds.set_banned(guild.xid, banned=True)

        DatabaseSession.expire_all()
        guild = await DatabaseSession.get(Guild, guild.xid)
        assert guild
        assert guild.banned

    async def test_guilds_voiced(self) -> None:
        assert await guilds.voiced() == []

        guild1 = GuildFactory.create(voice_create=True)
        GuildFactory.create()
        guild3 = GuildFactory.create(voice_create=True)
        GuildFactory.create(voice_create=True, active=False)

        assert set(await guilds.voiced()) == {guild1.xid, guild3.xid}

    async def test_guilds_set_active(self) -> None:
        guild = GuildFactory.create()
        assert guild.active is True

        await guilds.set_active(guild.xid, active=False)
        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.active is False

        await guilds.set_active(guild.xid, active=True)
        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.active is True

    async def test_guilds_upsert_is_noop_when_unchanged(self) -> None:
        guild = GuildFactory.create(name="guild-name")

        DatabaseSession.expire_all()
        before = await DatabaseSession.get(Guild, guild.xid)
        assert before
        original_updated_at = before.updated_at

        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_guild.name = "guild-name"
        discord_guild.icon = None
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.updated_at == original_updated_at

    async def test_guilds_upsert_skips_write_when_cached(self) -> None:
        discord_guild = MagicMock()
        discord_guild.id = 505
        discord_guild.name = "guild-name"
        discord_guild.icon = None
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        before = await DatabaseSession.get(Guild, discord_guild.id)
        assert before
        original_updated_at = before.updated_at

        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, discord_guild.id)
        assert refreshed
        assert refreshed.updated_at == original_updated_at

    async def test_guilds_upsert_reactivates_inactive_guild(self) -> None:
        guild = GuildFactory.create(active=False)

        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_guild.name = "reactivated-name"
        discord_guild.icon = None
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.active is True
        assert refreshed.name == "reactivated-name"

    async def test_guilds_upsert_persists_locale(self) -> None:
        discord_guild = MagicMock()
        discord_guild.id = 202
        discord_guild.name = "guild-name"
        discord_guild.icon = None
        await guilds.upsert(discord_guild, locale="es")

        DatabaseSession.expire_all()
        guild = await DatabaseSession.get(Guild, discord_guild.id)
        assert guild
        assert guild.locale == "es"

    async def test_guilds_upsert_updates_locale(self) -> None:
        guild = GuildFactory.create(locale="en")

        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_guild.name = guild.name
        discord_guild.icon = None
        await guilds.upsert(discord_guild, locale="fr")

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.locale == "fr"

    async def test_guilds_upsert_is_noop_when_locale_unchanged(self) -> None:
        guild = GuildFactory.create(name="guild-name", locale="en")

        DatabaseSession.expire_all()
        before = await DatabaseSession.get(Guild, guild.xid)
        assert before
        original_updated_at = before.updated_at

        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_guild.name = "guild-name"
        discord_guild.icon = None
        await guilds.upsert(discord_guild, locale="en")

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.updated_at == original_updated_at
        assert refreshed.locale == "en"

    async def test_guilds_upsert_persists_icon(self) -> None:
        icon_url = "https://cdn.discordapp.com/icons/303/abc.png"
        discord_guild = MagicMock()
        discord_guild.id = 303
        discord_guild.name = "guild-name"
        discord_guild.icon = icon_url
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        guild = await DatabaseSession.get(Guild, discord_guild.id)
        assert guild
        assert guild.icon == icon_url

    async def test_guilds_upsert_updates_icon(self) -> None:
        guild = GuildFactory.create(icon="https://cdn.discordapp.com/icons/304/old.png")

        new_icon = "https://cdn.discordapp.com/icons/304/new.png"
        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_guild.name = guild.name
        discord_guild.icon = new_icon
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.icon == new_icon

    async def test_guilds_upsert_clears_icon_when_removed(self) -> None:
        guild = GuildFactory.create(icon="https://cdn.discordapp.com/icons/305/old.png")

        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_guild.name = guild.name
        discord_guild.icon = None
        await guilds.upsert(discord_guild)

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.icon is None

    async def test_guilds_set_icon(self) -> None:
        guild = GuildFactory.create(icon=None)

        url = "https://cdn.discordapp.com/icons/306/feedface.png"
        await guilds.set_icon(guild.xid, url)
        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.icon == url

        await guilds.set_icon(guild.xid, None)
        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.icon is None

    async def test_guilds_award_add(self) -> None:
        discord_guild = MagicMock()
        discord_guild.id = 101
        discord_guild.name = "guild-name"
        discord_guild.icon = None
        await guilds.upsert(discord_guild)
        await guilds.award_add(
            guild_xid=discord_guild.id,
            count=5,
            role="a-role",
            message="a-message",
        )

        award = (
            await DatabaseSession.execute(
                select(GuildAward).where(GuildAward.count == 5),
            )
        ).scalar_one_or_none()
        assert award
        assert award.role == "a-role"
        assert award.message == "a-message"
        assert award.guild_xid == discord_guild.id

    async def test_guilds_award_delete(self, guild: Guild) -> None:
        award1 = GuildAwardFactory.create(guild=guild)
        award2 = GuildAwardFactory.create(guild=guild)

        award1_id = award1.id
        assert await guilds.award_delete(guild.xid, award1.id) is True
        # Deleting a missing award, or one in another guild, is a no-op returning False.
        assert await guilds.award_delete(guild.xid, 404) is False
        assert await guilds.award_delete(guild.xid + 1, award2.id) is False

        DatabaseSession.expire_all()
        assert not await DatabaseSession.get(GuildAward, award1_id)
        assert await DatabaseSession.get(GuildAward, award2.id)

    async def test_guilds_award_update(self, guild: Guild) -> None:
        award = GuildAwardFactory.create(
            guild=guild,
            count=5,
            role="old-role",
            message="old-message",
            repeating=False,
        )

        updated = await guilds.award_update(
            guild.xid,
            award.id,
            count=10,
            role="new-role",
            message="new-message",
            repeating=True,
            verified_only=True,
        )
        assert updated is not None
        assert updated.count == 10
        assert updated.role == "new-role"
        assert updated.message == "new-message"
        assert updated.repeating is True
        assert updated.verified_only is True

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(GuildAward, award.id)
        assert refreshed is not None
        assert refreshed.count == 10
        assert refreshed.role == "new-role"

        # Updating a missing award, or one in another guild, returns None and changes nothing.
        assert await guilds.award_update(guild.xid, 404, count=1, role="x", message="y") is None
        assert (
            await guilds.award_update(guild.xid + 1, award.id, count=1, role="x", message="y")
            is None
        )

    async def test_guilds_award_list(self, guild: Guild) -> None:
        # Returned ordered by required game count, ascending.
        award_b = GuildAwardFactory.create(guild=guild, count=20, role="b")
        award_a = GuildAwardFactory.create(guild=guild, count=10, role="a")
        other_guild = GuildFactory.create()
        GuildAwardFactory.create(guild=other_guild, count=5, role="other")

        awards = await guilds.award_list(guild.xid)
        assert [a.id for a in awards] == [award_a.id, award_b.id]

    async def test_guilds_setup_mythic_track(self) -> None:
        guild = GuildFactory.create(xid=101, enable_mythic_track=False)
        guild_data = await guilds.get(guild.xid)
        assert guild_data is not None
        assert not guild_data.enable_mythic_track

        guild_data = await guilds.setup_mythic_track(guild_data)

        assert guild_data.enable_mythic_track
        DatabaseSession.expire_all()
        guild = await DatabaseSession.get(Guild, 101)
        assert guild
        assert guild.enable_mythic_track

    async def test_guilds_voice_category_prefixes(self) -> None:

        guild = GuildFactory.create(xid=101)
        ChannelFactory.create(guild=guild, voice_category="Voice Channels")
        ChannelFactory.create(guild=guild, voice_category="Voice Channels")
        ChannelFactory.create(guild=guild, voice_category="Other Category")

        prefixes = await guilds.voice_category_prefixes(guild.xid)

        assert set(prefixes) == {"Voice Channels", "Other Category"}


@pytest.mark.asyncio
class TestFetchIconUrl:
    async def test_returns_none_without_bot_token(self) -> None:
        with patch.object(guilds.settings, "BOT_TOKEN", None):
            assert await guilds.fetch_icon_url(401) is None

    async def test_returns_png_url_for_static_icon(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"icon": "deadbeef"})
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        with (
            patch.object(guilds.settings, "BOT_TOKEN", "tok"),
            patch.object(guilds.httpx, "AsyncClient", return_value=mock_client),
        ):
            url = await guilds.fetch_icon_url(402)
        assert url == "https://cdn.discordapp.com/icons/402/deadbeef.png"

    async def test_returns_gif_url_for_animated_icon(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"icon": "a_animated"})
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        with (
            patch.object(guilds.settings, "BOT_TOKEN", "tok"),
            patch.object(guilds.httpx, "AsyncClient", return_value=mock_client),
        ):
            url = await guilds.fetch_icon_url(403)
        assert url == "https://cdn.discordapp.com/icons/403/a_animated.gif"

    async def test_returns_none_when_guild_has_no_icon(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"icon": None})
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        with (
            patch.object(guilds.settings, "BOT_TOKEN", "tok"),
            patch.object(guilds.httpx, "AsyncClient", return_value=mock_client),
        ):
            assert await guilds.fetch_icon_url(404) is None

    async def test_returns_none_on_http_error(self) -> None:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("boom"))
        with (
            patch.object(guilds.settings, "BOT_TOKEN", "tok"),
            patch.object(guilds.httpx, "AsyncClient", return_value=mock_client),
        ):
            assert await guilds.fetch_icon_url(405) is None


@pytest.mark.asyncio
class TestServiceGuildsUpdateSettings:
    async def test_updates_allow_listed_fields(self) -> None:
        guild = GuildFactory.create(xid=9001, motd="old", show_links=False)
        await guilds.update_settings(guild.xid, motd="new", show_links=True)
        DatabaseSession.expire_all()
        updated = await DatabaseSession.get(Guild, guild.xid)
        assert updated is not None
        assert updated.motd == "new"
        assert updated.show_links is True

    async def test_ignores_unlisted_fields(self) -> None:
        guild = GuildFactory.create(xid=9002, banned=False, promote=True)
        await guilds.update_settings(guild.xid, banned=True, promote=False)
        DatabaseSession.expire_all()
        updated = await DatabaseSession.get(Guild, guild.xid)
        assert updated is not None
        assert updated.banned is False
        assert updated.promote is True

    async def test_no_safe_fields_is_a_noop(self) -> None:
        guild = GuildFactory.create(xid=9003, motd="keep")
        await guilds.update_settings(guild.xid, banned=True)
        DatabaseSession.expire_all()
        updated = await DatabaseSession.get(Guild, guild.xid)
        assert updated is not None
        assert updated.motd == "keep"
