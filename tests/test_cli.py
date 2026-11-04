# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

from spellbot.cli import main
from spellbot.i18n import TRANSLATIONS_DIR
from spellbot.settings import settings
from tests.mocks.decoys import ANY

if TYPE_CHECKING:
    import pytest
    from click.testing import CliRunner
    from decoy import Decoy
    from syrupy.assertion import SnapshotAssertion

    from tests.fixtures import CliFakes


class TestCLI:
    def test_help(
        self,
        cli: CliFakes,
        runner: CliRunner,
        snapshot: SnapshotAssertion,
    ) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert result.output == snapshot
        assert cli.ran == []

    def test_run_api(self, cli: CliFakes, runner: CliRunner, decoy: Decoy) -> None:
        result = runner.invoke(main, ["--api"])
        assert result.exit_code == 0
        decoy.verify(cli.launch_dev_server(False, 404), times=1)

    def test_run_api_with_port(self, cli: CliFakes, runner: CliRunner, decoy: Decoy) -> None:
        result = runner.invoke(main, ["--api", "--port", "200"])
        assert result.exit_code == 0
        decoy.verify(cli.launch_dev_server(False, 200), times=1)

    def test_run_bot(self, cli: CliFakes, runner: CliRunner, decoy: Decoy) -> None:
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert result.output == ""
        decoy.verify(cli.start_reloader(ANY), times=0, ignore_extra_args=True)
        decoy.verify(cli.configure_logging("INFO"), times=1)
        decoy.verify(cli.build_bot(mock_games=False, disable_tasks=False), times=1)
        assert cli.ran == ["run_bot"]

    def test_run_bot_without_secret_token(
        self,
        cli: CliFakes,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        monkeypatch.setattr(settings, "SECRET_TOKEN", "")
        result = runner.invoke(main, [])
        assert result.exit_code == 1
        assert "missing required settings: SECRET_TOKEN" in result.output
        decoy.verify(cli.build_bot(), times=0, ignore_extra_args=True)
        assert cli.ran == []

    def test_run_bot_with_log_level(self, cli: CliFakes, runner: CliRunner, decoy: Decoy) -> None:
        runner.invoke(main, ["--log-level", "DEBUG"])
        decoy.verify(cli.configure_logging("DEBUG"), times=1)

    def test_run_bot_without_bot_token(
        self,
        cli: CliFakes,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        monkeypatch.setattr(settings, "BOT_TOKEN", None)
        result = runner.invoke(main, [])
        assert result.exit_code == 1
        assert result.output == ""
        decoy.verify(cli.start_reloader(ANY), times=0, ignore_extra_args=True)
        decoy.verify(cli.configure_logging("INFO"), times=1)
        decoy.verify(cli.build_bot(), times=0, ignore_extra_args=True)
        assert cli.ran == []

    def test_run_bot_with_mock_games(self, cli: CliFakes, runner: CliRunner, decoy: Decoy) -> None:
        runner.invoke(main, ["--mock-games"])
        decoy.verify(cli.build_bot(mock_games=True, disable_tasks=False), times=1)

    def test_run_bot_with_dev(self, cli: CliFakes, runner: CliRunner, decoy: Decoy) -> None:
        decoy.when(cli.start_reloader("spellbot.main")).then_return(cli.reloader)
        runner.invoke(main, ["--dev"])
        decoy.verify(cli.reloader.watch_files([str(TRANSLATIONS_DIR / "*.po*")]), times=1)
