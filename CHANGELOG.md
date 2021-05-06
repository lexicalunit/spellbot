# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
