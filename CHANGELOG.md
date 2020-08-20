# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Updated to latest from beautiful-jekyll.

### Added

- Adds support for reporting on game ids like "#sb1234".

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
