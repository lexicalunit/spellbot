# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import uuid
from functools import update_wrapper, wraps
from typing import TYPE_CHECKING, Any

from datadog import initialize
from ddtrace.constants import ERROR_MSG, ERROR_TYPE
from ddtrace.trace import tracer
from discord.app_commands import CommandOnCooldown
from discord.http import HTTPClient

from .environment import running_in_pytest
from .errors import AdminOnlyError, GuildBannedError, GuildOnlyError, ModOnlyError, UserBannedError
from .settings import settings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from ddtrace.trace import Span
    from discord import File
    from discord.http import Route

IS_RUNNING_IN_PYTEST = running_in_pytest()


def no_metrics() -> bool:
    return (
        IS_RUNNING_IN_PYTEST
        or not settings.DD_API_KEY
        or not settings.DD_APP_KEY
        or not settings.DD_TRACE_ENABLED
    )


def skip_if_no_metrics(f: Any) -> Callable[..., None]:  # pragma: no cover
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        return None if no_metrics() else f(*args, **kwargs)

    return wrapper


def trace_discord_requests(client: type[HTTPClient]) -> None:
    """
    Wrap `client.request` in a `discord.http` span that lasts until the response.

    The resource is the route's path template, which has placeholders in place of ids
    and interaction tokens. The request body isn't tagged: it holds message content
    and other user data. The wrapper repeats `HTTPClient.request`'s exact signature so
    it type-checks as a drop-in replacement.
    """
    request = client.request

    async def traced(
        self: HTTPClient,
        route: Route,
        *,
        files: Sequence[File] | None = None,
        form: Iterable[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        with tracer.trace(service="discord", name="http", resource=route.path) as span:
            span.set_tags(
                {
                    "base": route.BASE,
                    "channel_xid": str(route.channel_id),
                    "guild_xid": str(route.guild_id),
                    "method": route.method,
                },
            )
            return await request(self, route, files=files, form=form, **kwargs)

    update_wrapper(traced, request)
    # ty types a method attribute as that exact function, so it rejects any replacement,
    # even this one with the identical signature.
    client.request = traced  # ty: ignore[invalid-assignment]


@skip_if_no_metrics
def patch_discord() -> None:  # pragma: no cover
    trace_discord_requests(HTTPClient)


@skip_if_no_metrics
def setup_metrics() -> None:  # pragma: no cover
    initialize(api_key=settings.DD_API_KEY, app_key=settings.DD_APP_KEY)
    patch_discord()


def generate_request_id() -> str:
    """Generate a unique request ID for spans."""
    return str(uuid.uuid4())


@skip_if_no_metrics
def add_span_request_id(request_id: str) -> None:  # pragma: no cover
    """Add a request_id to the current span."""
    if span := tracer.current_span():
        span.set_tag("request_id", request_id)


@skip_if_no_metrics
def add_span_context(interaction: Any) -> None:  # pragma: no cover
    if span := tracer.current_span():
        # Use interaction.id as the request ID for tracing
        if interaction_id := getattr(interaction, "id", None):
            span.set_tag("request_id", str(interaction_id))
            span.set_tag("interaction_id", interaction_id)
        # Standardize on user_xid for the user's Discord ID
        user = getattr(interaction, "user", None) or getattr(interaction, "author", None)
        if user_id := getattr(user, "id", None):
            span.set_tag("user_xid", str(user_id))
        if application_id := getattr(interaction, "application_id", None):
            span.set_tag("application_id", application_id)
        # Standardize on channel_xid and guild_xid
        if channel_id := getattr(interaction, "channel_id", None):
            span.set_tag("channel_xid", str(channel_id))
        if component_id := getattr(interaction, "component_id", None):
            span.set_tag("component_id", component_id)
        if data := getattr(interaction, "data", None):
            span.set_tag("data", data)
        if guild_id := getattr(interaction, "guild_id", None):
            span.set_tag("guild_xid", str(guild_id))


# Marks the one span per trace that carries a reported failure. ddtrace also flags every
# span an exception propagated through, so counting error spans counts a single failure
# several times over; alerting counts this tag instead. See `add_span_error`.
REPORTED_ERROR_TAG = "spellbot.error.reported"

# Longest error message we put on a span. Keeps a huge repr (an API body, say) from
# dominating the trace view.
MAX_SPAN_ERROR_MSG = 500


def span_error_tags(ex: BaseException) -> dict[str, str]:
    """
    Build the tags describing `ex` for the root span of the trace it failed in.

    The root span is where the trace view and the APM error rate read their error from, but
    the exception itself was raised further down, so the root has to be told what happened.
    Reporting the real type and message keeps that honest: naming every failure
    `OperationalError` sent anyone reading a trace looking for a database fault, whatever had
    actually gone wrong.
    """
    message = str(ex) or ex.__class__.__name__
    if len(message) > MAX_SPAN_ERROR_MSG:
        message = f"{message[:MAX_SPAN_ERROR_MSG]}… (truncated)"
    return {
        ERROR_TYPE: ex.__class__.__name__,
        ERROR_MSG: message,
        REPORTED_ERROR_TAG: "true",
    }


@skip_if_no_metrics
def add_span_error(ex: BaseException) -> None:  # pragma: no cover
    if span := tracer.current_span():
        span.set_exc_info(ex.__class__, ex, getattr(ex, "__traceback__", None))

    if root := tracer.current_root_span():
        root.set_tags(span_error_tags(ex))
        root.error = 1


@skip_if_no_metrics
def setup_ignored_errors(span: Span) -> None:  # pragma: no cover
    span._ignore_exception(AdminOnlyError)  # noqa: SLF001
    span._ignore_exception(CommandOnCooldown)  # noqa: SLF001
    span._ignore_exception(GuildBannedError)  # noqa: SLF001
    span._ignore_exception(GuildOnlyError)  # noqa: SLF001
    span._ignore_exception(ModOnlyError)  # noqa: SLF001
    span._ignore_exception(UserBannedError)  # noqa: SLF001
