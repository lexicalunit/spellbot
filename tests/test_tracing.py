from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from spellbot.tracing import configure_tracing, is_empty_resource


class TestIsEmptyResource:
    @pytest.mark.parametrize("resource", ["", " ", ";", " ; ", ";;", " ;\t; "])
    def test_empty_variants_are_dropped(self, resource: str) -> None:
        span = MagicMock(resource=resource)
        assert is_empty_resource(span) is True

    @pytest.mark.parametrize("resource", ["SELECT 1", "BEGIN", "SELECT 1;"])
    def test_meaningful_resources_are_kept(self, resource: str) -> None:
        span = MagicMock(resource=resource)
        assert is_empty_resource(span) is False

    def test_none_resource_is_dropped(self) -> None:
        span = MagicMock(resource=None)
        assert is_empty_resource(span) is True


class TestConfigureTracing:
    def test_registers_filter(self) -> None:
        with patch("ddtrace.trace.tracer") as mock_tracer:
            configure_tracing()
        mock_tracer.configure.assert_called_once()
        processors = mock_tracer.configure.call_args.kwargs["trace_processors"]
        assert len(processors) == 1

    def test_filter_drops_empty_resource_spans(self) -> None:
        with patch("ddtrace.trace.tracer") as mock_tracer:
            configure_tracing()
        processor = mock_tracer.configure.call_args.kwargs["trace_processors"][0]
        keep = MagicMock(resource="SELECT 1")
        drop = MagicMock(resource=";")
        assert processor.process_trace([keep, drop]) == [keep]

    def test_filter_returns_none_when_all_dropped(self) -> None:
        with patch("ddtrace.trace.tracer") as mock_tracer:
            configure_tracing()
        processor = mock_tracer.configure.call_args.kwargs["trace_processors"][0]
        drop = MagicMock(resource=";")
        assert processor.process_trace([drop]) is None
