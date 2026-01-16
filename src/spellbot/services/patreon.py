from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from asgiref.sync import sync_to_async
from ddtrace.trace import tracer

from spellbot.environment import running_in_pytest
from spellbot.settings import settings

logger = logging.getLogger(__name__)


def get_patreon_campaign_url() -> str:
    return (
        f"https://www.patreon.com/api/oauth2/v2/campaigns/{settings.PATREON_CAMPAIGN}/members?"
        + urlencode(
            {
                "fields[member]": "patron_status",
                "fields[user]": "social_connections",
                "include": "user",
            },
        )
    )


def get_patron_ids(data: dict[str, Any]) -> set[str]:
    """Extract Patreon's Discord IDs for active patrons."""
    active_members: set[str] = set()
    members: list[dict[str, Any]] = data.get("data") or []
    for member in members:
        if not (attributes := member.get("attributes")):
            continue
        if not (patron_status := attributes.get("patron_status")):
            continue
        if patron_status != "active_patron":
            continue
        if not (relationships := member.get("relationships")):
            continue
        if not (user := relationships.get("user")):
            continue
        if not (user_data := user.get("data")):
            continue
        if not (user_id := user_data.get("id")):
            continue
        active_members.add(user_id)
    return active_members


def get_supporters(data: dict[str, Any], patrons: set[str]) -> set[int]:
    supporters: set[int] = {711717544435646494}  # test account
    included = data.get("included") or []
    for item in included:
        if not (item_id := item.get("id")):
            continue
        if item_id in patrons:
            attributes = item.get("attributes") or {}
            social_connections = attributes.get("social_connections") or {}
            discord = social_connections.get("discord") or {}
            if discord_id := discord.get("user_id"):
                supporters.add(int(discord_id))
    return supporters


class PatreonService:
    @sync_to_async()
    @tracer.wrap()
    def supporters(self) -> set[int]:
        """Return a list of Discord IDs of active Patreon supporters."""
        if running_in_pytest():
            return set()

        response: httpx.Response | None = None
        all_patrons: set[str] = set()
        all_included: list[dict[str, Any]] = []

        try:
            headers = {"Authorization": f"Bearer {settings.PATREON_TOKEN}"}
            next_url: str | None = get_patreon_campaign_url()

            with httpx.Client(timeout=10.0) as client:
                while next_url:
                    response = client.get(next_url, headers=headers)

                    if response.status_code != 200:
                        logger.error("patreon sync failed, error response: %s", response.text)
                        break

                    data = response.json()
                    all_patrons.update(get_patron_ids(data))
                    all_included.extend(data.get("included") or [])
                    links = data.get("links") or {}
                    next_url = links.get("next")

            combined_data: dict[str, Any] = {"included": all_included}
            return get_supporters(combined_data, all_patrons)

        except Exception:
            logger.exception(
                "patreon sync failed, unknown error: %s",
                response.text if response else "no response",
            )
            return set()
