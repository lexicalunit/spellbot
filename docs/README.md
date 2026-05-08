# SpellBot.io

This is the source for [https://spellbot.io](https://spellbot.io). Automatic [deployments][deployments] are handled by `github-pages`. The site's theme is built using [beautiful-jekyll][beautifuljekyll].

## Development

To install dependencies and serve the site locally use the following commands.

```shell
brew install rbenv
rbenv install
eval "$(rbenv init - zsh)"
rbenv rehash
bundle update --bundler
bundle install
bundle exec jekyll serve
```

Or just run `make` if you have it installed and it will do all of the above for you.

## Updating

First check that `.ruby-version` has the version used by [GH Pages][gh-pages-versions]. If not, update that and re-install everything.

The `scripts/update_docs.sh` script can automatically update the theme source code to the latest. It will **overwrite** existing files so make sure changes are checked in before running the script. You will then have to manually revert changes, line by line, in files such as `_config.yml` (and potentially others) so that relevant updates are applied without blowing away any `spellbot.io` settings or customization.

[beautifuljekyll]: https://beautifuljekyll.com/
[deployments]: https://github.com/lexicalunit/spellbot/deployments/activity_log?environment=github-pages
[gh-pages-versions]: https://pages.github.com/versions/
