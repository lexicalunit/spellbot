# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx
import pytest
from ddtrace._trace.span import Span
from ddtrace.constants import ERROR_MSG, ERROR_TYPE
from discord.http import HTTPClient, Route

from spellbot import metrics
from spellbot.metrics import (
    MAX_SPAN_ERROR_MSG,
    REPORTED_ERROR_TAG,
    span_error_tags,
    tag_span,
    trace_discord_requests,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from types import TracebackType

    from decoy import Decoy
    from discord import File

    from tests.fixtures import Stub


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


class RecordingSpan(Span):
    """A real span that records when it opens and closes, and the tags it is given."""

    events: list[str]
    tags: dict[str, str]

    @classmethod
    def into(cls, events: list[str]) -> RecordingSpan:
        span = cls("test")
        span.events = events
        span.tags = {}
        return span

    def __enter__(self) -> Span:
        self.events.append("open")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.events.append("close")

    def set_tags(self, tags: dict[str, str]) -> None:
        self.tags.update(tags)


@pytest.mark.asyncio
class TestTraceDiscordRequests:
    async def test_span_wraps_the_whole_request(self, decoy: Decoy, stub: Stub) -> None:
        events: list[str] = []
        span = RecordingSpan.into(events)
        trace = stub(metrics.tracer, "trace")
        decoy.when(
            trace(
                service="discord",
                name="http",
                resource="/interactions/{interaction_id}/{interaction_token}/callback",
            ),
        ).then_return(span)

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
        client = decoy.mock(cls=Client)
        assert await Client.request(client, route, json={"content": "hi"}) == "response"

        assert events == [
            "open",
            "request files=None form=None {'json': {'content': 'hi'}}",
            "close",
        ]
        # The span is named by the route template, never the interaction token.
        assert span.tags == {
            "base": Route.BASE,
            "channel_xid": "None",
            "guild_xid": "None",
            "method": "POST",
            "data": "{'files': None, 'form': None, 'json': {'content': 'hi'}}",
        }
        assert interaction_token not in str(span.tags)
        assert Client.request.__name__ == "request"


class TestTagSpan:
    def test_tags_the_current_span_with_strings(self, decoy: Decoy, stub: Stub) -> None:
        span = decoy.mock(cls=Span)
        current_span_fake = stub(metrics.tracer, "current_span")
        decoy.when(current_span_fake(), ignore_extra_args=True).then_return(span)
        tag_span({"warning.type": "x"}, guild_xid=123, remove=False, missing=None)
        decoy.verify(
            span.set_tags(
                {
                    "warning.type": "x",
                    "guild_xid": "123",
                    "remove": "False",
                    "missing": "None",
                },
            ),
            times=1,
        )

    def test_no_current_span(self, decoy: Decoy, stub: Stub) -> None:
        current_span_fake = stub(metrics.tracer, "current_span")
        decoy.when(current_span_fake(), ignore_extra_args=True).then_return(None)
        tag_span(guild_xid=123)  # nothing to tag, and no error
