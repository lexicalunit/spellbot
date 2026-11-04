# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Real `httpx` clients answered by canned responses, through `httpx.MockTransport`.

Code under test builds its own `httpx.AsyncClient`, so `serve_httpx` swaps the class for one
that is wired to a responder. Everything else about the client is real: status codes, JSON
bodies, and transport errors behave exactly as they would against a live server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    import pytest

type Responder = Callable[[httpx.Request], httpx.Response]

# A JSON value, as sent in a request or response body.
type JSON = Mapping[str, JSON] | Sequence[JSON] | str | int | float | bool | None

# The real class, captured before any test patches it, so calling `serve_httpx` again in
# one test replaces the responder instead of wrapping the previous fake.
REAL_ASYNC_CLIENT = httpx.AsyncClient

DISCORD_TOKEN_PATH = "/api/oauth2/token"
DISCORD_IDENTIFY_PATH = "/api/users/@me"


def serve_httpx(monkeypatch: pytest.MonkeyPatch, respond: Responder) -> list[httpx.Request]:
    """Answer every `httpx.AsyncClient` made during the test with `respond`."""
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return respond(request)

    def make_client(*, timeout: float | httpx.Timeout | None = None) -> httpx.AsyncClient:
        return REAL_ASYNC_CLIENT(timeout=timeout, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(httpx, "AsyncClient", make_client)
    return requests


def client_for(respond: Responder) -> httpx.AsyncClient:
    """Build a real client whose requests `respond` answers, for code that takes a client."""
    return REAL_ASYNC_CLIENT(transport=httpx.MockTransport(respond))


def recording_client(response: httpx.Response) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    """Build a client that answers every request with `response`, and the requests it saw."""
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return response

    return client_for(respond), requests


def in_order(*responses: httpx.Response | type[httpx.TransportError]) -> Responder:
    """Answer requests with `responses`, one each, in order; an error class fails that request."""
    remaining = list(responses)

    def respond(request: httpx.Request) -> httpx.Response:
        response = remaining.pop(0)
        if isinstance(response, httpx.Response):
            return response
        raise response("boom", request=request)

    return respond


def raising(error: type[httpx.TransportError] = httpx.ConnectError) -> Responder:
    """Fail every request with a transport-level `error`."""

    def respond(request: httpx.Request) -> httpx.Response:
        raise error("boom", request=request)

    return respond


def discord_oauth(
    *,
    token_status: int = 200,
    token_json: Mapping[str, JSON] | None = None,
    identify_status: int = 200,
    identify_json: Mapping[str, JSON] | None = None,
) -> Responder:
    """Answer Discord's OAuth token exchange and identify calls."""

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == DISCORD_TOKEN_PATH:
            return httpx.Response(token_status, json=token_json or {"access_token": "tok"})
        if request.url.path == DISCORD_IDENTIFY_PATH:
            body = identify_json or {"id": "42", "username": "u"}
            return httpx.Response(identify_status, json=body)
        return httpx.Response(404)

    return respond
