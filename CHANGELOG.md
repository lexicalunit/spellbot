# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v17.1.2](https://github.com/lexicalunit/spellbot/releases/tag/v17.1.2) - 2025-11-18

### Fixed

- Fix issue with convoke password generation.

## [v17.1.1](https://github.com/lexicalunit/spellbot/releases/tag/v17.1.1) - 2025-11-18

### Fixed

- Fix issue with patreon sync.
- Fix issue with convoke game creation.

## [v17.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v17.1.0) - 2025-11-18

### Added

- Support for convoke.games!

## [v17.0.7](https://github.com/lexicalunit/spellbot/releases/tag/v17.0.7) - 2025-11-07

### Changed

- Change ecr retention, add a script to cleanup old images manually.

## [v17.0.6](https://github.com/lexicalunit/spellbot/releases/tag/v17.0.6) - 2025-11-07

### Changed

- Revert GunicornUVLoopWebWorker, go back to GunicornWebWorker for now.

## [v17.0.5](https://github.com/lexicalunit/spellbot/releases/tag/v17.0.5) - 2025-11-07

### Changed

- Updated dependencies.
- Added tf settings.

## [v17.0.4](https://github.com/lexicalunit/spellbot/releases/tag/v17.0.4) - 2025-11-06

### Added

- Support for connecting your Patreon account to SpellBot.

## [v17.0.3](https://github.com/lexicalunit/spellbot/releases/tag/v17.0.3) - 2025-10-09

### Changed

- Updated dependencies.
- Updated server list.

### Added

- Support for convoke.games (to be released soon).

## [v17.0.2](https://github.com/lexicalunit/spellbot/releases/tag/v17.0.2) - 2025-09-24

### Fixed

- Fixed a typo in the output of `/award add` which said that `/set awards` is a command.

### Changed

- Refactored code to workaround a bug with `ddtrace.wrap()` and `discord.Role` arguments.
- Updated code formatting to use COM812. This might cause issues in the future. Fingers crossed.
- Updates to SERVICES.md documentation.
- Updated codebase tests to check for future annotations in cog files.

## [v17.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v17.0.1) - 2025-09-23

### Fixed

- Fixed an issue where the join/leave buttons were not removed from started games.

### Changed

- Refactored game embed generated code.

## [v17.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v17.0.0) - 2025-09-23

### Fixed

- Fixed an issue with `/score` causing a 500 http error due to locales.

### Changed

- Added icons to bracket levels.
- Updated dependencies.

### Removed

- Removed unused code related to game points, score, and elo.

## [v16.4.0](https://github.com/lexicalunit/spellbot/releases/tag/v16.4.0) - 2025-09-21

### Changed

- Upgrade to python 3.13.
- Updated dependencies.
- Removed maximum versions for dependencies (rely on uv.lock instead).

## [v16.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v16.3.0) - 2025-09-21

### Added

- Added a SERVICES.md document to explain how to add support for a new game service.

### Fixed

- Fixed the .env.example file (incorrect variable names).
- Fixed the DOCKER.md documentation since splitting up the bot and API.
- Added a try .. finally to `db_session_manager()` to ensure we always end the session.
- Fixed a bug with TableStream game creation not using the correct auth token.

### Changed

- Changed the spelltable_link column to game_link, since it's not just for SpellTable.
- Using GunicornUVLoopWebWorker workers for the API now.
- Replaced deprecated `uvloop.install()` with a `asyncio.set_event_loop_policy()` call.
- Refactored `create_game_link()` for clarity.
- Refactored tablestream.py to remove aiohttp in favor of httpx.
- Updated dependencies.

### Deleted

- Removed old legacy scripts from database upgrade.
- Removed `ENABLE_SPELLTABLE` flag since it's no longer used.
- Deleted code related to spectator links since the feature is no longer supported.
- Removed dependency on aiohttp-retry.

## [v16.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v16.2.0) - 2025-09-17

### Fixed

- Fixed build exclusions.

## [v16.1.8](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.8) - 2025-09-16

### Changed

- Handle multiple bots running with some grace.
- Added a monitor for ecs running task desire count.

## [v16.1.7](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.7) - 2025-09-16

### Changed

- Ensure that the tag "env" is always set for logs.
- Terraform updates for monitors and infra resources.

## [v16.1.6](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.6) - 2025-09-16

### Changed

- Lower CloudWatch retention to reduce costs.
- Update dependencies.
- Use basic logging for development mode.

## [v16.1.5](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.5) - 2025-09-14

### Changed

- Better logging and tracing for spellbot rest api.

## [v16.1.4](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.4) - 2025-09-12

### Changed

- Tweaking some code to reduce the number of no-op database queries.

## [v16.1.3](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.3) - 2025-09-12

### Changed

- Add the status attribute to logs so the show up nicely in datadog.

## [v16.1.2](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.2) - 2025-09-10

### Changed

- Use redis for bad user cache since uptime is much longer on AWS.

## [v16.1.1](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.1) - 2025-09-08

### Changed

- Reduce the number of retries and sleeping between them for SpellTable.

## [v16.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v16.1.0) - 2025-09-08

### Changed

- Changed to JSON logging.
- Switch to alpine based docker image.

## [v16.0.4](https://github.com/lexicalunit/spellbot/releases/tag/v16.0.4) - 2025-09-07

### Fixed

- Workaround a weird issue with pylic that is blocking CI.

## [v16.0.3](https://github.com/lexicalunit/spellbot/releases/tag/v16.0.3) - 2025-09-07

### Fixed

- Fixed a build issue related to licenses configuration.

## [v16.0.2](https://github.com/lexicalunit/spellbot/releases/tag/v16.0.2) - 2025-09-07

### Fixed

- Fixed a typo in the last patch.

## [v16.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v16.0.1) - 2025-09-07

### Changed

- Added link service to the game creation trace.

## [v16.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v16.0.0) - 2025-09-07

### Changed

- Deployment changed to AWS.
- Removed dependency on headless chrome for SpellTable game creation.

### Fixed

- Fixes a potential issue with rate limiting.

## [v15.6.6](https://github.com/lexicalunit/spellbot/releases/tag/v15.6.6) - 2025-08-24

### Changed

- Changed an error log to a warning log.

## [v15.6.5](https://github.com/lexicalunit/spellbot/releases/tag/v15.6.5) - 2025-08-20

### Changed

- Updated ddtrace.

## [v15.6.4](https://github.com/lexicalunit/spellbot/releases/tag/v15.6.4) - 2025-08-20

### Changed

- Much faster SpellTable game creation using cached page states and browser.
- Updated all dependencies, including an update to discord.py v2.6.0.

## [v15.6.3](https://github.com/lexicalunit/spellbot/releases/tag/v15.6.3) - 2025-08-19

### Changed

- Slightly longer timeout for SpellTable game creation.

## [v15.6.2](https://github.com/lexicalunit/spellbot/releases/tag/v15.6.2) - 2025-08-19

### Fixed

- Fixes for the CLI test suite.

## [v15.6.1](https://github.com/lexicalunit/spellbot/releases/tag/v15.6.1) - 2025-08-19

### Added

- Support for interactive chrome headless mode.

### Fixed

- Click the "Authorize" button when creating a SpellTable game.

## [v15.6.0](https://github.com/lexicalunit/spellbot/releases/tag/v15.6.0) - 2025-08-12

### Added

- Adds support for blind games: Player names are hidden; blocked players are still respected.

## [v15.3.1](https://github.com/lexicalunit/spellbot/releases/tag/v15.3.1) - 2025-08-04

### Changed

- Updates to all dependencies.
- Ensure that we accept the privacy policy when creating SpellTable games.
- More robust click handling for Create Game button.

## [v15.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v15.3.0) - 2025-07-02

### Added

- Adds the `rules:` option to `/lfg` which lets users stipulate additional rules for their game.

## [v15.2.1](https://github.com/lexicalunit/spellbot/releases/tag/v15.2.1) - 2025-07-02

### Fixed

- Case insensitive suggested voice channel category prefix comparison.

## [v15.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v15.2.0) - 2025-07-02

### Added

- Adds the ability to configure the "suggested voice channels" feature for your guild.
- Adds the `/set suggest_vc_category` command to set the category prefix for suggestions.
  - If the suggested vc category is set, that will toggle ON the suggestion feature.
  - If the suggested vc category is unset (set to ""), that will toggle OFF the feature.

## [v15.1.1](https://github.com/lexicalunit/spellbot/releases/tag/v15.1.1) - 2025-05-25

### Fixed

- Fixes a bug related to games and created_at/updated_at times.

## [v15.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v15.1.0) - 2025-05-23

### Changed

- Update dependencies including an update to use psycopg version 3.

## [v15.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v15.0.1) - 2025-05-16

### Changed

- Only install Chromium deps for playwright.

## [v15.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v15.0.0) - 2025-05-16

### Changed

- Migrate from poetry to uv.
- Updated all dependencies.

## [v14.10.2](https://github.com/lexicalunit/spellbot/releases/tag/v14.10.2) - 2025-03-26

### Changed

- Updated all dependencies.

## [v14.10.1](https://github.com/lexicalunit/spellbot/releases/tag/v14.10.1) - 2025-03-19

### Changed

- Made `/rematch` work across channels in a guild.

## [v14.10.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.10.0) - 2025-03-09

### Added

- Added a `/rematch` command to create a new game with the same players.

## [v14.9.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.9.0) - 2025-03-02

### Added

- Notification support for when players track their games on Mythic Track.

## [v14.8.4](https://github.com/lexicalunit/spellbot/releases/tag/v14.8.4) - 2025-02-15

### Added

- Some tracking on when a user verifies their play pin.

## [v14.8.2](https://github.com/lexicalunit/spellbot/releases/tag/v14.8.2) - 2025-02-13

### Changed

- More color logos for various yearly events.
- Optimization: Check for rate limit when creating SpellTable games.
- Updated grafana snapshot.

## [v14.8.1](https://github.com/lexicalunit/spellbot/releases/tag/v14.8.1) - 2025-02-12

### Changed

- Reordered the options for `/lfg` to make brackets easier to get to by keyboard.

## [v14.8.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.8.0) - 2025-02-12

### Added

- Adds support to manually set the SpellTable format when creating the game.

## [v14.7.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.7.0) - 2025-02-12

### Added

- Adds setup command and documentation for Mythic Track integration.

## [v14.6.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.6.0) - 2025-02-11

### Added

- Adds support for the Commander Bracket system.

## [v14.5.1](https://github.com/lexicalunit/spellbot/releases/tag/v14.5.1) - 2025-02-02

### Fixed

- Fixed an issue with suggested voice channels not being the same per player.

### Changed

- Updated dependencies.

## [v14.5.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.5.0) - 2025-02-01

### Fixed

- Fixed SpellTable link generation by using an approach developed by @nathvnt (https://github.com/nathvnt). Thanks Nathan, you rock!

### Added

- Adds support for PIN code on game plays.
- Adds support for external app integrations.
- Adds REST API for verifying PIN codes.
- Adds support MythicTrack link and surfacing PIN to players.

## [v14.4.1](https://github.com/lexicalunit/spellbot/releases/tag/v14.4.1) - 2025-01-01

### Fixed

- Only suggest a vc if the game has started.

## [v14.4.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.4.0) - 2025-01-01

### Added

- Adds an field to embeds for the suggested voice channel.

## [v14.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.3.0) - 2025-01-01

### Changed

- Send user DMs in parallel to speed up things when a pod fires.

## [v14.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.2.0) - 2025-01-01

### Added

- Adds a feature to suggest voice channels (not configurable, beta only).

## [v14.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.1.0) - 2024-12-29

### Changed

- Updated dependencies.
- Factored game link details into a dataclass.
- Reintroduced guild specific critical section locks (rather than a global lock).

## [v14.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v14.0.0) - 2024-12-22

### Changed

- Updated dependencies.
- Delete the pending game when the last player leaves it.
- Cleaned up some code by reducing the number of cogs.

### Removed

- Removes the unfinished ELO and points confirmation code. This can be reintroduced in the future
  but it needs to be fully overhauled from its current state.

## [v13.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v13.0.1) - 2024-12-15

### Changed

- Changed twitter links to bluesky in readme.
- Updated dependencies.
- Comment out unreachable code for now, pending refactor of points/ELO

### Added

- Adds pytest-socket
- Adds coverage for `create_game_link`
- Adds coverage for voice channel creation helper function
- Adds coverage for table stream game objects

### Fixed

- Fixes typo in name of operation `safe_create_channel_invite`
- Fixes typo in the name of file `test_lfg_action.py`

## [v13.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v13.0.0) - 2024-11-30

### Added

- Adds support for Table Stream.

### Changed

- Updated all dependencies.

## [v12.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v12.0.0) - 2024-11-17

### Removed

- Removes mirrors.
- Disables ELO system until I can go back and rework it. Right now it is not ready to be used.

## [v11.6.2](https://github.com/lexicalunit/spellbot/releases/tag/v11.6.2) - 2024-11-17

### Added

- Adds some DB indexes to help with performance of some queries.

## [v11.6.1](https://github.com/lexicalunit/spellbot/releases/tag/v11.6.1) - 2024-11-17

### Added

- Adds some defensive code to the "I found a game for you" code for when Discord is having issues.

## [v11.6.0](https://github.com/lexicalunit/spellbot/releases/tag/v11.6.0) - 2024-10-28

### Added

- Adds a documentation description for the game service option in `/lfg`.
- Adds the Pauper EDH format -- Thanks @camclark!

## [v11.5.2](https://github.com/lexicalunit/spellbot/releases/tag/v11.5.2) - 2024-10-21

### Added

- Begins to build out support for table-stream.com.

### Fixed

- Fixes the `service` option in the `/lfg` command, which broke in v11.5.0.

## [v11.5.1](https://github.com/lexicalunit/spellbot/releases/tag/v11.5.1) - 2024-10-17

### Added

- Adds the Archenemy format.
- Adds ordering config for game services.

### Changed

- Use the GameFormat repr for game format name in embeds.

## [v11.5.0](https://github.com/lexicalunit/spellbot/releases/tag/v11.5.0) - 2024-10-16

### Changed

- Updated python dependencies.
- Adds cEDH format to the list of formats.
- Reorder the format list and customize the format titles better.

## [v11.4.1](https://github.com/lexicalunit/spellbot/releases/tag/v11.4.1) - 2024-10-03

### Added

- Added the Duel Commander format.

## [v11.4.0](https://github.com/lexicalunit/spellbot/releases/tag/v11.4.0) - 2024-09-29

### Added

- Added support for higher quality audio voice channels.

## [v11.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v11.3.0) - 2024-08-07

### Added

- Added the oathbreaker format.

## [v11.2.3](https://github.com/lexicalunit/spellbot/releases/tag/v11.2.3) - 2024-07-07

### Fixed

- Fixes the embed description for non-spelltable games to not mention spelltable.

## [v11.2.2](https://github.com/lexicalunit/spellbot/releases/tag/v11.2.2) - 2024-07-04

### Fixed

- Fixes an issue with improper permissions when creating a game embed.

## [v11.2.1](https://github.com/lexicalunit/spellbot/releases/tag/v11.2.1) - 2024-06-24

### Changed

- Updated python dependencies.

## [v11.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v11.2.0) - 2024-06-10

### Added

- Added a small call for support with links to patreon and ko-fi.

## [v11.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v11.1.0) - 2024-06-09

### Added

- Support for general notices.

### Changed

- Updated python dependencies.

## [v11.0.4](https://github.com/lexicalunit/spellbot/releases/tag/v11.0.4) - 2024-05-16

### Changed

- Updated python dependencies.
- More test coverage.

## [v11.0.3](https://github.com/lexicalunit/spellbot/releases/tag/v11.0.3) - 2024-05-08

### Fixed

- Fixed a typo in operations log for the defer operation.

### Changed

- Publish platform linux/amd64.
- Reduce complexity of Dockerfile.
- Reduce proliferation of Settings objects.
- Use __slots__ in some classes to reduce memory usage.

## [v11.0.2](https://github.com/lexicalunit/spellbot/releases/tag/v11.0.2) - 2024-05-02

### Added

- Interactive developer shell with database access.
- Adds cached user name to `/blocked` list.

## [v11.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v11.0.1) - 2024-04-30

### Added

- Improved test coverage.
- cEDH UK.
- Turbo Commander.
- Comunidad Española de cEDH.

### Removed

- Removed Playing with Power logo.

### Changed

- Updated grafana dashboard.
- Updated python dependencies.

### Fixed

- Fixed an issue with DB sessions in test code.
- Added permissions check for fetching channels.

## [v11.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v11.0.0) - 2024-04-11

### Changed

- Upgrade to python 3.12.

## [v10.3.7](https://github.com/lexicalunit/spellbot/releases/tag/v10.3.7) - 2024-04-04

### Added

- Trans Rights.
- MTG@Home server.
- Ban guild commands.

### Changed

- Updated servers list.
- Updated servers logos.
- Updated website CSS.

## [v10.3.6](https://github.com/lexicalunit/spellbot/releases/tag/v10.3.6) - 2024-04-03

### Fixed

- Database session management within the test suite.

### Added

- A script to automatically update server lists in README.md and docs/index.html.
- Special call outs for supporting servers.

### Changed

- Updates cEDH logo and link.
- Updated the screenshot in the README.md and docs/index.html files.
- Updated the list of servers.
- Updated the grafana snapshot.

## [v10.3.5](https://github.com/lexicalunit/spellbot/releases/tag/v10.3.5) - 2024-04-02

### Fixed

- Fixes the jump link for watched user notifications.

## [v10.3.4](https://github.com/lexicalunit/spellbot/releases/tag/v10.3.4) - 2024-04-02

### Changed

- 2 hour invite expiry for cross queue.

### Added

- More test coverage.

## [v10.3.3](https://github.com/lexicalunit/spellbot/releases/tag/v10.3.3) - 2024-04-01

### Fixed

- Fixes the jump link for cross-queue games.

## [v10.3.2](https://github.com/lexicalunit/spellbot/releases/tag/v10.3.2) - 2024-04-01

### Fixed

- Fixes `/lfg` in cross-queue channels so that it sees games created in the other channel.

## [v10.3.1](https://github.com/lexicalunit/spellbot/releases/tag/v10.3.1) - 2024-03-30

### Changed

- For channels with show_points and require_confirmation set to True, use win/loss/tie ranking.

### Fixed

- Fixes check for when a user can run the `/confirm` command.
- The reporting commands now properly update game posts.
- Don't ask players to confirm their game if it's already confirmed.

## [v10.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v10.3.0) - 2024-03-30

### Added

- More debugging and logging around the cross-queue feature.
- ELO support.

### Changed

- Add the game format to the "found you a game" embed posts.

## [v10.2.1](https://github.com/lexicalunit/spellbot/releases/tag/v10.2.1) - 2024-03-24

### Fixed

- Fixed issue with SpellBot sending messages to users when they leave games.

### Changed

- Updated logo for command the cause.

## [v10.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v10.2.0) - 2024-03-22

### Fixed

- Fixed some issues with permissions handling.
- Much improved test coverage.

### Changed

- Updated dependencies.
- Global async lock on all activities that can cause users to join/leave games.
- Users can queue in multiple guilds at the same time now.
- Show Game ID in watched user notifications.

### Added

- Allow mods to set/confirm points for players for games.
- `/set voice_invite` in a channel to turn on/off creation of temp voice channel invites.
- Ability to mirror or link two channels, even on different guilds, together for cross-queue.
- An owner command to configure mirror settings.

## [v10.1.3](https://github.com/lexicalunit/spellbot/releases/tag/v10.1.3) - 2024-03-16

### Added

- Allow mods to set/confirm points for players for games.

## [v10.1.2](https://github.com/lexicalunit/spellbot/releases/tag/v10.1.2) - 2024-03-16

### Added

- Prevent users from joining a new game if reporting is still pending for their last game.
- Don't let users change their points after someone has confirmed them.
- Don't let users re-confirm something they've already confirmed.

## [v10.1.1](https://github.com/lexicalunit/spellbot/releases/tag/v10.1.1) - 2024-03-16

### Fixed

- Fixed parameter name for the `/set default_service` command.

## [v10.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v10.1.0) - 2024-03-15

### Added

- Adds ability to select service for game creation (SpellTable, MTG Arena, etc...)

## [v10.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v10.0.0) - 2024-03-10

### Changed

- Updated dependencies.

### Removed

- Removed power level per player settings.

### Added

- Initial beta support for ELO ratings.

## [v9.7.0](https://github.com/lexicalunit/spellbot/releases/tag/v9.7.0) - 2024-02-02

### Changed

- Changed some logging around expiring games.
- Always delete empty pending games when expiring them.

## [v9.6.0](https://github.com/lexicalunit/spellbot/releases/tag/v9.6.0) - 2024-01-30

### Added

- Added the pre cons format.
- Added some more DD metrics collection around expiring games.

## [v9.5.0](https://github.com/lexicalunit/spellbot/releases/tag/v9.5.0) - 2024-01-26

### Added

- Adds an Updated At field to pending games.
- Sets the embed color to gray, purple, and gold, depending on the game state.

## [v9.4.10](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.10) - 2024-01-23

### Changed

- Whenever the pending game clean task runs, also cleanup empty pending games.

## [v9.4.9](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.9) - 2024-01-15

### Added

- Added the planechase format.

## [v9.4.8](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.8) - 2024-01-14

### Changed

- Updated dependencies.
- Bug fix: Don't show join/leave buttons on games that have already started.

## [v9.4.7](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.7) - 2024-01-03

### Changed

- No changes.

## [v9.4.6](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.6) - 2024-01-03

### Changed

- Show player names on multiple lines.

## [v9.4.5](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.5) - 2024-01-01

### Added

- Adds player name in addition to player handle to game embed.
- Various dependency version updates.

## [v9.4.4](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.4) - 2023-12-11

### Added

- Adds CombatStep discord.
- Adds a manage_messages permission check to safe_delete_message.

## [v9.4.3](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.3) - 2023-11-26

### Changed

- Updates how user vs member is handled in application commands to avoid potential issue.

## [v9.4.2](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.2) - 2023-11-24

### Changed

- Dependency updates.

## [v9.4.1](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.1) - 2023-11-02

- Handle case when a user has no blocked users and runs the `/blocked` command.
- Update dev dependencies.
- Replace black with ruff format.

## [v9.4.0](https://github.com/lexicalunit/spellbot/releases/tag/v9.4.0) - 2023-10-17

### Added

- Adds the `/default_format` command.
- Adds the `/blocked` command.

## [v9.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v9.3.0) - 2023-10-04

### Added

- Added some auditing to plays and blocks.

## [v9.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v9.2.0) - 2023-09-17

### Added

- A `/move_user` command.

## [v9.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v9.1.0) - 2023-09-04

### Added

- Support for a `/set channel_extra` command that adds extra message to game posts.

## [v9.0.5](https://github.com/lexicalunit/spellbot/releases/tag/v9.0.5) - 2023-09-03

### Changed

- Dependency updates.

### Fixed

- Small fix to user `is_waiting` to avoid possible race condition.

## [v9.0.4](https://github.com/lexicalunit/spellbot/releases/tag/v9.0.4) - 2023-08-10

### Changed

- Dependency updates.

## [v9.0.3](https://github.com/lexicalunit/spellbot/releases/tag/v9.0.3) - 2023-08-03

### Changed

- Dependency updates.
- Changes how leave game action works a bit to be more robust and use less queries.

## [v9.0.2](https://github.com/lexicalunit/spellbot/releases/tag/v9.0.2) - 2023-07-19

### Fixed

- Fixes another bug in a multi-queue related query.

## [v9.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v9.0.1) - 2023-07-19

### Fixed

- Fixes a bug in a multi-queue related query.

## [v9.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v9.0.0) - 2023-07-19

### Added

- Support for queueing in up to five pending games at a time.

## [v8.11.13](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.13) - 2023-07-06

### Fixed

- Fixed the timeout length for `wait_until_ready()`, this was broken in v8.11.12.

## [v8.11.12](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.12) - 2023-07-06

### Added

- Less hacky solution for cancelling unfinished tasks in `wait_until_ready()`.

## [v8.11.11](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.11) - 2023-07-06

### Changed

- Disable debug logging for discord.state, it's too spammy.

## [v8.11.10](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.10) - 2023-07-06

### Added

- Proper handling for cancelling ready and resumed events.
- Debug logging for discord.state.
- Logging for when shards are ready.

## [v8.11.9](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.9) - 2023-07-06

### Added

- More defensive code around `permissions_for()` calls.

## [v8.11.8](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.8) - 2023-07-06

### Added

- Adds a workaround for client never getting the ready event and tasks not starting.

## [v8.11.7](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.7) - 2023-07-04

### Added

- Catch IndexErrors in admin pagination commands.
- Small tweak to SpellTable API interface to handle upstream timeout errors.

## [v8.11.6](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.6) - 2023-06-12

### Changed

- Updated all dependencies.

## [v8.11.5](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.5) - 2023-06-04

### Added

- More pride.

## [v8.11.4](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.4) - 2023-06-01

### Added

- More robust defensive coding around the leave button action.

## [v8.11.3](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.3) - 2023-05-26

### Added

- Check "manage_channels" permissions check before creating category channel.

## [v8.11.2](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.2) - 2023-05-19

### Added

- Added logic to guard against `interaction.original_message()` failures.

## [v8.11.1](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.1) - 2023-05-19

### Added

- Retry logic to all discord operations to combat ClientOSError issues.

## [v8.11.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.11.0) - 2023-04-26

### Removed

- Removed the creation of voice channel invite links since those now open in
  a browser rather than directly in the app.

### Changed

- Applied more linting and formatting rules from ruff.

### Added

- Automatically clean deleted channels when running the /channels command.

## [v8.10.1](https://github.com/lexicalunit/spellbot/releases/tag/v8.10.1) - 2023-04-19

### Fixed

- Fixed issue with command description length being over 100 characters.

## [v8.10.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.10.0) - 2023-04-19

### Added

- Adds support for placeholders in MOTD messages.

## [v8.9.4](https://github.com/lexicalunit/spellbot/releases/tag/v8.9.4) - 2023-04-19

### Changed

- More robust logic for role hierarchy comparison.

## [v8.9.3](https://github.com/lexicalunit/spellbot/releases/tag/v8.9.3) - 2023-04-19

### Changed

- Updated all dependencies.

## [v8.9.1](https://github.com/lexicalunit/spellbot/releases/tag/v8.9.1) - 2023-04-18

### Added

- Checks role hierarchy before attempting to manage roles.

## [v8.9.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.9.0) - 2023-02-02

### Added

- Adds an optional `ago` parameter to the `/top` command.

## [v8.8.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.8.0) - 2023-01-01

### Added

- Adds a `/top` command that gives you a top 10 list of players in a channel.

### Changed

- Updated all dependencies.

## [v8.7.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.7.0) - 2022-12-24

### Added

- Adds a detector for Discord message deletion, which is handled if it's a game.

## [v8.6.1](https://github.com/lexicalunit/spellbot/releases/tag/v8.6.1) - 2022-12-23

### Changed

- Update to discord.py v2.1.

## [v8.6.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.6.0) - 2022-12-23

### Added

- Adds admin command `/forget_channel` to forget about deleted channels.

### Changed

- Changed `/channels` to list the Discord Channel IDs for channels listed.
  These IDs can be used in the `/forget_channel` command to forget settings
  for a channel. For example if the channel has been deleted.
- Adds dependency on certifi rather directly (rather than thru requests).
- Fixed a number of pylint reported issues.
- Updates packaging and pylint versions.
- Mark pylint codebase test as skipped rather than commenting it out.

## [v8.5.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.5.0) - 2022-12-06

### Changed

- More detailed logs in send user error handling.
- Added the `!naughty` command for owners.

## [v8.4.1](https://github.com/lexicalunit/spellbot/releases/tag/v8.4.1) - 2022-12-02

### Changed

- Updated dependencies.

### Removed

- Removed isort and replaced with ruff.
- Removed passing of `loop` into SpellBot, discord.py ignores it anyway.
- Applied ruff import sorting to all files.

## [v8.4.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.4.0) - 2022-12-01

### Changed

- Changes from Bot to AutoShardedBot.

### Added

- Adds owner command: !stats.
- Added a process killer that check for bot readiness every 30 minutes.

## [v8.3.9](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.9) - 2022-11-25

### Fixed

- Fixed a bug in moderation role detection.

## [v8.3.8](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.8) - 2022-11-25

### Fixed

- Fixed a bug in metrics handling.

## [v8.3.7](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.7) - 2022-11-25

### Changed

- Log role name if not able to give a role because user is unknown.
- Fixed span context from interaction for discord.py 2.0.

## [v8.3.6](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.6) - 2022-11-25

### Changed

- Rename battle cruiser to one word.
- Cleaned up some code in reply/followup/send code in LFG action.
- Log unknown channel/message as warnings.

## [v8.3.5](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.5) - 2022-11-21

### Changed

- Changed how the bot and api are started by the supervisord process to avoid ddtrace errors.

## [v8.3.4](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.4) - 2022-11-20

### Added

- Adds EDH bc, low, mid, high, and max formats to /lfg format list.

## [v8.3.3](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.3) - 2022-11-16

### Added

- Adds a log for ready signal to help debug https://github.com/Rapptz/discord.py/issues/9074.

## [v8.3.2](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.2) - 2022-11-16

### Added

- Adds the ability to have multiple guild awards with the same count number. Each award with the same count number that applies to a player will be granted when they reach that play count.

### Changed

- Updated dependencies.
- Removed flake8 in favor of ruff, which is a lot faster.

## [v8.3.1](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.1) - 2022-11-02

### Fixed

- Fixed a bug in the last migration script.

## [v8.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.3.0) - 2022-11-02

### Fixed

- Fixed issue where sometimes points dropdown was shown even if "Show Points" if off.

### Changed

- Moved the "Show Points" setting to a per-channel config rather than per guild.

## [v8.2.3](https://github.com/lexicalunit/spellbot/releases/tag/v8.2.3) - 2022-10-28

### Fixed

- Workaround annoying datadog statsd errors at every startup.

## [v8.2.2](https://github.com/lexicalunit/spellbot/releases/tag/v8.2.2) - 2022-10-17

### Added

- Allow removal of users from the watch list by mention _or_ ID.

## [v8.2.1](https://github.com/lexicalunit/spellbot/releases/tag/v8.2.1) - 2022-10-16

### Fixed

- Fixes a bug in the new award logic.

## [v8.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.2.0) - 2022-10-16

### Added

- Allow guild awards to be verified or unverifed only.

## [v8.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.1.0) - 2022-10-15

### Added

- Adds the `/set delete_expired setting:[True|False]` channel setting.

## [v8.0.2](https://github.com/lexicalunit/spellbot/releases/tag/v8.0.2) - 2022-09-07

### Changed

- Custom "guild-only" handling for application commands.

## [v8.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v8.0.1) - 2022-08-19

### Fixed

- Removes support for Discord API proxy.
- Fixes toggle for show points setting.
- Fixes issue of views not being properly cleared on game posts.
- Fixes issue with expiring games.
- Fixes issue with interaction in `/game` command.
- Fixes bug in `upsert_request_objects()` when processing non-guild interactions.
- Fixes bug with permissions calculation due to discord.py patch.

## [v8.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v8.0.0) - 2022-07-28

### Changed

- Adds favicon to bot.spellbot.io.
- Bumps dependencies.
- Using discord.py 2.0 latest alpha release.

## [v7.12.5](https://github.com/lexicalunit/spellbot/releases/tag/v7.12.5) - 2022-06-19

### Changed

- Adds 1 second delay between voice channel deletion.

## [v7.12.4](https://github.com/lexicalunit/spellbot/releases/tag/v7.12.4) - 2022-03-05

### Changed

- Refactoring how user blocks work to ensure no one is placed in a game with someone they've blocked.

## [v7.12.3](https://github.com/lexicalunit/spellbot/releases/tag/v7.12.3) - 2022-02-22

### Changed

- Do not treat user errors as error traces in datadog.

## [v7.12.2](https://github.com/lexicalunit/spellbot/releases/tag/v7.12.2) - 2022-02-20

### Fixed

- Ensure that plays counts for awards are only counted on a per-server basis.

### Changed

- Updated outdated dependencies.
- Do not send exception metrics about user errors.

## [v7.12.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.12.1) - 2022-02-15

### Fixed

- Don't attempt to assign the `@everyone` role.

## [v7.12.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.12.0) - 2022-01-24

### Changed

- Adds workaround for recurring Discord rate limit issue.
- This issue seems to occur when /lfg, join, and leave commands take longer than expected.
- As such, always defer /lfg, join, and leave. This should allow more flexibility.
- However, this has the following knock-on consequences:
- Can't use hidden messages in /lfg.
- Many errors are now reported by sending a message to the user instead of to the channel.
- Until it can be fixed later, error reporting on role and DM failures is disabled.

## [v7.11.6](https://github.com/lexicalunit/spellbot/releases/tag/v7.11.6) - 2022-01-12

### Added

- More gay.

## [v7.11.5](https://github.com/lexicalunit/spellbot/releases/tag/v7.11.5) - 2022-01-10

### Fixed

- Ensure that `suppress` only pushes error metrics when an error is captured.

## [v7.11.4](https://github.com/lexicalunit/spellbot/releases/tag/v7.11.4) - 2022-01-10

### Changed

- Workaround slow interaction responses for `/lfg` command by posting game without buttons.

## [v7.11.3](https://github.com/lexicalunit/spellbot/releases/tag/v7.11.3) - 2022-01-10

### Fixed

- Fixes a massive performance issue when users `/lfg` with a friends list.

### Added

- Added root error status when an exception is suppressed in a Discord operation.
- Adds a fallback notification when we have an interaction failure.

## [v7.11.2](https://github.com/lexicalunit/spellbot/releases/tag/v7.11.2) - 2022-01-10

### Fixed

- Make metrics code a bit more robust in the face of errors.

## [v7.11.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.11.1) - 2022-01-09

### Fixed

- Ensures that users who have blocked each other can not be added to a game via friends.

## [v7.11.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.11.0) - 2021-12-31

### Added

- Allow "award" level to __remove__ a role, rather than give a role to a player.

## [v7.10.11](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.11) - 2021-12-30

### Added

- Puts discord request metrics into their own service.
- Add HTTP request path to resource name in dd trace for discord spans.
- Capture DD_TRACE_ENABLED env var in settings an use to turn metrics on/off.

## [v7.10.10](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.10) - 2021-12-27

### Added

- Adds metrics patch for discord.py's HTTP requests.

## [v7.10.9](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.9) - 2021-12-27

### Added

- Flag users as bad if we get a 403 when trying to send a DM to them.
- Adds a lot more tracer tags for Discord operation functions.

## [v7.10.8](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.8) - 2021-12-27

### Changed

- Adds error info on the root span when an error happens in a child span.

### Added

- Adds a test to ensure we use non-relative imports in spellbot package.

## [v7.10.7](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.7) - 2021-12-21

### Changed

- Adds errors to tracer spans rather than using alerting events.

### Fixed

- Don't run verification on messages from SpellBot itself.
- Added some missing awaits in `ctx.defer(ignore=True)` calls in error handling code.

## [v7.10.6](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.6) - 2021-12-16

### Changed

- Leave button only works if you click it for the game you're in.
- The `/leave` command works globally to remove you from any game you're in.

## [v7.10.5](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.5) - 2021-12-15

### Changed

- Group datadog traces under an "interaction" operation and include on_message with commands.
- Add span context to each trace based on the discord interaction or message context.
- Attempt to shrink the docker container image size a bit.
- Break out the leave button and leave command traces.
- Avoid API calls to fetch messages by using `discord.PartialMessage`.
- Added detailed trace metrics for operations, lfg cog, and leave cog.

## [v7.10.4](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.4) - 2021-12-12

### Changed

- Group datadog traces under a "command" operation with multiple resources.
- Add datadog tracing to spellapi deployment.

## [v7.10.3](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.3) - 2021-12-11

### Fixed

- Fixes broken tasks cog.

## [v7.10.2](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.2) - 2021-12-11

### Changed

- Adds SpellBot version via DD_VERSION if metrics are configured.
- Use DD_SERVICE to identify the service name (spellbot or spellapi).
- Use DD_HOSTNAME to identify the DYNO (or localhost in development mode).

### Fixed

- Fixes a typo in the Dockerfile.

## [v7.10.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.10.1) - 2021-12-11

### Added

- APM and alerting metrics via DataDog integration.
- Automatically rollback database transaction when a task fails.

## [v7.9.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.9.1) - 2021-12-07

### Added

- Handle `/lfg` in a thread by informing the user that it's not supported.

### Changed

- Fill in the transparent center of the SpellBot avatar.

## [v7.9.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.9.0) - 2021-12-03

### Removed

- Completely remove pylint from project dependencies just to make it totally clear
  that no source code from pylint nor any modules are being used within SpellBot.
  Tests using pylint will now require that you've installed it on your own.

### Added

- Adds publishing to docker hub as part of publish script.
- Admins can set the preferred voice category name prefix for created voice channels
  on a per-channel basis.

## [v7.8.4](https://github.com/lexicalunit/spellbot/releases/tag/v7.8.4) - 2021-11-28

### Changed

- Ensure that only non-deleted games are selected for inactivity.

## [v7.8.3](https://github.com/lexicalunit/spellbot/releases/tag/v7.8.3) - 2021-11-28

### Changed

- Generate previous and next page buttons' href values rather than use onclick.

## [v7.8.2](https://github.com/lexicalunit/spellbot/releases/tag/v7.8.2) - 2021-11-28

### Changed

- Updates some test snapshots.

## [v7.8.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.8.1) - 2021-11-28

### Changed

- Prevent page jumping to top before redirect.

## [v7.8.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.8.0) - 2021-11-28

### Changed

- Smaller page size on play records pages.
- Use browser's locale when humanizing timestamps.

## [v7.7.3](https://github.com/lexicalunit/spellbot/releases/tag/v7.7.3) - 2021-11-27

### Changed

- Adds an index to optimize records matching.
- Removes useless sorting in records subquery.
- Rearranges records subquery to better inform query optimizer.
- Removes needless guild and channel fetch from records query.
- Refactors channel records query to avoid duplicate seq scans.

## [v7.7.2](https://github.com/lexicalunit/spellbot/releases/tag/v7.7.2) - 2021-11-26

### Changed

- Undo previous SQL optimization, it actually was not needed.

## [v7.7.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.7.1) - 2021-11-26

### Changed

- Small SQL optimization to `/score` record page generation.

## [v7.7.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.7.0) - 2021-11-26

### Changed

- Soft delete games when they expire instead of actually deleting them.

## [v7.6.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.6.1) - 2021-11-25

### Fixed

- Small fix to the way pagination work in game history pages.

## [v7.6.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.6.0) - 2021-11-25

### Removed

- Removed `!command` CTA to use slash commands and legacy prefix logic.

## [v7.5.2](https://github.com/lexicalunit/spellbot/releases/tag/v7.5.2) - 2021-11-23

### Changed

- Updates dependencies

## [v7.5.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.5.1) - 2021-11-22

### Fixed

- Fixes a missed cli unit test

## [v7.5.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.5.0) - 2021-11-22

### Changed

- Using `uvloop` as a drop in replacement for `asyncio` to improve speed.

## [v7.4.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.4.0) - 2021-11-18

### Added

- Adds `/power :level` command to set your power level for a guild.

## [v7.3.3](https://github.com/lexicalunit/spellbot/releases/tag/v7.3.3) - 2021-11-18

### Fixed

- Fixes records view when users have `:` or `@` in their display names.

## [v7.3.2](https://github.com/lexicalunit/spellbot/releases/tag/v7.3.2) - 2021-11-12

### Fixed

- Fixes the `/setup` command when guild motd has been unset.

## [v7.3.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.3.1) - 2021-11-12

### Changed

- Made `message:` optional in `/set motd` and `/set channel_motd`.

### Fixed

- Handle user verification status within interactions instead of just messages.

## [v7.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.3.0) - 2021-11-10

### Added

- Adds `/set channel_motd` command to set channel message of the day.

## [v7.2.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.2.1) - 2021-11-09

### Changed

- Changed default branch name to main.

### Fixed

- Handle `name` property missing from guild, channel, or users.
- Handle upserts for guild, channel, and users more carefully.

## [v7.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.2.0) - 2021-11-06

### Added

- Adds the /game command for admins to create and start ad-hoc games.
- Adds voice channel and invite creation to the /game command.
- More test coverage.

### Changed

- Reduce the size of the `!lfg` CTA and delete it after 10 seconds.
- Adds some pyright config, remove mypy config.

### Fixed

- Ensure components are removed from expired games.
- Fix safari using table-cell display for td elements.
- Some css fixes for mobile.

## [v7.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.1.0) - 2021-11-01

### Added

- Adds the /verify and /unverify admin commands.
- Adds spectate link to watched user notifications.
- Adds game expiration after 45 minutes of inactivity.
- Message reply permission check in slash command CTA response.

### Fixed

- Workaround for wonky discord-interactions edit-origin failures.
- Fixes updated_at updates on games for user join/leave actions.
- Better sanity checking user input on the /info command.
- Safely handle the case where message xid was not set for a game.
- Fixes a spurious warning in test suite due to transaction rollback.

### Changed

- Dependency updates.
- Use the new spelltable.wizards.com domain for SpellTable links.

## [v7.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v7.0.1) - 2021-10-24

### Fixed

- Many bug fixes have been fixed after the were discovered when deploying SpellBot to production.

## [v7.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v7.0.0) - 2021-10-24

### Changed

- Complete rewrite of SpellBot to support the new Discord slash commands.

## [v6.1.4](https://github.com/lexicalunit/spellbot/releases/tag/v6.1.4) - 2021-06-15

### Fixed

- Fixes spectate urls since latest SpellTable update.

### Changed

- Dependency updates.

## [v6.1.3](https://github.com/lexicalunit/spellbot/releases/tag/v6.1.3) - 2021-06-02

### Fixed

- Handle not a number errors on `!spellbot awards` command.

## [v6.1.2](https://github.com/lexicalunit/spellbot/releases/tag/v6.1.2) - 2021-06-01

### Changed

- Give up on deleting voice channels that we don't have permissions for.

## [v6.1.1](https://github.com/lexicalunit/spellbot/releases/tag/v6.1.1) - 2021-06-01

### Fixed

- Fixes a bug in the `!report` command where the game url could be ambiguous.

## [v6.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v6.1.0) - 2021-06-01

### Added

- Added ability to ask for how many plays someone else has on a server.

## [v6.0.8](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.8) - 2021-05-20

### Changed

- Handle all exception classes in SpellTable API requests.
- Handle random CSV exceptions in processing of event data.

## [v6.0.7](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.7) - 2021-05-16

### Fixed

- Removed an unused import.

## [v6.0.6](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.6) - 2021-05-16

### Fixed

- Handle unhandled exceptions in background tasks so that the task doesn't die.

## [v6.0.5](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.5) - 2021-05-14

### Fixed

- Fixing a small mypy issue.

## [v6.0.4](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.4) - 2021-05-14

### Fixed

- Added more needed truncation for stored cached names.

### Added

- Adds SQL profiling: set environment `SPELLBOT_PROFILE=1` to enable.

## [v6.0.3](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.3) - 2021-05-13

### Fixed

- Fixes missing commit in voice channel cleanup.

## [v6.0.2](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.2) - 2021-05-13

### Added

- Adds some more logging to some tasks.
- More defensive code around SpellTable API calls.
- Permissions check on delete channel.

### Fixed

- Truncate user names at 50 characters.

## [v6.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.1) - 2021-05-11

### Fixed

- Fixes an isort issue.

## [v6.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v6.0.0) - 2021-05-11

### Removed

- Got rid of "active channels" entirely, use Discord permissions instead.

### Changed

- Refactoring commands to do less database work.
- Pass around a command context object instead of a bunch of random variables.

### Added

- Adding a separate build script to avoid accidental deploys.
- Adds `--use-feature=in-tree-build` to python builds to avoid deprecation warning.
- Adds exception handling for SpellTable API HTTP exceptions.

## [v5.31.6](https://github.com/lexicalunit/spellbot/releases/tag/v5.31.6) - 2021-05-10

### Changed

- Cleaning up the deploy.sh script a bit.

### Added

- Adds a couple more indexes on the games table to speed up some slow queries.

## [v5.31.5](https://github.com/lexicalunit/spellbot/releases/tag/v5.31.5) - 2021-05-09

### Changed

- A bit of refactoring to reduce db commits and clean some code up.

## [v5.31.4](https://github.com/lexicalunit/spellbot/releases/tag/v5.31.4) - 2021-05-08

### Fixed

- Fixes a bunch of bugs related to channel types.

## [v5.31.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.31.3) - 2021-05-08

### Fixed

- Fixes a bug in DM messaging.

## [v5.31.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.31.2) - 2021-05-08

### Fixed

- Fixes a bug where awards were not being given properly for games played.

## [v5.31.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.31.1) - 2021-05-08

### Fixed

- Fixes the !plays command so that it can work when you have plays in multiple servers.

## [v5.31.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.31.0) - 2021-05-08

### Added

- Adds the !plays command to see how many games you've played.

## [v5.30.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.30.0) - 2021-05-08

### Added

- Give user role awards when they reach the required play counts.

### Changed

- Changed force delete voice channel timeout to 5 hours from 7 hours.

## [v5.29.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.29.2) - 2021-05-06

### Changed

- Adds stringent permissions checking to code that fetches messages.
- Adds game's spelltable url to watched user notification.

## [v5.29.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.29.1) - 2021-05-06

### Changed

- Slightly more graceful handling of send DM failure when our bot is blocked.

## [v5.29.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.29.0) - 2021-05-06

### Added

- Automatically delete games from deleted channels and messages.

## [v5.28.10](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.10) - 2021-05-05

### Changed

- Adds stringent permissions checking to code that sends messages to channels.

## [v5.28.9](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.9) - 2021-05-05

### Changed

- Even more stringent permissions checking to make emoji reaciton code more robust.

## [v5.28.8](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.8) - 2021-05-05

### Changed

- Don't ignore any API errors as too many of these leads to API rate limiting.
- Check for permissions before trying to react with emojis.

## [v5.28.7](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.7) - 2021-05-02

### Fixed

- When a user is mentioned, make sure they're allowed read messages in that channel.

## [v5.28.6](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.6) - 2021-04-30

### Fixed

- Fixed some places where a commit was missing.

### Changed

- The "show links" configuration now also controls if you see the voice channel info.

## [v5.28.5](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.5) - 2021-04-28

### Changed

- Changed invite link expiration to 4 hours.

## [v5.28.4](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.4) - 2021-04-27

### Changed

- Reduced pop-in of "status: online" button on website.
- Changed invite link expiration to 24 hours.

## [v5.28.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.3) - 2021-04-21

### Fixed

- The implementation and API for roles and permissions in discord.py is absolute horseshit.

### Added

- Adds repeating awards, use % in front of the play count to indicate repeating award.
- Adds user tracking for awards.

## [v5.28.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.2) - 2021-04-20

### Fixed

- Fixing a bunch of bugs in how permissions and roles are calculated.

## [v5.28.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.1) - 2021-04-20

### Fixed

- Fixes a bug in how has_admin_perms is calculated.

## [v5.28.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.28.0) - 2021-04-20

### Added

- Adds configuration command for awards.

### Changed

- Allow bots to message SpellBot.
- Updates sqlalchemy.

## [v5.27.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.27.3) - 2021-04-08

### Changed

- Using caret-style version numbers in pyproject.toml to let dependabot know
  that it should try to keep production dependencies up to date.

## [v5.27.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.27.2) - 2021-04-07

### Added

- Updating to the latest version of discord.py
- Ignore .env files in tests

## [v5.27.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.27.1) - 2021-03-31

### Fixed

- Fixes postgres URI scheme for the API backend.
- Handle case where watched user note is too long.

### Added

- Adds historical tracking for `!game` invocations as well.

## [v5.27.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.27.0) - 2021-03-29

### Added

- Adds record keeping for historical game plays for users.

## [v5.26.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.26.0) - 2021-03-29

### Added

- Adds some event metrics instrumentation to discover if a feature is being used.

## [v5.25.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.25.3) - 2021-03-28

### Fixed

- Workaround for SQLAlchemy 1.4.x which removed support for the postgres:// URI scheme.

## [v5.25.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.25.2) - 2021-03-28

### Changed

- Updates to many dependencies.

## [v5.25.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.25.1) - 2021-03-15

### Fixed

- Fixed a bug in how block/unblock works with users that have spaces in name.

## [v5.25.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.25.0) - 2021-03-06

### Added

- Adds unverified-only channels for use by unverified users (and admins).
- New command to set unverified-only channels is `!spellbot unverified-only`.

## [v5.24.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.24.0) - 2021-03-06

### Added

- Added permissions error detection to the output of `!spellbot config`.

## [v5.23.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.23.0) - 2021-02-25

### Added

- Adds support to ban users.

## [v5.22.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.22.1) - 2021-02-23

### Fixed

- Filter out mentions in watch notes correctly.

## [v5.22.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.22.0) - 2021-02-22

### Added

- Adds notes for watched users.

## [v5.21.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.21.3) - 2021-02-21

### Fixed

- Don't overwrite channel cached_name with an empty string.

## [v5.21.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.21.2) - 2021-02-20

### Fixed

- Actually don't use mentions in game creation notes.

## [v5.21.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.21.1) - 2021-02-20

### Fixed

- Don't use mentions in game creation notes.

## [v5.21.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.21.0) - 2021-02-20

### Changed

- Pick up extra useless parameters to !lfg and use them as a creation note.

## [v5.20.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.20.2) - 2021-02-20

### Added

- Added an active guilds metric.

## [v5.20.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.20.1) - 2021-02-19

### Changed

- Adds some retry logic to SpellTable API call.

## [v5.20.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.20.0) - 2021-02-19

### Added

- Added new `!watch` and `!unwatch` commands that allows moderators to set up
  notifications for when a player enters a new game on their server.

## [v5.19.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.19.0) - 2021-02-19

### Added

- Added a new `!spellbot queue-time` command that allows admins to enable/disable
  average queue time details for the server or for specifically mentioned channels.

## [v5.18.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.18.0) - 2021-02-19

### Added

- Added ability to mention specific channels in `!spellbot tags` command to
  allow overrides for specific channels.

## [v5.17.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.17.1) - 2021-02-13

### Fixed

- Fixes a bug if you set the server prefix to something that a command starts with -- Thanks pongo!

### Changed

- Lots of dashboard cleanup including improvements to styles and login/logout flow.

## [v5.17.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.17.0) - 2021-01-28

### Added

- The `!game` command will now create voice channels if that's enabled for the server.
  And the new `!spellbot voice-category` command will define the category channel
  that these created voice channels will be put into. The default is to use the
  same category as the voice channels that are created by `!lfg`.

## [v5.16.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.16.0) - 2021-01-27

### Fixed

- Fixed the forwarding of environment variables in supervisord config.
- Fixed the API setup code path since subapps don't trigger events in fast api.
- Fixed the interaction between auto-verify channels and verification-required.

### Added

- Added a server logout to expire the http-only cookie.
- Introduces a logger tool for PlayEDH, just for debugging reasons.

### Changed

- Slightly better help message for some admin commands.
- Updates a number of dependencies -- Thanks dependabot!

## [v5.15.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.15.1) - 2021-01-22

### Changed

- Adds ninja blocks so you don't notify the user that you're blocking.

## [v5.15.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.15.0) - 2021-01-22

### Added

- Adds an initial WIP version of the SpellBot Dashboard.
- Adds !block and !unblock commands for users.

## [v5.14.4](https://github.com/lexicalunit/spellbot/releases/tag/v5.14.4) - 2021-01-15

### Fixed

- Fixes a bug in !power command use in DM.

### Changed

- Lots of dependencies have been updated to their latest -- Thanks dependabot!
- Updated some documentation about deployment.
- Adds some more logging to voice channel deletes.
- Adds a .dockerignore file to speed up docker builds.

## [v5.14.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.14.3) - 2020-12-16

### Changed

- Some updates to dependencies.

## [v5.14.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.14.2) - 2020-12-12

### Changed

- Use Python 3.9 in the docker container.

### Added

- Adds support for Python 3.9

## [v5.14.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.14.1) - 2020-12-10

### Fixed

- Fixes a bug that prevented SpellBot from responding to DMs.

## [v5.14.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.14.0) - 2020-12-09

### Added

- Adds ability to set auto-verification channels.

### Changed

- Change hover transition for add bot button on site.

## [v5.13.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.13.1) - 2020-12-06

### Changed

- Switch to Patreon for donations.

## [v5.13.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.13.0) - 2020-12-06

### Added

- Adds cached_name to channel settings.
- Adds created_at and updated_at to channel settings.

## [v5.12.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.12.0) - 2020-12-05

### Added

- Adds a last updated at column to user model.

### Fixed

- Update some Beautiful Jekyll CSS to work better across browsers.

## [v5.11.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.11.1) - 2020-12-04

### Fixed

- Also show spectator link in even orchestration commands.

## [v5.11.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.11.0) - 2020-12-04

### Removed

- Removes RSS feed from site.

### Added

- Adds GraphQL, security alerts, security policy, and badge.
- Allow servers to turn on a setting for showing spectator links.

### Changed

- Moves top.gg widget to navbar.
- Update to latest from beautiful-jekyll.

## [v5.10.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.10.0) - 2020-11-23

### Added

- Adds the `!spellbot toggle-verify` command that toggles the verification
  requirements for the channel that the command is ran within. Unverified users
  will be unable to use SpellBot in channels that require verification.
- Adds a `!verify` command that can be used to verify users mentioned.
- Adds an `!unverify` command that does the opposite of `!verify`.
- Adds a `!spellbot cmotd` command to set the channel message of the day.
- Adds a `!spellbot verify-message` command to set the not verified message for a channel.

### Changed

- The old `user_teams` table has been refactored into a generic `user_server_settings`
  that can contain any users settings related to a specific server, such as teams
  and verification status. The affected sql scripts have been updated.
- Use privileged members intents to find members by name.

## [v5.9.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.9.3) - 2020-11-18

### Changed

- Prefer to fill older games over newer games.

### Added

- Even more tests for higher code coverage.

## [v5.9.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.9.2) - 2020-11-18

### Added

- More tests for higher code coverage.

## [v5.9.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.9.1) - 2020-11-15

### Changed

- Server stats from all time instead of just the last five days.

## [v5.9.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.9.0) - 2020-11-15

### Added

- Adds a server stats command that can be expanded on in the future.

## [v5.8.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.8.3) - 2020-11-10

### Added

- More robust error handling when SpellBot tries to send messages to a channel.

## [v5.8.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.8.2) - 2020-11-10

### Fixed

- Game embeds now properly handle the case where the bot can not create a link.

## [v5.8.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.8.1) - 2020-11-08

### Changed

- Really old voice channels (more than 7 hours old) will be deleted even if
  there are still users in them.

## [v5.8.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.8.0) - 2020-11-05

### Added

- Adds settings for default game size on a per-channel basis.

## [v5.7.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.7.2) - 2020-11-01

### Added

- Automatically cleanup usage warnings sent to users after a brief period of time.

## [v5.7.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.7.1) - 2020-10-31

### Changed

- Refactor much of the codebase to use the member mention property.

### Added

- Adds a bunch of SQL scripts that can generate some interesting data sets.
- Adds a script to execute SQL scripts against a database to generate CSV files.
- Adds exception handling for Discord API Internal Server Errors.

## [v5.7.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.7.0) - 2020-10-27

### Added

- Adds name caching for servers.

## [v5.6.4](https://github.com/lexicalunit/spellbot/releases/tag/v5.6.4) - 2020-10-27

### Added

- Adds some more metrics.

## [v5.6.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.6.3) - 2020-10-27

### Changed

- Refactors background tasks code.

## [v5.6.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.6.2) - 2020-10-26

### Changed

- Updated poetry lock file to latest dependencies.

## [v5.6.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.6.1) - 2020-10-26

### Changed

- Updated aiohttp.

## [v5.6.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.6.0) - 2020-10-24

### Added

- Adds some notes about using a staging environment on heroku.
- Privacy settings for MOTD.
- Adds a warning for a very rare exception that I have observed happening.

## [v5.5.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.5.3) - 2020-10-24

### Fixed

- Ran into a production issue with SSL because aiohttp released a new version that
  had broken code due to variable shadowing: https://github.com/aio-libs/aiohttp/issues/5110
  The next patch version should have a fix but it's been 10 hours and they still
  having released a new version with the fix. I'm going to pin down all my production
  dependency versions to a specific version to avoid this in the future.

## [v5.5.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.5.0) - 2020-10-24

### Changed

- Use is\_() and isnot() to avoid spurious CodeFactor warnings.

### Added

- Adds support for a server wide message of the day setting.

## [v5.4.6](https://github.com/lexicalunit/spellbot/releases/tag/v5.4.6) - 2020-10-23

### Fixed

- Fixes an issue with metrics on PostgreSQL.

## [v5.4.5](https://github.com/lexicalunit/spellbot/releases/tag/v5.4.5) - 2020-10-23

### Added

- Adds some daily games created metrics.

## [v5.4.4](https://github.com/lexicalunit/spellbot/releases/tag/v5.4.4) - 2020-10-22

### Added

- Added some information to the game posts about how long till voice invites expire.

### Fixed

- Fixes an issue with session and game-creation locking where multiple users
  could all `!lfg` at the same time and the bot would treat each of them in
  sequence because of the game-creation lock, but it's view onto the database
  for each of those processes would be snapshotted to the same time. This could
  lead to a user's game seemingly being "stolen" out from under them.

## [v5.4.3](https://github.com/lexicalunit/spellbot/releases/tag/v5.4.3) - 2020-10-22

### Fixed

- Handle unexpected responses from the SpellTable API.

## [v5.4.2](https://github.com/lexicalunit/spellbot/releases/tag/v5.4.2) - 2020-10-22

### Changed

- Changes some warning errors to debug in the logs.
- Refactored how emoji reactions work.
- Average wait times based on games that started within the last hour.

## [v5.4.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.4.1) - 2020-10-19

### Added

- Adds a check for if the user is the owner of the guild and if so lets them
  run administrator commands without needing to have the role.
- Removes a bunch of `#pragma: no cover` directives to encourage me to add
  tests for this code. Most of it is not particular critical code that needs
  to be tested. For example: Fetching environment variables. But tests can and
  should be written for these things.

## [v5.4.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.4.0) - 2020-10-18

### Added

- Average wait time notifications for game posts.

### Removed

- Removes the "require avatars" feature for now... the solution to the problem
  that this feature was meant to solve requires a bit more thought.

### Fixed

- Fixes a small typo in readme/webpage.

## [v5.3.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.3.1) - 2020-10-18

### Added

- Also ignore user reactions for users without and avatar if avatars required is on.

## [v5.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.3.0) - 2020-10-18

### Added

- Adds an option to make user avatars required for a server.

## [v5.2.1](https://github.com/lexicalunit/spellbot/releases/tag/v5.2.1) - 2020-10-18

### Fixed

- Handle UTF errors in attachment processing.

## [v5.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.2.0) - 2020-10-17

### Removed

- Removed the `!help` command, use `!spellbot help` instead.

### Fixed

- Fixed an old invite link to have the correct permissions bits.

### Changed

- Changed the logic around the expired games deletion background task to be more robust.
- Added more information to the description of game posts to help users understand.
- Ignore any `!help` messages, too many other bots use that command.

## [v5.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.1.0) - 2020-10-17

### Changed

- Don't completely delete expired game posts, just delete their content.

### Added

- Added the ability to @mention other players with lfg to create/find games with them.
- You can now !lfg when you're in a pending game to "look for N more" players.

### Removed

- Removed the `!find` command as it was confusing and not useful.

## [v5.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v5.0.0) - 2020-10-17

- New major version, no code changes.

## [v4.10.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.10.0) - 2020-10-16

### Added

- Adds voice channel overflow logic so that new categories get created automatically.

## [v4.9.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.9.0) - 2020-10-16

### Changed

- Use a nicer looking embed as the response to a game being found.
- Message not found warnings logs are now debug logs.

## [v4.8.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.8.0) - 2020-10-16

### Removed

- Removed warning logging for 403 Forbidden errors when sending messages to users.
  This occurs all the time due to users having DMs blocked except from friends.

### Added

- More tests to get coverage on data and operations back up to 100%.

### Changed

- Async locking was added to ensure that there is no interleaved processing
  as we handle commands or emoji reactions that can create games. This prevents
  cases where, for example, multiple voice channels are created for a single
  game. Or redundant but idempotent processing is done during game creation.

## [v4.7.5](https://github.com/lexicalunit/spellbot/releases/tag/v4.7.5) - 2020-10-15

### Fixed

- Workaround a concurrency issue with creating new voice channels.

## [v4.7.4](https://github.com/lexicalunit/spellbot/releases/tag/v4.7.4) - 2020-10-14

### Added

- Added 10 minutes of leeway for vacant voice channels before deleting them.

## [v4.7.3](https://github.com/lexicalunit/spellbot/releases/tag/v4.7.3) - 2020-10-14

### Fixed

- Use a more reliable way to check for vacant voice channels.

## [v4.7.2](https://github.com/lexicalunit/spellbot/releases/tag/v4.7.2) - 2020-10-14

### Fixed

- Delay background tasks start until after bot has connected to discord.

## [v4.7.1](https://github.com/lexicalunit/spellbot/releases/tag/v4.7.1) - 2020-10-14

### Changed

- Check for expired games every 2 minutes instead of 30 seconds.
- Update metrics on startup instead of after 1 hour of uptime.
- Clean up voice channels every 10 minutes instead of every 30 minutes.

## [v4.7.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.7.0) - 2020-10-14

### Added

- Adds created_at for users and servers

## [v4.6.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.6.0) - 2020-10-14

### Added

- Turn on or off the ability to use tags on your server.

## [v4.5.2](https://github.com/lexicalunit/spellbot/releases/tag/v4.5.2) - 2020-10-13

### Added

- More robust redis connection and error handling.

## [v4.5.1](https://github.com/lexicalunit/spellbot/releases/tag/v4.5.1) - 2020-10-13

### Removed

- Removes the /metrics endpoint in favor of using redis for metrics storage.

### Added

- Adds redis metrics support.

## [v4.5.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.5.0) - 2020-10-13

### Added

- Adds some documentation that you can set teams to none to delete them.
- Adds voice channel instant invites when voice channels are turned on.

## [v4.4.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.4.0) - 2020-10-12

### Added

- Puts created voice channels into a "SpellBot Voice Channels" category.

### Fixed

- Fixed check for Authorization header to fail with 403 if not present.

## [v4.3.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.3.0) - 2020-10-12

### Added

- Adds a /metrics endpoint that returns some metrics about the bot.

## [v4.2.1](https://github.com/lexicalunit/spellbot/releases/tag/v4.2.1) - 2020-10-12

### Fixed

- Fixes a small typo in the docstring for the !spellbot command.

### Added

- Adds checks to ensure that the documentation for admin subcommands is synced.
- Adds checks to ensure that the webpage documentation for is synced.

### Updated

- Updates some admin documentation on the webpage.

## [v4.2.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.2.0) - 2020-10-12

### Added

- Adds the ability to automatically create new voice channels for games.
- Adds automatic task to clean up any unused voice channels that were created.

## [v4.1.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.1.0) - 2020-09-22

### Added

- Adds the ability to turn off the !power command completely for your server.

## [v4.0.2](https://github.com/lexicalunit/spellbot/releases/tag/v4.0.2) - 2020-09-17

### Fixed

- Cleans up error handling for discord operations.

## [v4.0.1](https://github.com/lexicalunit/spellbot/releases/tag/v4.0.1) - 2020-09-10

### Added

- More error handling and additional details to existing logging.

### Changed

- Resolves codefactor.io issues.

## [v4.0.0](https://github.com/lexicalunit/spellbot/releases/tag/v4.0.0) - 2020-09-06

### Added

- Adds more emoji reactions to let users know when a command was processed.

### Removed

- Removes aliases as they were confusing and no one was seeming to use them.
- Removes unnecessary response from leave command.

## [v3.25.2](https://github.com/lexicalunit/spellbot/releases/tag/v3.25.2) - 2020-08-31

### Fixed

- Fixes a bug where started event games were getting culled with expired games.

## [v3.25.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.25.1) - 2020-08-29

### Added

- Allow admins to remove teams.

### Fixed

- Update game post when a user's power changes.

## [v3.25.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.25.0) - 2020-08-26

### Removed

- Removed the navbar brand element from the site navbar.

### Changed

- Update to latest from beautiful-jekyll.

### Added

- Adds whitespace check exclusion for problematic beautiful-jekyll sources.

## [v3.24.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.24.0) - 2020-08-25

### Removed

- Removes the all the invitation code paths, this code needs to be refactored.

### Changed

- Updated screenshots.

## [v3.23.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.23.0) - 2020-08-25

### Fixed

- Fixed the section headers in the !help response.

### Removed

- Removed the !queue command as it was half-baked. It could come back again
  but only after some refactoring in the !lfg code and when fully thought out.

## [v3.22.13](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.13) - 2020-08-25

### Changed

- More visible emoji so that users can actually see them in dark mode.

## [v3.22.12](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.12) - 2020-08-23

### Fixed

- The !team command is only be allowed in server channels, not in DMs.

## [v3.22.11](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.11) - 2020-08-22

### Added

- Adds special handling for when players do a !powerN command with no space.

## [v3.22.10](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.10) - 2020-08-22

### Added

- Added a check that player includes at least one person in their !report.

## [v3.22.9](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.9) - 2020-08-22

### Changed

- Allow incomplete reports.

## [v3.22.8](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.8) - 2020-08-22

### Fixed

- Fixed incorrect error message to !report command.

### Changed

- Less verbose response to !team command.

## [v3.22.7](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.7) - 2020-08-22

### Added

- Added tracking of a game's power level when it is started so we can get stats.

## [v3.22.6](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.6) - 2020-08-21

### Added

- Adds some logic to make sure that player with power 6 are never placed into a
  game with average power level 7 or higher, and vice versa.

## [v3.22.5](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.5) - 2020-08-21

### Fixed

- Ensure that team points are scoped to a single server.

## [v3.22.4](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.4) - 2020-08-21

### Fixed

- Make sure to show team points even if they're 0.

## [v3.22.3](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.3) - 2020-08-20

### Added

- Adds inline documentation for some of the new @command features.
- Adds ability to group commands together in the help usage.

## [v3.22.2](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.2) - 2020-08-20

### Changed

- Less verbose response to players using the !help command; now it uses emoji.
- Less verbose response to players using the !power command; now it uses emoji.

## [v3.22.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.1) - 2020-08-19

### Changed

- Updated to latest from beautiful-jekyll.

### Added

- Adds support for reporting on game ids like "#sb1234".
- Adds some cheeky responses to the !power command.

## [v3.22.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.22.0) - 2020-08-19

### Added

- Adds report verification for CommandFest style reports.
- Adds team points to the response of !points when used by an admin.

## [v3.21.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.21.0) - 2020-08-19

### Added

- Added a link to uptime robot dashboard from README.md.
- Adds CodeFactor integration and fixes a few issues found by CodeFactor.
- Adds !spellbot teams command to configure sever teams.
- Adds a !team command for users to get and set their team.
- Adds report verification for CommandFest style reports.
- Adds team points to the response of !points when used by an admin.

## [v3.20.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.20.1) - 2020-08-16

### Added

- Adds a created_at column to report table.

## [v3.20.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.20.0) - 2020-08-16

### Added

- Adds at !report command to report on finished games.

## [v3.19.5](https://github.com/lexicalunit/spellbot/releases/tag/v3.19.5) - 2020-08-15

### Added

- Added uptime badge to readme.
- Added vote link to about embed and help response.

## [v3.19.4](https://github.com/lexicalunit/spellbot/releases/tag/v3.19.4) - 2020-08-15

### Added

- Added configuration for hostname.

## [v3.19.3](https://github.com/lexicalunit/spellbot/releases/tag/v3.19.3) - 2020-08-15

### Fixed

- Fixed the HTTP server code.
- Fixed the order of when to start the hupper reloader in dev mode.

### Added

- Added command line arguments for HTTP port.

## [v3.19.2](https://github.com/lexicalunit/spellbot/releases/tag/v3.19.2) - 2020-08-15

- Disable HTTP server for now.

## [v3.19.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.19.1) - 2020-08-15

- Use PORT env for HTTP server port.

## [v3.19.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.19.0) - 2020-08-15

### Added

- Added a twitter follow link in the readme.
- Added a very simple HTTP server for checking uptime.

## [v3.18.3](https://github.com/lexicalunit/spellbot/releases/tag/v3.18.3) - 2020-08-15

### Added

- Added a CTA for using !spellbot help when a user tries to run a nonexistent command.

## [v3.18.2](https://github.com/lexicalunit/spellbot/releases/tag/v3.18.2) - 2020-08-15

### Changed

- Renamed the !join command to !find to avoid overlap with MEE6.

## [v3.18.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.18.1) - 2020-08-15

### Changed

- Updated to latest from beautiful-jekyll.
- Re-enabled cleanup task for expired pending games.
- When matching a player with power to a pending games, don't consider power-less games.

## [v3.18.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.18.0) - 2020-08-14

### Added

- Added the !power command and support for power level matching.

### Changed

- Added `apt-get update` to CI workflow.
- Using a newer version of Ubuntu for CI.

### Fixed

- Fixed the migrations test so that it actually uses the CI configured database.
- Fixed some typos in an old migration script.

## [v3.17.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.17.0) - 2020-08-12

### Added

- Link to docker hub published image.
- Online status badge from top.gg.
- Documentation for beautiful-jekyll.
- A top.gg widget to the site.
- Feedback section in the README.
- Added links privacy server setting.

## [v3.16.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.16.1) - 2020-08-09

### Removed

- Deleted the crufty about me page.
- Unused SpellTable logo.

### Changed

- Changed the site favicon to be a SpellBot icon instead of a SpellTable icon.
- Moves SpellBot specific CSS changes to the theme into its own file.
- Cropped SpellBot logo to content.

### Added

- Adds meta keywords to site.
- Adds a method for updating the site's beautiful-jekyll copy.
- Updated the site's theme and added some css tweaks like transitions.
- Added test to ensure no trailing whitespace and that we do file ending newlines.
- Some documentation for docker hub publishing.

## [v3.16.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.16.0) - 2020-08-07

### Changed

- Renamed and rephrased the Secrets section to an Ergonomics section.
- Changed link from SpellTable Patreon to SpellTable Discord server.

### Added

- Adds meta theme-color and meta og:site_name to front page.
- Adds a note about Administrator permissions to the Commands for Admins section of the front page.
- Spellbot will message in the channel when it does not have permission to adjust reactions.
- Added more tests to increase coverage.
- Added a section on the front page to ask for feedback.

## [v3.15.4](https://github.com/lexicalunit/spellbot/releases/tag/v3.15.4) - 2020-08-02

### Fixed

- Fixed a typo in a warning message string.

### Added

- Adds a clarification about role permissions to the front page.

### Changed

- Moves AsyncMock to module level.

## [v3.15.3](https://github.com/lexicalunit/spellbot/releases/tag/v3.15.3) - 2020-08-01

### Changed

- Refactors parts of the test suite into modules.

## [v3.15.2](https://github.com/lexicalunit/spellbot/releases/tag/v3.15.2) - 2020-08-01

### Added

- Added a cute 404 page image.

### Fixed

- Fixes an issue when exporting games associated with events.

## [v3.15.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.15.1) - 2020-07-31

### Changed

- Cleans up some css on the front page.
- Refactors test mocks into their own module.

### Added

- Adds link to game post for enqueue response.

## [v3.15.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.15.0) - 2020-07-31

### Added

- Support for google analytics tag manager.
- Adds some notes about the `SpellBot Admin` role and links to Discord
  documentation on role creation to both the readme (thanks to
  [@crookedneighbor](https://github.com/crookedneighbor)) and front page.
- Added message links when informing the player that they were added to a game so it's easier to
  find the post. Before you would have had to scroll up in history to find it manually.
- Added a markdown-lint configuration and made some small improvements to some markdown files.

### Changed

- Changed the colors of the add-bot and ko-fi buttons in the readme to match the front page.
- Updated dunamai dependency to 1.3.0.
- Changed twitter social link to the new @SpellBotIO twitter account.
- Updated isort dev dependency to 5.2.2.
- When trying to `!lfg` and you're already in a pending game, you will now automatically be
  removed from that game first, then your command will be processed as normal.
- When trying to react with a + to a game when you're already in a pending game, you will
  first be removed from your pending game and then added to that new game.

## [v3.14.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.14.0) - 2020-07-30

### Removed

- Removes the unused pydantic dependency.

### Added

- Adds some much nicer buttons and logos to the front page.
- Adds an admin-only `!queue` command for on-demand events.

## [v3.13.9](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.9) - 2020-07-29

### Fixed

- Workaround over-eager caching of embed thumbnail images by discord.

## [v3.13.8](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.8) - 2020-07-29

### Added

- Added a longer meta description for the front page.
- Added FB OpenGraph and Twitter Summary cards back into the header.

### Changed

- Use the phrase "the Discord bot" instead of "a Discord bot".
- Use the size title for the front page.
- Enabled mypy analysis for pytest since version 6.0.0 now supports it!
- Moved tox and pytest configuration into pyproject.toml.
- Moved flake8 configuration into .flak8 so that I could delete tox.ini.

### Fixed

- Fixes a spelling error on the front page.
- Fixes the screenshot borders on the front page.

## [v3.13.7](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.7) - 2020-07-29

### Changed

- Updates the screenshots in the readme and front page.

### Fixed

- Fixes some broken markdown syntax in the response to `!help`.

## [v3.13.6](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.6) - 2020-07-29

### Fixed

- Fixes an issue where users might react with + to a game but not be able to join it, but also not be able to !leave any games either.

## [v3.13.5](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.5) - 2020-07-29

### Changed

- Updates the logo to be something different than exactly what SpellTable uses to avoid confusion.
- Rewrites some copy on the front page.

## [v3.13.4](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.4) - 2020-07-29

### Changed

- Don't allow admins to lock themselves out of using SpellBot by setting invalid channels.
- Allow admins to set the bot to operate within all channels.
- Better communication about warnings and errors when using the `!spellbot channels` command.

## [v3.13.3](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.3) - 2020-07-28

### Added

- Adds #BLM donation link to front page.
- Removes some information from the !about embed that is just clutter.
- Disables auto-embed links for responses to admin when games are created.

## [v3.13.2](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.2) - 2020-07-28

### Fixed

- Adds logic to handle the error when a user appears in multiple pairings in an event.

## [v3.13.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.1) - 2020-07-28

### Changed

- Makes the navbar easier to read, especially the hamburger menu icon.
- Adds a neat border to the screenshot images.
- Beautify the index.html file and fix the broken links in the contributing section.

## [v3.13.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.13.0) - 2020-07-28

### Added

- Added a webpage for SpellBot: spellbot.io.
- Adds an invite link to the !about embed and !help response.

### Fixed

- Fixes a typo in the contributing docs.

## [v3.12.2](https://github.com/lexicalunit/spellbot/releases/tag/v3.12.2) - 2020-07-27

### Changed

- Updates some documentation including screenshots.

## [v3.12.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.12.1) - 2020-07-27

### Added

- Adds the ability to join-up with someone by mentioning them in your lfg/join commands.
- Adds this changelog going back a few releases. It will be used more in future releases.

## [v3.12.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.12.0) - 2020-07-27

### Added

- Adds functional tags for game size. For example, using ~modern will now automatically assume the game size is 2.

## [v3.11.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.11.1) - 2020-07-27

### Changed

- Improves various documentation and usage help.

## [v3.11.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.11.0) - 2020-07-27

### Changed

- Improves a lot of the bot's communication and logging.

## [v3.10.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.10.1) - 2020-07-27

### Added

- Adds documentation for bot permissions.

## [v3.10.0](https://github.com/lexicalunit/spellbot/releases/tag/v3.10.0) - 2020-07-26

### Added

- Adds aliases for a bunch of commands to improve usability.

## [v3.9.3](https://github.com/lexicalunit/spellbot/releases/tag/v3.9.3) - 2020-07-26

### Fixed

- Fixes an issue with event command.

## [v3.9.2](https://github.com/lexicalunit/spellbot/releases/tag/v3.9.2) - 2020-07-26

### Fixed

- Fixes a bug with tag matching that prevented users from being able to correctly join existing games.

## [v3.9.1](https://github.com/lexicalunit/spellbot/releases/tag/v3.9.1) - 2020-07-26

### Fixed

- Fixed an issue so that game embeds will update when users leave the game via the leave command.
