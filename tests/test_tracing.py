# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import ddtrace.trace
import pytest
from ddtrace._trace.span import Span

from spellbot.tracing import configure_tracing, is_empty_resource

if TYPE_CHECKING:
    from ddtrace.trace import TraceFilter


def span(resource: str | None) -> Span:
    real = Span("test")
    # ddtrace types `resource` as `str`, but nothing stops it being `None` at runtime.
    real.resource = resource  # ty: ignore[invalid-assignment]
    return real


class FakeTracer:
    """Stands in for `ddtrace.trace.tracer`, which `configure()` force-enables like the real one."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.processors: list[TraceFilter] = []

    def configure(self, *, trace_processors: list[TraceFilter]) -> None:
        self.processors = trace_processors
        self.enabled = True


@pytest.fixture
def tracer(monkeypatch: pytest.MonkeyPatch) -> FakeTracer:
    fake = FakeTracer()
    monkeypatch.setattr(ddtrace.trace, "tracer", fake)
    return fake


class TestIsEmptyResource:
    @pytest.mark.parametrize("resource", ["", " ", ";", " ; ", ";;", " ;\t; "])
    def test_empty_variants_are_dropped(self, resource: str) -> None:
        assert is_empty_resource(span(resource)) is True

    @pytest.mark.parametrize("resource", ["SELECT 1", "BEGIN", "SELECT 1;"])
    def test_meaningful_resources_are_kept(self, resource: str) -> None:
        assert is_empty_resource(span(resource)) is False

    def test_none_resource_is_dropped(self) -> None:
        assert is_empty_resource(span(None)) is True


class TestConfigureTracing:
    def test_registers_filter(self, tracer: FakeTracer) -> None:
        configure_tracing()
        assert len(tracer.processors) == 1

    @pytest.mark.parametrize("enabled", [True, False])
    def test_preserves_enabled_state(self, tracer: FakeTracer, enabled: bool) -> None:
        tracer.enabled = enabled
        configure_tracing()
        assert tracer.enabled is enabled

    def test_filter_drops_empty_resource_spans(self, tracer: FakeTracer) -> None:
        configure_tracing()
        keep, drop = span("SELECT 1"), span(";")
        assert tracer.processors[0].process_trace([keep, drop]) == [keep]

    def test_filter_returns_none_when_all_dropped(self, tracer: FakeTracer) -> None:
        configure_tracing()
        assert tracer.processors[0].process_trace([span(";")]) is None
