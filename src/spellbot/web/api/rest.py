from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from aiohttp import web
from aiohttp_retry import ExponentialRetry, RetryClient
from dateutil import tz

from spellbot.database import db_session_manager
from spellbot.services import GamesService, PlaysService, UsersService
from spellbot.settings import settings
from spellbot.web.tools import rate_limited

if TYPE_CHECKING:
    from aiohttp.web_response import Response as WebResponse

    from spellbot.models import GameDict, UserDict

logger = logging.getLogger(__name__)


async def game_verify_endpoint(request: web.Request) -> WebResponse:
    try:
        async with db_session_manager():
            game_id = int(request.match_info["game"])
            payload = await request.json()
            user_xid = int(payload["user_xid"])
            guild_xid = int(payload["guild_xid"])
            pin = payload["pin"]
            plays = PlaysService()
            verified = await plays.verify_game_pin(
                game_id=game_id,
                user_xid=user_xid,
                guild_xid=guild_xid,
                pin=pin,
            )
            if not verified and await rate_limited(request, key=f"game_verify:{game_id}"):
                return web.json_response({"error": "Rate limited"}, status=429)
            return web.json_response({"result": {"verified": verified}})
    except ValueError as e:
        if await rate_limited(request):
            return web.json_response({"error": "Rate limited"}, status=429)
        return web.json_response({"error": str(e)}, status=400)
    except KeyError as e:
        if await rate_limited(request):
            return web.json_response({"error": "Rate limited"}, status=429)
        return web.json_response({"error": f"missing key: {e}"}, status=400)
    except Exception as e:
        if await rate_limited(request):
            return web.json_response({"error": "Rate limited"}, status=429)
        return web.json_response({"error": str(e)}, status=500)


def game_record_embed(
    *,
    game: GameDict,
    players: list[UserDict],
    commanders: dict[int | None, str],
    winner_xid: int | None,
    tracker_xid: int,
) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    winner_name = next((p["name"] for p in players if p["xid"] == winner_xid), None)
    winner_commander = commanders.get(winner_xid)
    tracker_name = next(p["name"] for p in players if p["xid"] == tracker_xid)
    has_winner = winner_xid and winner_name and winner_commander
    if has_winner:
        value = f"<@{winner_xid}> ({winner_name}) - {winner_commander}"
        fields = [{"name": "🎉 Winner 🎉", "value": value}]
    else:
        fields = [{"name": "No Winner", "value": "Draw game"}]
    fields.append(
        {
            "name": "Players",
            "value": "\n".join(
                f"• <@{p['xid']}> ({p['name']}) - {commanders[p['xid']]}" for p in players
            ),
        },
    )
    description = f"A game you played was tracked by <@{tracker_xid}> ({tracker_name})."
    if has_winner:
        description += f" The winner was marked as <@{winner_xid}> ({winner_name})."
    else:
        description += " No winner was marked, the game ended in a draw."
    jump_link = game["jump_links"].get(game["guild_xid"])
    channel_xid = game["channel_xid"]
    started_at = game["started_at"]
    assert started_at is not None
    started_at_ts = int(cast(datetime, started_at).replace(tzinfo=tz.UTC).timestamp())
    game_start = f"<t:{started_at_ts}>"
    description += (
        f"\n\nThe game was played in <#{channel_xid}> on {game_start}. "
        f"[Jump to the original game post]({jump_link}) to see more details."
        f"\n\n_If the winner is incorrect, please contact the server mods for help._"
    )
    return {
        "content": "",
        "embeds": [
            {
                "author": {
                    "name": "Your game was tracked on Mythic Track!",
                    "icon_url": settings.ICO_URL,
                },
                "description": description,
                "fields": fields,
                "color": f"#{settings.INFO_EMBED_COLOR:X}".lower(),
                "footer": {"text": f"SpellBot Game ID: #SB{game['id']}"},
            }
        ],
    }


async def send_dm(user_xid: int, message: dict[str, Any]) -> None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bot {settings.BOT_TOKEN}",
    }
    try:
        # create dm channel
        async with (
            RetryClient(
                raise_for_status=False,
                retry_options=ExponentialRetry(attempts=5),
            ) as client,
            client.post(
                "https://discord.com/api/users/@me/channels",
                headers=headers,
                json={"recipient_id": user_xid},
            ) as create_dm_resp,
        ):
            raw_data = await create_dm_resp.read()
            if not (data := json.loads(raw_data)):
                return

            # then send message to dm channel
            channel_xid = data["id"]
            async with client.post(
                f"https://discord.com/api/channels/{channel_xid}/messages",
                headers=headers,
                json=message,
            ):
                pass  # fire and forget...

    except Exception as ex:
        logger.warning(
            "warning: Discord API failure: %s, data: %s, raw: %s",
            ex,
            data,
            raw_data,
            exc_info=True,
        )


async def game_record_endpoint(request: web.Request) -> WebResponse:
    async with db_session_manager():
        users = UsersService()
        plays = PlaysService()
        games = GamesService()
        game_id = int(request.match_info["game"])
        if not (game := await games.select(game_id)):
            return web.json_response({"error": "Game not found"}, status=404)
        payload = await request.json()
        winner_xid = int(w) if (w := payload.get("winner")) else None
        tracker_xid = int(payload.get("tracker"))
        players_data = payload.get("players", []) or []
        commanders: dict[int | None, str] = {int(p["xid"]): p["commander"] for p in players_data}
        if not players_data:
            return web.json_response({"error": "No players provided"}, status=400)
        plays = await plays.get_plays_by_game_id(game_id)
        player_xids = [int(p["xid"]) for p in players_data]
        players = await users.get_players_by_xid(player_xids)
        if len(plays) != len(players) or len(players) != len(players_data):
            return web.json_response({"error": "Mismatched player count"}, status=400)
        embed = game_record_embed(
            game=game,
            players=players,
            commanders=commanders,
            winner_xid=winner_xid,
            tracker_xid=tracker_xid,
        )
        notify_player_tasks = [send_dm(player_xid, embed) for player_xid in player_xids]
        await asyncio.gather(*notify_player_tasks)
        return web.json_response({"result": {"success": True}})
