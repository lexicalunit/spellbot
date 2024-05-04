# Docker Support

SpellBot can be run directly from docker so that you don't have
to worry about installing anything or managing your environment.

## Database

You can quickly get a PostgreSQL Database running locally with `docker`:

```shell
docker run -i --rm -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15
```

You should then be able to connect to this database using `psql`:

```shell
psql -h localhost -p 5432 -U postgres
```

## SpellBot

Either pull the latest image from the registry:

```shell
docker pull lexicalunit/spellbot
```

Or build it yourself:

```shell
docker build -t spellbot .
```

Now you can run SpellBot via `docker run`. You should pass your
configuration into the process via environment variables:

```shell
docker run -it --rm -p 8080:80 \
    -e HOST="0.0.0.0" \
    -e PORT="80" \
    -e DATABASE_URL="postgresql://postgres@host.docker.internal:5432/postgres" \
    -e API_BASE_URL="http://localhost:8080" \
    -e DD_TRACE_ENABLED="false" \
    -e BOT_TOKEN="<Your Discord provided bot token>" \
    -e SPELLTABLE_AUTH_KEY="<Your SpellTable API auth token>" \
    -e DEBUG_GUILD="<optional: Debug guild id to use>" \
    <lexicalunit/spellbot (pulled from registry) or spellbot (built locally)>
```
