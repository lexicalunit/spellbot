from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import tenacity
from aiohttp import web
from dateutil import parser, tz
from ddtrace.trace import tracer

from spellbot.database import db_session_manager
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.services import NotificationData, ServicesRegistry
from spellbot.settings import settings
from spellbot.web.tools import rate_limited

if TYPE_CHECKING:
    from datetime import datetime

    from aiohttp.web_response import Response as WebResponse

    from spellbot.models import GameDict, UserDict

logger = logging.getLogger(__name__)

UNRECOVERABLE = {400, 401, 403, 404}


def reply(
    data: dict[str, Any] | None = None,
    *,
    status: int | None = None,
    error: str | None = None,
) -> WebResponse:
    data = data or {}
    status = status or (200 if error is None else 500)
    if error is None:
        return web.json_response({"result": data}, status=status)
    return web.json_response({"error": error}, status=status)


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
                return reply({}, error="Rate limited", status=429)
            return reply({"verified": verified})
    except ValueError as e:
        if await rate_limited(request):
            return reply({}, error="Rate limited", status=429)
        return reply(error=str(e), status=400)
    except KeyError as e:
        if await rate_limited(request):
            return reply({}, error="Rate limited", status=429)
        return reply(error=f"missing key: {e}", status=400)
    except Exception as e:
        if await rate_limited(request):
            return reply({}, error="Rate limited", status=429)
        return reply(error=str(e))


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


def retry_if_not_unrecoverable(exc: BaseException) -> bool:
    return not isinstance(exc, aiohttp.ClientResponseError) or exc.status not in UNRECOVERABLE


@tenacity.retry(
    stop=tenacity.stop_after_attempt(5),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    after=tenacity.after_log(logger, logging.INFO),
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    retry=tenacity.retry_if_exception(retry_if_not_unrecoverable),
)
@tracer.wrap(name="rest", resource="post_with_retry")
async def post_with_retry(
    session: aiohttp.ClientSession,
    path: str,
    payload: dict[str, Any] | None = None,
    method: str = "post",
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bot {settings.BOT_TOKEN}",
    }
    op = getattr(session, method)
    async with op(
        f"https://discord.com/api{path}",
        headers=headers,
        json=payload,
    ) as response:
        response.raise_for_status()
        return await response.json()


@tracer.wrap(name="rest", resource="send_message")
async def send_message(channel_xid: int, message: dict[str, Any]) -> dict[str, Any] | None:
    logger.info("Sending message to channel %s...", channel_xid)
    try:
        async with aiohttp.ClientSession() as session:
            return await post_with_retry(
                session,
                f"/channels/{channel_xid}/messages",
                message,
            )
    except Exception as ex:
        logger.warning("Send message failure: %s", ex, exc_info=True)
    return None


@tracer.wrap(name="rest", resource="update_message")
async def update_message(
    channel_xid: int,
    message_xid: int,
    message: dict[str, Any],
) -> dict[str, Any] | None:
    logger.info("Sending message to channel %s...", channel_xid)
    try:
        async with aiohttp.ClientSession() as session:
            return await post_with_retry(
                session,
                f"/channels/{channel_xid}/messages/{message_xid}",
                message,
                method="patch",
            )
    except Exception as ex:
        logger.warning("Send message failure: %s", ex, exc_info=True)
    return None


@tracer.wrap(name="rest", resource="delete_message")
async def delete_message(
    channel_xid: int,
    message_xid: int,
) -> dict[str, Any] | None:
    logger.info("Deleting message in channel %s...", channel_xid)
    try:
        async with aiohttp.ClientSession() as session:
            return await post_with_retry(
                session,
                f"/channels/{channel_xid}/messages/{message_xid}",
                method="delete",
            )
    except Exception as ex:
        logger.warning("Delete message failure: %s", ex, exc_info=True)
    return None


@tracer.wrap(name="rest", resource="send_dm")
async def send_dm(user_xid: int, message: dict[str, Any]) -> None:
    logger.info("Beginning DM send to user %s...", user_xid)
    try:
        async with aiohttp.ClientSession() as session:
            # create dm channel
            dm_channel = await post_with_retry(
                session,
                "/users/@me/channels",
                {"recipient_id": user_xid},
            )
            logger.info("DM channel to user %s created", user_xid)

            # then send message to dm channel
            channel_xid = dm_channel["id"]
            logger.info("Sending DM to user %s...", user_xid)
            dm_message = await post_with_retry(
                session,
                f"/channels/{channel_xid}/messages",
                message,
            )
            logger.info("Sent DM to user %s with response: %s", user_xid, json.dumps(dm_message))

    except aiohttp.ClientResponseError as ex:
        if ex.status in UNRECOVERABLE:
            logger.info("Not allowed to DM this user: %s", user_xid)
    except Exception as ex:
        logger.warning("Discord API failure: %s", ex, exc_info=True)


@tracer.wrap(name="rest", resource="game_record_embed")
def game_notification_message(notif: NotificationData) -> dict[str, Any]:
    service = str(GameService(notif.service))
    fields = [
        {"name": "Players", "value": "\n".join(f"• {player}" for player in notif.players)},
        {"name": "Format", "value": str(GameFormat(notif.format)), "inline": True},
    ]
    if notif.bracket != GameBracket.NONE.value:
        bracket = GameBracket(notif.bracket)
        bracket_title = str(bracket)
        name = bracket_title[8:]
        icon = bracket.icon
        bracket_str = f"{icon} {name}" if icon else name
        fields.append({"name": "Bracket", "value": bracket_str, "inline": True})
    if notif.started_at:
        started_ts = int(cast("datetime", notif.started_at).replace(tzinfo=tz.UTC).timestamp())
        fields.append({"name": "Started at", "value": f"<t:{started_ts}>", "inline": True})
        description = "Spectate the game by opening the game link in your browser."
        title = f"**This game has begun on {service}.**"
    else:
        updated_ts = int(cast("datetime", notif.updated_at).replace(tzinfo=tz.UTC).timestamp())
        fields.append({"name": "Updated at", "value": f"<t:{updated_ts}>", "inline": True})
        description = "Join the game by opening the game link in your browser."
        title = f"**There's a new public game on {service}!**"
    message = {
        "content": "",
        "embeds": [
            {
                "title": title,
                "description": description,
                "fields": fields,
                "color": (
                    settings.STARTED_EMBED_COLOR
                    if notif.started_at
                    else settings.PENDING_EMBED_COLOR
                ),
                "thumbnail": {"url": settings.thumb(notif.guild)},
                "footer": {
                    "text": f"SpellBot Notification ID: #SN{notif.id} — Service: {service}",
                },
            },
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": "Open Game Link",
                        "url": notif.link,
                    },
                ],
            },
        ],
    }
    if notif.role:
        message["content"] = f"<@&{notif.role}>"
        message["allowed_mentions"] = {"roles": [notif.role]}
    return message


def parse_datetime_str(dt_str: str) -> datetime:
    dt = parser.isoparse(dt_str)
    return dt.replace(tzinfo=tz.UTC) if dt.tzinfo is None else dt.astimezone(tz.UTC)


@tracer.wrap(name="rest", resource="create_notification_endpoint")
async def create_notification_endpoint(request: web.Request) -> WebResponse:
    async with db_session_manager():
        services = ServicesRegistry()
        payload = await request.json()
        link = payload["link"]
        guild = int(payload["guild"])
        channel = int(payload["channel"])
        players = payload["players"]
        format = payload["format"]
        bracket = payload["bracket"]
        service = payload["service"]
        started_at = payload.get("started_at")
        role = payload.get("role")
        notif = NotificationData(
            link=link,
            guild=guild,
            channel=channel,
            players=players,
            format=format,
            bracket=bracket,
            service=service,
            started_at=parse_datetime_str(started_at) if started_at else None,
            role=role,
        )
        notif = await services.notifications.create(notif)
        message = game_notification_message(notif)
        message_id: int | None = None
        if (
            (resp := await send_message(channel, message))
            and (message_id := resp.get("id"))
            and (notif_id := notif.id)
        ):
            await services.notifications.set_message(notif_id, message_id)
        return reply({"success": bool(resp and message_id), "notification": notif.id}, status=201)


@tracer.wrap(name="rest", resource="update_notification_endpoint")
async def update_notification_endpoint(request: web.Request) -> WebResponse:
    try:
        async with db_session_manager():
            services = ServicesRegistry()
            payload = await request.json()
            notif_id = int(request.match_info["notif"])
            players = payload["players"]
            started_at = payload.get("started_at")
            notif = await services.notifications.update(
                notif_id,
                players=players,
                started_at=started_at,
            )
            if not notif:
                return reply(error="Notification not found", status=404)
            message = game_notification_message(notif)
            message_id: int | None = None
            if notif.message:
                resp = await update_message(notif.channel, notif.message, message)
                message_id = notif.message
            else:
                resp = await send_message(notif.channel, message)
                message_id = resp.get("id") if resp else None
            if not notif.message and message_id:
                await services.notifications.set_message(notif_id, message_id)
            return reply({"success": bool(resp and "id" in resp)})
    except Exception as e:
        return reply(error=str(e))


@tracer.wrap(name="rest", resource="delete_notification_endpoint")
async def delete_notification_endpoint(request: web.Request) -> WebResponse:
    try:
        async with db_session_manager():
            services = ServicesRegistry()
            notif_id = int(request.match_info["notif"])
            notif = await services.notifications.delete(notif_id)
            if not notif:
                return reply(error="Notification not found", status=404)
            if notif.message:
                await delete_message(notif.channel, notif.message)
            return reply({"success": True})
    except Exception as e:
        return reply(error=str(e))


@tracer.wrap(name="rest", resource="game_record_endpoint")
async def game_record_endpoint(request: web.Request) -> WebResponse:
    async with db_session_manager():
        services = ServicesRegistry()
        game_id = int(request.match_info["game"])
        if not (game := await services.games.select(game_id)):
            return reply(error="Game not found", status=404)
        payload = await request.json()
        winner_xid = int(w) if (w := payload.get("winner")) else None
        tracker_xid = int(payload.get("tracker"))
        players_data = payload.get("players", []) or []
        commanders: dict[int | None, str] = {int(p["xid"]): p["commander"] for p in players_data}
        if not players_data:
            return reply(error="No players provided", status=400)
        plays = await services.plays.get_plays_by_game_id(game_id)
        player_xids = [int(p["xid"]) for p in players_data]
        players = await services.users.get_players_by_xid(player_xids)
        if len(plays) != len(players) or len(players) != len(players_data):
            return reply(error="Mismatched player count", status=400)
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
        return reply({"success": True})
