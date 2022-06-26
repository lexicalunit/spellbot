from __future__ import annotations

from unittest.mock import ANY

from spellbot.cli import main


class TestCLI:
    def test_help(self, cli, runner, snapshot):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert result.output == snapshot
        cli.bot.run.assert_not_called()

    def test_run_api(self, cli, runner):
        result = runner.invoke(main, ["--api"])
        assert result.exit_code == 0
        cli.launch_web_server.assert_called_once_with(
            cli.settings,
            cli.loop,
            cli.settings.PORT,
        )
        cli.loop.run_forever.assert_called_once_with()

    def test_run_api_with_port(self, cli, runner):
        result = runner.invoke(main, ["--api", "--port", "200"])
        assert result.exit_code == 0
        cli.launch_web_server.assert_called_once_with(cli.settings, cli.loop, 200)
        cli.loop.run_forever.assert_called_once_with()

    def test_run_bot(self, cli, runner):
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert result.output == ""
        cli.hupper.start_reloader.assert_not_called()
        cli.configure_logging.assert_called_once_with("INFO")
        cli.build_bot.assert_called_once_with(
            clean_commands=False,
            force_sync_commands=False,
            loop=cli.loop,
            mock_games=False,
        )
        cli.bot.run.assert_called_once_with("facedeadbeef")

    def test_run_bot_with_log_level(self, cli, runner):
        runner.invoke(main, ["--log-level", "DEBUG"])
        cli.configure_logging.assert_called_once_with("DEBUG")

    def test_run_bot_without_bot_token(self, cli, runner):
        cli.settings.BOT_TOKEN = None
        result = runner.invoke(main, [])
        assert result.exit_code == 1
        assert result.output == ""
        cli.hupper.start_reloader.assert_not_called()
        cli.configure_logging.assert_called_once_with("INFO")
        cli.build_bot.assert_not_called()
        cli.bot.run.assert_not_called()

    def test_run_bot_with_clean_commands(self, cli, runner):
        runner.invoke(main, ["--clean-commands"])
        cli.build_bot.assert_called_once_with(
            clean_commands=True,
            force_sync_commands=ANY,
            loop=ANY,
            mock_games=ANY,
        )

    def test_run_bot_with_force_sync_commands(self, cli, runner):
        runner.invoke(main, ["--sync-commands"])
        cli.build_bot.assert_called_once_with(
            clean_commands=ANY,
            force_sync_commands=True,
            loop=ANY,
            mock_games=ANY,
        )

    def test_run_bot_with_mock_games(self, cli, runner):
        runner.invoke(main, ["--mock-games"])
        cli.build_bot.assert_called_once_with(
            clean_commands=ANY,
            force_sync_commands=ANY,
            loop=ANY,
            mock_games=True,
        )

    def test_run_bot_with_debug(self, cli, runner):
        runner.invoke(main, ["--debug"])
        cli.loop.set_debug.assert_called_once_with(True)

    def test_run_bot_with_dev(self, cli, runner):
        runner.invoke(main, ["--dev"])
        cli.hupper.start_reloader.assert_called_once_with("spellbot.main")
