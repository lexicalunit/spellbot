from __future__ import annotations

from typing import TYPE_CHECKING

from spellbot.cli import main

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from click.testing import CliRunner
    from syrupy.assertion import SnapshotAssertion


class TestCLI:
    def test_help(
        self,
        cli: MagicMock,
        runner: CliRunner,
        snapshot: SnapshotAssertion,
    ) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert result.output == snapshot
        cli.bot.run.assert_not_called()

    def test_run_api(
        self,
        cli: MagicMock,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(main, ["--api"])
        assert result.exit_code == 0
        cli.launch_web_server.assert_called_once_with(cli.loop, 404)
        cli.loop.run_forever.assert_called_once_with()

    def test_run_api_with_port(
        self,
        cli: MagicMock,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(main, ["--api", "--port", "200"])
        assert result.exit_code == 0
        cli.launch_web_server.assert_called_once_with(cli.loop, 200)
        cli.loop.run_forever.assert_called_once_with()

    def test_run_bot(
        self,
        cli: MagicMock,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert result.output == ""
        cli.hupper.start_reloader.assert_not_called()
        cli.configure_logging.assert_called_once_with("INFO")
        cli.build_bot.assert_called_once_with(mock_games=False)
        cli.bot.run.assert_called_once_with("facedeadbeef", log_handler=None)

    def test_run_bot_with_log_level(
        self,
        cli: MagicMock,
        runner: CliRunner,
    ) -> None:
        runner.invoke(main, ["--log-level", "DEBUG"])
        cli.configure_logging.assert_called_once_with("DEBUG")

    def test_run_bot_without_bot_token(
        self,
        cli: MagicMock,
        runner: CliRunner,
    ) -> None:
        cli.settings.BOT_TOKEN = None
        result = runner.invoke(main, [])
        assert result.exit_code == 1
        assert result.output == ""
        cli.hupper.start_reloader.assert_not_called()
        cli.configure_logging.assert_called_once_with("INFO")
        cli.build_bot.assert_not_called()
        cli.bot.run.assert_not_called()

    def test_run_bot_with_mock_games(self, cli: MagicMock, runner: CliRunner) -> None:
        runner.invoke(main, ["--mock-games"])
        cli.build_bot.assert_called_once_with(mock_games=True)

    def test_run_bot_with_dev(self, cli: MagicMock, runner: CliRunner) -> None:
        runner.invoke(main, ["--dev"])
        cli.hupper.start_reloader.assert_called_once_with("spellbot.main")
