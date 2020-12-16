# Docker Support

SpellBot components can be run directly from docker so that you don't have
to worry about installing anything or managing your environment.

## SpellBot

**Pull the latest image from the registry:**

```shell
docker pull lexicalunit/spellbot
```

**Or build it yourself:**

```shell
docker build -t spellbot -f Dockerfile.bot .
```

You can now run it via `docker run`. You'll want to pass your
configuration into the bot via environment variables. You will also want
to mount a volume for the `db` directory so that your application state
doesn't get blown away whenever you kill and remove the image.

```shell
docker run \
    -e SPELLBOT_TOKEN="<your-discord-bot-token>" \
    -e SPELLTABLE_AUTH="<your-spellbot-api-token>" \
    -e SPELLBOT_DB_URL="<your-sqlalchemy-database-url>" \
    -v "$(pwd)/db":/db \
    --rm \
    spellbot
```

> **Note:** Leave `SPELLBOT_DB_URL` unset if you want to use sqlite3.

## SpellAPI

The SpellBot API can be built by running this from the repository root:

```shell
docker build -t spellapi -f Dockerfile.api .
```

Then run it:

```shell
docker run -it --rm -p 8080:80 spellapi
```

## SpellDash

You will need to provide your `REACT_APP_REDIRECT_URI` and
`REACT_APP_CLIENT_ID` values to properly build the SpellBot Dashboard.
Your Client ID is the ID of your SpellBot application in Discord and the
Redirect URI is your configured OAuth2 redirect URI. It should be the
URL to your SpellBot Dashboard application on Heroku.

Then it can be built by running this from the repository root:

```shell
docker build \
    -t spelldash \
    --build-arg REACT_APP_REDIRECT_URI="<your-oauth-redirect-uri>" \
    --build-arg REACT_APP_CLIENT_ID="<your-application-client-id>" \
    --build-arg NODE_ENV="<your-node-env>" \
    -f Dockerfile.dash dash
```

You can now run it via `docker run`. You'll want to pass your
configuration into the dash via environment variables. For example, you can
configure the internal port that nginx will bind to by passing in `PORT`.

```shell
docker run -it --rm -p 8080:80 spelldash
```

Then visit the site by going to `http://localhost:8080` in your web browser.
