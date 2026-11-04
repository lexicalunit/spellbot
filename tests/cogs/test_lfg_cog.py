# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import discord
import pytest
from decoy import matchers
from sqlalchemy import func, select, update

from spellbot import operations
from spellbot.actions import lfg_action
from spellbot.cogs import LookingForGameCog, lfg_cog
from spellbot.cogs.lfg_cog import guild_war_autocomplete
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat, GameService
from spellbot.integrations import convoke
from spellbot.models import Channel, Game, GameStatus, Guild, Queue, User
from spellbot.services.games import game_players
from spellbot.services.users import current_game
from spellbot.settings import settings as runtime_settings
from spellbot.views import GameView, lfg_view
from tests.fixtures import Factories, run_command
from tests.mocks import decoys, mock_discord_object, mock_operations
from tests.mocks.decoys import ANY, captured

if TYPE_CHECKING:
    from collections.abc import Callable

    from decoy import Decoy

    from spellbot import SpellBot
    from spellbot.settings import Settings
    from tests.fixtures import Stub

pytestmark = pytest.mark.use_db

CONVOKE_PENDING_MSG = (
    "_A [Convoke](https://www.convoke.games/) link will be created when all players have joined._"
)


def support_cta(guild_xid: int) -> str:
    return (
        "\n\n-# **Settings** — "
        f"See [live games]({runtime_settings.API_BASE_URL}/queues) and configure "
        f"[your notifications]({runtime_settings.API_BASE_URL}/queues/g/{guild_xid}).\n"
        "-# **Support SpellBot** — "
        "Become [a patron](https://www.patreon.com/lexicalunit) "
        "or give a [one-off tip](https://ko-fi.com/lexicalunit)."
    )


@pytest.fixture
def cog(bot: SpellBot) -> LookingForGameCog:
    return LookingForGameCog(bot)


@pytest.mark.asyncio
class TestCogLookingForGame:
    async def test_lfg(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, lfg_action):
            message = decoy.mock(cls=discord.Message)
            message.id = 123
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.lfg, interaction)

            decoy.verify(
                await operations.safe_followup_channel(
                    interaction,
                    content=None,
                    embed=ANY,
                    view=ANY,
                    allowed_mentions=ANY,
                ),
                times=1,
            )
            # check that the view (join/leave buttons) exists for pending games:
            safe_followup_channel_view = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_followup_channel(ANY, view=safe_followup_channel_view),
                ignore_extra_args=True,
            )
            assert isinstance(captured(safe_followup_channel_view, object), GameView)

        # Find the user created by this interaction
        user = (
            await DatabaseSession.execute(select(User).where(User.xid == interaction.user.id))
        ).scalar_one()
        # Find the game created in this channel
        game = (
            (
                await DatabaseSession.execute(
                    select(Game)
                    .where(
                        Game.channel_xid == channel.xid,
                        Game.guild_xid == guild.xid,
                    )
                    .order_by(Game.id.desc()),
                )
            )
            .scalars()
            .first()
        )
        assert game is not None
        assert game.channel_xid == channel.xid
        assert game.guild_xid == guild.xid
        assert interaction.channel is not None
        user_game = await current_game(user.xid, interaction.channel.id)
        assert user_game is not None
        assert user_game.id == game.id

    async def test_lfg_snapshots_channel_modes(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        decoy: Decoy,
    ) -> None:
        await DatabaseSession.execute(
            update(Channel)
            .where(Channel.xid == channel.xid)
            .values(to_mode=True, competitive_mode=True),
        )
        await DatabaseSession.commit()

        message = decoy.mock(cls=discord.Message)
        message.id = 123
        with mock_operations(decoy, lfg_action):
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)
            await run_command(cog.lfg, interaction)

        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        assert game.to_mode is True
        assert game.competitive_mode is True

    async def test_lfg_fully_seated(
        self,
        cog: LookingForGameCog,
        add_channel: Callable[..., Channel],
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        settings: Settings,
        decoy: Decoy,
    ) -> None:
        channel = add_channel(
            default_format=GameFormat.MODERN.value,
            default_service=GameService.COCKATRICE.value,
            default_seats=2,
            xid=interaction.channel_id,
        )
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            service=GameService.COCKATRICE.value,
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=123)

        other_user = factories.user.create(xid=interaction.user.id + 1, game=game)
        other_player = mock_discord_object(decoy, other_user)

        with mock_operations(decoy, lfg_action, users=[other_player]):
            message = decoy.mock(cls=discord.Message)
            message.id = game.posts[0].message_xid
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.lfg, interaction)

            DatabaseSession.expire_all()
            game = (await DatabaseSession.execute(select(Game))).scalar_one()
            started_at_timestamp = int(game.started_at.replace(tzinfo=UTC).timestamp())
            safe_update_embed_embed = matchers.ValueCaptor()
            safe_update_embed_view = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_update_embed(
                    ANY,
                    embed=safe_update_embed_embed,
                    view=safe_update_embed_view,
                ),
                ignore_extra_args=True,
            )
            assert captured(safe_update_embed_embed, discord.Embed).to_dict() == {
                "color": settings.STARTED_EMBED_COLOR,
                "description": (
                    "Please check your Direct Messages for your game details.\n\n"
                    f"{guild.motd}\n\n{channel.motd}"
                )
                + support_cta(guild.xid),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": (
                            f"• <@{interaction.user.id}> "
                            f"({interaction.user.display_name})\n"
                            f"• <@{other_player.id}> ({other_player.display_name})"
                        ),
                    },
                    {"inline": True, "name": "Format", "value": "Modern"},
                    {
                        "inline": True,
                        "name": "Started at",
                        "value": f"<t:{started_at_timestamp}>",
                    },
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Cockatrice"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Your game is ready!**",
                "type": "rich",
                "flags": 0,
            }
            # check that the view (join/leave buttons) is removed from fully seated games:
            assert captured(safe_update_embed_view, object) is None

    async def test_lfg_when_blocked(
        self,
        game: Game,
        user: User,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        other_user = factories.user.create(game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)

        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction)

        # Verify the original game still exists
        other_game = (
            await DatabaseSession.execute(select(Game).where(Game.id == game.id))
        ).scalar_one()
        assert other_game is not None
        # Verify a new game was created for the user (due to blocking)
        # The user should be in a different game now
        user_game = (
            await DatabaseSession.execute(
                select(Game)
                .join(Queue, Queue.game_id == Game.id)
                .where(Queue.user_xid == user.xid),
            )
        ).scalar_one()
        assert other_game.id != user_game.id

    async def test_lfg_when_already_in_game(
        self,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        channel: Channel,
        bot: SpellBot,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, lfg_action, users=[mock_discord_object(decoy, player)]):
            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction)

            decoy.verify(
                await operations.safe_followup_channel(
                    interaction,
                    "You're already in a game in this channel.",
                ),
                times=1,
            )

        found = (
            await DatabaseSession.execute(select(User).where(User.xid == player.xid))
        ).scalar_one()
        found_game = await current_game(found.xid, channel.xid)
        assert found_game is not None
        assert found_game.id == game.id

    async def test_lfg_with_format(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
    ) -> None:
        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction, format=GameFormat.MODERN.value)
        assert (
            await DatabaseSession.execute(select(Game))
        ).scalar_one().format == GameFormat.MODERN.value

    async def test_lfg_with_seats(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
    ) -> None:
        cog = LookingForGameCog(bot)
        await run_command(cog.lfg, interaction, seats=2)
        assert (await DatabaseSession.execute(select(Game))).scalar_one().seats == 2

    async def test_lfg_with_friends(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        decoy: Decoy,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        players = [mock_discord_object(decoy, x) for x in (user, friend1, friend2)]
        with mock_operations(decoy, lfg_action, users=players):
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        queues = list((await DatabaseSession.execute(select(Queue))).scalars().all())
        assert len(queues) == 3
        assert all(queue.game_id == game.id for queue in queues)

    async def test_lfg_with_friends_blocked(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        decoy: Decoy,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        factories.block.create(user_xid=user.xid, blocked_user_xid=friend1.xid)
        players = [mock_discord_object(decoy, x) for x in (user, friend1, friend2)]
        with mock_operations(decoy, lfg_action, users=players):
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        queues = list((await DatabaseSession.execute(select(Queue))).scalars().all())
        assert len(queues) == 2
        assert all(queue.game_id == game.id for queue in queues)
        assert not any(queue.user_xid == friend1.xid for queue in queues)

    async def test_lfg_with_friends_blocked_by(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        decoy: Decoy,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        factories.block.create(user_xid=friend1.xid, blocked_user_xid=user.xid)
        players = [mock_discord_object(decoy, x) for x in (user, friend1, friend2)]
        with mock_operations(decoy, lfg_action, users=players):
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            cog = LookingForGameCog(bot)
            await run_command(cog.lfg, interaction, friends=f"<@{friend1.xid}><@{friend2.xid}>")

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        queues = list((await DatabaseSession.execute(select(Queue))).scalars().all())
        assert len(queues) == 2
        assert all(queue.game_id == game.id for queue in queues)
        assert not any(queue.user_xid == friend1.xid for queue in queues)

    async def test_lfg_with_too_many_friends(
        self,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        decoy: Decoy,
    ) -> None:
        friend1 = factories.user.create()
        friend2 = factories.user.create()
        friend3 = factories.user.create()
        friend4 = factories.user.create()
        players = [
            mock_discord_object(decoy, x) for x in (user, friend1, friend2, friend3, friend4)
        ]
        with mock_operations(decoy, lfg_action, users=players):
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            cog = LookingForGameCog(bot)
            await run_command(
                cog.lfg,
                interaction,
                friends=f"<@{friend1.xid}><@{friend2.xid}><@{friend3.xid}><@{friend4.xid}>",
            )

        assert not (await DatabaseSession.execute(select(Game))).scalar_one_or_none()

    async def test_lfg_multiple_times(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        await run_command(cog.lfg, interaction)
        await run_command(cog.lfg, interaction)
        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 1

    async def test_rematch(
        self,
        cog: LookingForGameCog,
        user: User,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        friend = factories.user.create()
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            format=GameFormat.MODERN.value,
            service=GameService.GIRUDO.value,
            status=GameStatus.STARTED.value,
            started_at=datetime.now(tz=UTC),
        )
        message = decoy.mock(cls=discord.Message)
        message.id = 123
        factories.post.create(
            guild=guild,
            channel=channel,
            game=game,
            message_xid=message.id,
        )
        factories.play.create(user_xid=user.xid, game_id=game.id)
        factories.play.create(user_xid=friend.xid, game_id=game.id)
        players = [mock_discord_object(decoy, x) for x in (user, friend)]

        with mock_operations(decoy, lfg_action, users=players):
            message = decoy.mock(cls=discord.Message)
            message.id = 456
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.rematch, interaction)

            decoy.verify(
                await operations.safe_followup_channel(
                    interaction,
                    content=None,
                    embed=ANY,
                    view=ANY,
                    allowed_mentions=ANY,
                ),
                times=1,
            )

        DatabaseSession.expire_all()
        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 2

    async def test_start(
        self,
        cog: LookingForGameCog,
        user: User,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        game = factories.game.create(guild=guild, channel=channel, seats=4)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=123)
        factories.queue.create(user_xid=user.xid, game_id=game.id, og_guild_xid=guild.xid)
        other_user = factories.user.create()
        factories.queue.create(user_xid=other_user.xid, game_id=game.id, og_guild_xid=guild.xid)
        players = [mock_discord_object(decoy, x) for x in (user, other_user)]

        with mock_operations(decoy, lfg_action, users=players):
            message = decoy.mock(cls=discord.Message)
            message.id = 456
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.start, interaction)

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        assert game.status == GameStatus.STARTED.value
        assert game.seats == 2


@pytest.mark.asyncio
class TestCogLookingForGameJoinButton:
    async def test_join(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        settings: Settings,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(lfg_view, "safe_original_response", decoys.async_returning(message))
        with mock_operations(decoy, lfg_action, users=[mock_discord_object(decoy, user)]):
            decoy.when(
                await operations.safe_update_embed_origin(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(True)
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            safe_update_embed_origin_embed = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_update_embed_origin(
                    ANY,
                    embed=safe_update_embed_origin_embed,
                ),
                ignore_extra_args=True,
            )
            assert captured(safe_update_embed_origin_embed, discord.Embed).to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (f"{CONVOKE_PENDING_MSG}\n\n{guild.motd}\n\n{channel.motd}")
                + support_cta(guild.xid),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": f"• <@{user.xid}> (user-{user.xid})",
                    },
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_join_when_no_original_response(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(lfg_view, "safe_original_response", decoys.async_returning(None))
        with mock_operations(decoy, lfg_action, users=[mock_discord_object(decoy, user)]):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_join_when_blocked(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        other_user = factories.user.create(xid=user.xid + 1, game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)

        with mock_operations(
            decoy,
            lfg_action,
            users=[
                mock_discord_object(decoy, user),
                mock_discord_object(decoy, other_user),
            ],
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            decoy.verify(
                await operations.safe_send_user(interaction.user, "You can not join this game."),
                times=1,
            )

        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 1

    async def test_join_when_blocked_with_to_mode(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        # Tournament organizer mode ignores blocks, so the blocked user joins the game.
        other_user = factories.user.create(xid=user.xid + 1, game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=user.xid)
        await DatabaseSession.execute(
            update(Channel).where(Channel.xid == game.channel.xid).values(to_mode=True),
        )
        await DatabaseSession.commit()

        with mock_operations(
            decoy,
            lfg_action,
            users=[
                mock_discord_object(decoy, user),
                mock_discord_object(decoy, other_user),
            ],
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            decoy.verify(await operations.safe_send_user(user=ANY), times=0, ignore_extra_args=True)

        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 1
        DatabaseSession.expire_all()
        assert sorted(p.xid for p in await game_players(game)) == sorted([user.xid, other_user.xid])

    async def test_join_when_started(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        # fully seat and start the game
        factories.user.create(game=game)
        factories.user.create(game=game)
        factories.user.create(game=game)
        factories.user.create(game=game)
        await DatabaseSession.execute(
            update(Game)
            .where(Game.id == game.id)
            .values(started_at=datetime.now(tz=UTC), status=GameStatus.STARTED.value),
        )
        await DatabaseSession.commit()

        # then try to join it
        with mock_operations(
            decoy,
            lfg_action,
            users=[mock_discord_object(decoy, user)],
        ):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            decoy.verify(
                await operations.safe_send_user(
                    interaction.user,
                    "Sorry, that game has already started.",
                ),
                times=1,
            )

        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Game))).scalar() or 0
        ) == 1

    async def test_join_when_defer_fails(
        self,
        game: Game,
        user: User,
        message: discord.Message,
        interaction: discord.Interaction,
        bot: SpellBot,
        decoy: Decoy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(lfg_view, "safe_defer_interaction", decoys.async_returning(False))
        with mock_operations(decoy, lfg_action, users=[mock_discord_object(decoy, user)]):
            interaction.message = message
            view = GameView(bot=bot)

            await view.join(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )


WAR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
WAR_TITLE = "Summer Clash"


def live_war(
    war_id: str = WAR_ID,
    title: str = WAR_TITLE,
    slug: str = "summer-clash",
) -> dict[str, str]:
    return {"id": war_id, "title": title, "slug": slug, "status": "active"}


@pytest.mark.asyncio
class TestCogWar:
    async def test_war_creates_a_game_tagged_with_the_war(
        self,
        cog: LookingForGameCog,
        channel: Channel,
        interaction: discord.Interaction,
        guild: Guild,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        resolve_live_guild_war_fake = stub(convoke, "resolve_live_guild_war")
        decoy.when(
            await resolve_live_guild_war_fake(war_id=ANY),
            ignore_extra_args=True,
        ).then_return(live_war())
        with mock_operations(decoy, lfg_action):
            message = decoy.mock(cls=discord.Message)
            message.id = 123
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.war, interaction, war=WAR_ID)

        game = (
            (
                await DatabaseSession.execute(
                    select(Game)
                    .where(
                        Game.guild_xid == guild.xid,
                        Game.channel_xid == channel.xid,
                    )
                    .order_by(Game.id.desc()),
                )
            )
            .scalars()
            .first()
        )
        assert game is not None
        assert game.war_id == WAR_ID
        assert game.war_title == WAR_TITLE

    async def test_war_forces_convoke_over_a_channel_default(
        self,
        cog: LookingForGameCog,
        add_channel: Callable[..., Channel],
        interaction: discord.Interaction,
        guild: Guild,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        # Guild Wars only exist on Convoke, so `/war` must win over a channel that
        # defaults to some other service rather than failing the request.
        add_channel(xid=interaction.channel_id, default_service=GameService.COCKATRICE.value)
        resolve_live_guild_war_fake = stub(convoke, "resolve_live_guild_war")
        decoy.when(
            await resolve_live_guild_war_fake(war_id=ANY),
            ignore_extra_args=True,
        ).then_return(live_war())
        with mock_operations(decoy, lfg_action):
            message = decoy.mock(cls=discord.Message)
            message.id = 123
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.war, interaction, war=WAR_ID)

        game = (await DatabaseSession.execute(select(Game))).scalars().one()
        assert game.service == GameService.CONVOKE.value
        assert game.war_id == WAR_ID

    async def test_war_with_an_unknown_war_creates_no_game(
        self,
        cog: LookingForGameCog,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        resolve_live_guild_war_fake = stub(convoke, "resolve_live_guild_war")
        decoy.when(
            await resolve_live_guild_war_fake(war_id=ANY),
            ignore_extra_args=True,
        ).then_return(None)
        with mock_operations(decoy, lfg_action):
            await run_command(cog.war, interaction, war="not-a-real-war")

            safe_followup_channel_content = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_followup_channel(ANY, safe_followup_channel_content),
                ignore_extra_args=True,
            )
            reply = captured(safe_followup_channel_content, str)
            assert "not available" in reply

        assert (await DatabaseSession.execute(select(func.count(Game.id)))).scalar_one() == 0

    async def test_lfg_no_longer_takes_a_guild_war(self, cog: LookingForGameCog) -> None:
        # Guild Wars moved to their own command; leaving the option on `/lfg` would be
        # a second, harder-to-type way to do the same thing.
        assert "guild_war" not in {param.name for param in cog.lfg.parameters}
        assert "war" in {param.name for param in cog.war.parameters}

    async def test_war_only_offers_seat_counts_a_war_can_hold(
        self,
        cog: LookingForGameCog,
    ) -> None:
        seats = next(param for param in cog.war.parameters if param.name == "seats")
        offered = [choice.value for choice in seats.choices]
        assert offered == list(range(convoke.MIN_WAR_SEATS, convoke.MAX_WAR_SEATS + 1))

    async def test_war_does_not_offer_a_service(self, cog: LookingForGameCog) -> None:
        assert "service" not in {param.name for param in cog.war.parameters}


@pytest.mark.asyncio
class TestGuildWarAutocomplete:
    async def test_lists_every_live_war_when_nothing_is_typed(
        self,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        get_live_guild_wars_fake = stub(convoke, "get_live_guild_wars")
        decoy.when(await get_live_guild_wars_fake(), ignore_extra_args=True).then_return(
            [live_war(), live_war("id-2", "Winter Clash", "winter-clash")]
        )
        choices = await guild_war_autocomplete(interaction, "")
        assert [(c.name, c.value) for c in choices] == [
            (WAR_TITLE, WAR_ID),
            ("Winter Clash", "id-2"),
        ]

    async def test_filters_by_title(
        self,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        get_live_guild_wars_fake = stub(convoke, "get_live_guild_wars")
        decoy.when(await get_live_guild_wars_fake(), ignore_extra_args=True).then_return(
            [live_war(), live_war("id-2", "Winter Clash", "winter-clash")]
        )
        choices = await guild_war_autocomplete(interaction, "  WINTER ")
        assert [c.value for c in choices] == ["id-2"]

    async def test_filters_by_slug(
        self,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        # The slug is what shows up in Convoke URLs, so someone pasting one should
        # still find their war.
        get_live_guild_wars_fake = stub(convoke, "get_live_guild_wars")
        decoy.when(await get_live_guild_wars_fake(), ignore_extra_args=True).then_return(
            [live_war(), live_war("id-2", "Winter Clash", "winter-clash")]
        )
        choices = await guild_war_autocomplete(interaction, "summer-cl")
        assert [c.value for c in choices] == [WAR_ID]

    async def test_truncates_names_over_the_discord_limit(
        self,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        get_live_guild_wars_fake = stub(convoke, "get_live_guild_wars")
        decoy.when(await get_live_guild_wars_fake(), ignore_extra_args=True).then_return(
            [live_war(title="W" * 200)]
        )
        choices = await guild_war_autocomplete(interaction, "")
        assert len(choices[0].name) == 100
        assert choices[0].name.endswith("...")
        # The value is the war id, so truncating the label never breaks selection.
        assert choices[0].value == WAR_ID

    async def test_caps_at_the_discord_choice_limit(
        self,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        get_live_guild_wars_fake = stub(convoke, "get_live_guild_wars")
        decoy.when(await get_live_guild_wars_fake(), ignore_extra_args=True).then_return(
            [live_war(f"id-{i}", f"War {i}", f"war-{i}") for i in range(40)]
        )
        choices = await guild_war_autocomplete(interaction, "")
        assert len(choices) == 25

    async def test_an_unreachable_convoke_offers_nothing(
        self,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        # `get_live_guild_wars` swallows failures and returns []; autocomplete must
        # degrade to an empty list rather than erroring inside Discord's UI.
        get_live_guild_wars_fake = stub(convoke, "get_live_guild_wars")
        decoy.when(await get_live_guild_wars_fake(), ignore_extra_args=True).then_return([])
        assert await guild_war_autocomplete(interaction, "summer") == []


@pytest.mark.asyncio
class TestCogDeferFailure:
    """When Discord rejects the deferral, the interaction is gone, so the command does nothing."""

    @pytest.mark.parametrize(
        ("command", "kwargs"),
        [
            pytest.param("lfg", {}, id="lfg"),
            pytest.param("war", {"war": "Some War"}, id="war"),
            pytest.param("rematch", {}, id="rematch"),
            pytest.param("start", {}, id="start"),
        ],
    )
    async def test_stops_when_defer_fails(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        decoy: Decoy,
        stub: Stub,
        command: str,
        kwargs: dict[str, Any],
    ) -> None:
        safe_defer_interaction_fake = stub(lfg_cog, "safe_defer_interaction")
        decoy.when(
            await safe_defer_interaction_fake(interaction=ANY),
            ignore_extra_args=True,
        ).then_return(False)
        create = stub(lfg_cog.LookingForGameAction, "create")
        cog = LookingForGameCog(bot)
        await run_command(getattr(cog, command), interaction, **kwargs)
        decoy.verify(create(bot=ANY, interaction=ANY), times=0, ignore_extra_args=True)
