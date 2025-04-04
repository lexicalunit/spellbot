from __future__ import annotations

import re
from functools import wraps
from typing import TYPE_CHECKING, Any

from datadog import initialize
from datadog.api.events import Event
from ddtrace.constants import ERROR_MSG, ERROR_TYPE
from ddtrace.trace import tracer
from wrapt import wrap_function_wrapper

from . import __version__
from .environment import running_in_pytest
from .errors import (
    AdminOnlyError,
    GuildBannedError,
    GuildOnlyError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from .settings import settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from ddtrace.trace import Span
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


@skip_if_no_metrics
def patch_discord() -> None:  # pragma: no cover
    interaction_callback = re.compile(r"/interactions/([0-9]+)/([^/]+)/callback")
    webhook_message = re.compile(r"/webhooks/([0-9]+)/([^/]+)/messages/@original")

    def request(  # pragma: no cover
        wrapped: Callable,  # type: ignore
        instance: Any,
        args: Any,
        kwargs: Any,
    ) -> Any:
        route: Route = args[0]
        path: str = route.path
        additional_tags = {}
        if matches := interaction_callback.match(path):
            resource = r"/interactions/{interaction_id}/{interaction_token}/callback"
            additional_tags["interaction_id"] = matches[1]
            additional_tags["interaction_token"] = matches[2]
        elif matches := webhook_message.match(path):
            resource = r"/webhooks/{application_id}/{interaction_token}/messages/@original"
            additional_tags["application_id"] = matches[1]
            additional_tags["interaction_token"] = matches[2]
        else:
            resource = path
        with tracer.trace(service="discord", name="http", resource=resource) as span:
            span.set_tags(
                {
                    "base": route.BASE,
                    "channel_xid": str(route.channel_id),
                    "data": kwargs,
                    "guild_xid": str(route.guild_id),
                    "instance": instance,
                    "method": route.method,
                    **additional_tags,
                },
            )
            return wrapped(*args, **kwargs)

    wrap_function_wrapper("discord.http", "HTTPClient.request", request)


@skip_if_no_metrics
def setup_metrics() -> None:  # pragma: no cover
    initialize(api_key=settings.DD_API_KEY, app_key=settings.DD_APP_KEY)
    patch_discord()


@skip_if_no_metrics
def alert_error(
    title: str,
    text: str = "",
    tags: list[str] | None = None,
) -> None:  # pragma: no cover
    tags = tags or []
    tags.append(f"version:{__version__}")
    Event.create(alert_type="error", title=title, text=text, tags=tags)


@skip_if_no_metrics
def add_span_context(interaction: Any) -> None:  # pragma: no cover
    if span := tracer.current_span():
        if interaction_id := getattr(interaction, "id", None):
            span.set_tag("interaction_id", interaction_id)
        if (user := getattr(interaction, "user", None)) and (user_id := getattr(user, "id", None)):
            span.set_tag("user_id", user_id)
        for prop in (
            "application_id",
            "channel_id",
            "component_id",
            "data",
            "guild_id",
        ):
            if value := getattr(interaction, prop, None):
                span.set_tag(prop, value)


@skip_if_no_metrics
def add_span_kv(key: str, value: Any) -> None:  # pragma: no cover
    if span := tracer.current_span():
        span.set_tag(key, value)


@skip_if_no_metrics
def add_span_error(ex: BaseException) -> None:  # pragma: no cover
    if span := tracer.current_span():
        span.set_exc_info(ex.__class__, ex, getattr(ex, "__traceback__", None))

    if root := tracer.current_root_span():
        root.set_tags(
            {
                ERROR_TYPE: "OperationalError",
                ERROR_MSG: "An error occurred during bot operation",
            },
        )
        root.error = 1


@skip_if_no_metrics
def setup_ignored_errors(span: Span) -> None:  # pragma: no cover
    span._ignore_exception(AdminOnlyError)  # noqa: SLF001
    span._ignore_exception(GuildOnlyError)  # noqa: SLF001
    span._ignore_exception(UserBannedError)  # noqa: SLF001
    span._ignore_exception(GuildBannedError)  # noqa: SLF001
    span._ignore_exception(UserUnverifiedError)  # noqa: SLF001
    span._ignore_exception(UserVerifiedError)  # noqa: SLF001
