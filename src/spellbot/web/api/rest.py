from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import tenacity
from aiohttp import web
from dateutil import tz
from ddtrace.trace import tracer

from spellbot.database import db_session_manager
from spellbot.services import ServicesRegistry
from spellbot.settings import settings
from spellbot.web.tools import rate_limited

if TYPE_CHECKING:
    from datetime import datetime

    from aiohttp.web_response import Response as WebResponse

    from spellbot.models import GameDict, UserDict

logger = logging.getLogger(__name__)


@tracer.wrap(name="rest", resource="game_verify_endpoint")
async def game_verify_endpoint(request: web.Request) -> WebResponse:
    try:
        async with db_session_manager():
            game_id = int(request.match_info["game"])
            payload = await request.json()
            user_xid = int(payload["user_xid"])
            guild_xid = int(payload["guild_xid"])
            pin = payload["pin"]
            services = ServicesRegistry()
            verified = await services.plays.verify_game_pin(
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


@tracer.wrap(name="rest", resource="game_record_embed")
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
    started_at_ts = int(cast("datetime", started_at).replace(tzinfo=tz.UTC).timestamp())
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
                "color": settings.INFO_EMBED_COLOR,
                "footer": {"text": f"SpellBot Game ID: #SB{game['id']}"},
            },
        ],
    }


class InvalidJsonResponseError(ValueError): ...


def retry_if_not_401_or_403(exc: BaseException) -> bool:
    return not isinstance(exc, aiohttp.ClientResponseError) or exc.status not in {401, 403}


@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    after=tenacity.after_log(logger, logging.INFO),
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    retry=tenacity.retry_if_exception(retry_if_not_401_or_403),
)
@tracer.wrap(name="rest", resource="fetch_with_retry")
async def fetch_with_retry(
    session: aiohttp.ClientSession,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bot {settings.BOT_TOKEN}",
    }
    async with session.post(
        f"https://discord.com/api{path}",
        headers=headers,
        json=payload,
    ) as response:
        response.raise_for_status()
        raw_data = await response.read()
        if not (data := json.loads(raw_data)):
            logger.error("API ERROR, json invalid: %s", raw_data.decode())
            raise InvalidJsonResponseError
        return data


@tracer.wrap(name="rest", resource="send_dm")
async def send_dm(user_xid: int, message: dict[str, Any]) -> None:
    logger.info("Beginning DM send to user %s...", user_xid)
    try:
        async with aiohttp.ClientSession() as session:
            # create dm channel
            dm_channel = await fetch_with_retry(
                session,
                "/users/@me/channels",
                {"recipient_id": user_xid},
            )
            logger.info("DM channel to user %s created", user_xid)

            # then send message to dm channel
            channel_xid = dm_channel["id"]
            logger.info("Sending DM to user %s...", user_xid)
            dm_message = await fetch_with_retry(
                session,
                f"/channels/{channel_xid}/messages",
                message,
            )
            logger.info("Sent DM to user %s with response: %s", user_xid, json.dumps(dm_message))

    except aiohttp.ClientResponseError as ex:
        if ex.status in {401, 403}:
            logger.info("Not allowed to DM this user: %s", user_xid)
    except Exception as ex:
        logger.warning("Discord API failure: %s", ex, exc_info=True)


@tracer.wrap(name="rest", resource="game_record_endpoint")
async def game_record_endpoint(request: web.Request) -> WebResponse:
    async with db_session_manager():
        services = ServicesRegistry()
        game_id = int(request.match_info["game"])
        if not (game := await services.games.select(game_id)):
            return web.json_response({"error": "Game not found"}, status=404)
        payload = await request.json()
        winner_xid = int(w) if (w := payload.get("winner")) else None
        tracker_xid = int(payload.get("tracker"))
        players_data = payload.get("players", []) or []
        commanders: dict[int | None, str] = {int(p["xid"]): p["commander"] for p in players_data}
        if not players_data:
            return web.json_response({"error": "No players provided"}, status=400)
        plays = await services.plays.get_plays_by_game_id(game_id)
        player_xids = [int(p["xid"]) for p in players_data]
        players = await services.users.get_players_by_xid(player_xids)
        if len(plays) != len(players) or len(players) != len(players_data):
            return web.json_response({"error": "Mismatched player count"}, status=400)
        embed = game_record_embed(
            game=game,
            players=players,
            commanders=commanders,
            winner_xid=winner_xid,
            tracker_xid=tracker_xid,
        )
        logger.info("Sending DMs to players %s...", ", ".join(str(x) for x in player_xids))
        notify_player_tasks = [send_dm(player_xid, embed) for player_xid in player_xids]
        await asyncio.gather(*notify_player_tasks)
        return web.json_response({"result": {"success": True}})
