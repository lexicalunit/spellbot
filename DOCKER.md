# Docker Support

SpellBot can be run directly from docker so that you don't have to worry
about installing anything or managing your Python environment.

First build your SpellBot docker image.

```shell
docker build -t spellbot .
```

You can now run it via `docker run`. You'll want to pass your
configuration into the bot via environment variables. You will also want
to mount a volume for the `db` directory so that your application state
doesn't get blown away whenever you kill and remove the image.

```shell
docker run \
    -e SPELLBOT_TOKEN="<your-discord-bot-token>" \
    -e SPELLBOT_AUTH="<your-spellbot-api-token>" \
    -e SPELLBOT_DB_URL="<your-sqlalchemy-database-url>" \
    -v "$(pwd)/db":/db \
    --rm
    spellbot
```

> **Note:** Don't set `SPELLBOT_DB_URL` if you want to use sqlite3.
