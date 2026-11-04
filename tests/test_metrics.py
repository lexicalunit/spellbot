# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from ddtrace.constants import ERROR_MSG, ERROR_TYPE
from discord.http import HTTPClient, Route

from spellbot.metrics import (
    MAX_SPAN_ERROR_MSG,
    REPORTED_ERROR_TAG,
    span_error_tags,
    trace_discord_requests,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from discord import File
    from pytest_mock import MockerFixture


class TestSpanErrorTags:
    def test_reports_the_real_exception_type(self) -> None:
        tags = span_error_tags(httpx.ReadTimeout("took too long"))
        assert tags[ERROR_TYPE] == "ReadTimeout"

    def test_reports_the_real_message(self) -> None:
        tags = span_error_tags(ValueError("seatLimit must be at least 2"))
        assert tags[ERROR_MSG] == "seatLimit must be at least 2"

    def test_marks_the_span_as_a_reported_error(self) -> None:
        assert span_error_tags(ValueError("boom"))[REPORTED_ERROR_TAG] == "true"

    def test_falls_back_to_the_type_name_for_a_blank_message(self) -> None:
        tags = span_error_tags(httpx.ConnectError(""))
        assert tags[ERROR_MSG] == "ConnectError"

    def test_long_message_is_truncated(self) -> None:
        tags = span_error_tags(ValueError("y" * (MAX_SPAN_ERROR_MSG + 100)))
        assert tags[ERROR_MSG].count("y") == MAX_SPAN_ERROR_MSG
        assert tags[ERROR_MSG].endswith("… (truncated)")

    def test_message_at_limit_is_not_truncated(self) -> None:
        tags = span_error_tags(ValueError("y" * MAX_SPAN_ERROR_MSG))
        assert "(truncated)" not in tags[ERROR_MSG]

    def test_http_status_error_keeps_its_own_type(self) -> None:
        request = httpx.Request("POST", "https://api.convoke.games/api/game/create-game")
        response = httpx.Response(400, text="nope", request=request)
        ex = httpx.HTTPStatusError("400", request=request, response=response)
        tags = span_error_tags(ex)
        assert tags[ERROR_TYPE] == "HTTPStatusError"
        assert tags[ERROR_TYPE] != "OperationalError"


@pytest.mark.asyncio
class TestTraceDiscordRequests:
    async def test_span_wraps_the_whole_request(self, mocker: MockerFixture) -> None:
        events: list[str] = []
        span = MagicMock()
        trace = mocker.patch("spellbot.metrics.tracer.trace")
        trace.return_value.__enter__.side_effect = lambda: events.append("open") or span
        trace.return_value.__exit__.side_effect = lambda *_: events.append("close")

        class Client(HTTPClient):
            async def request(
                self,
                route: Route,
                *,
                files: Sequence[File] | None = None,
                form: Iterable[dict[str, Any]] | None = None,
                **kwargs: Any,
            ) -> Any:
                events.append(f"request files={files} form={form} {kwargs}")
                return "response"

        trace_discord_requests(Client)
        interaction_token = uuid4().hex
        route = Route(
            "POST",
            "/interactions/{interaction_id}/{interaction_token}/callback",
            interaction_id=123,
            interaction_token=interaction_token,
        )
        client = MagicMock(spec=HTTPClient)
        assert await Client.request(client, route, json={"content": "hi"}) == "response"

        assert events == [
            "open",
            "request files=None form=None {'json': {'content': 'hi'}}",
            "close",
        ]
        trace.assert_called_once_with(
            service="discord",
            name="http",
            resource="/interactions/{interaction_id}/{interaction_token}/callback",
        )
        tags = span.set_tags.call_args.args[0]
        assert tags == {
            "base": Route.BASE,
            "channel_xid": "None",
            "guild_xid": "None",
            "method": "POST",
        }
        assert interaction_token not in str(trace.call_args) + str(tags)
        assert Client.request.__name__ == "request"
