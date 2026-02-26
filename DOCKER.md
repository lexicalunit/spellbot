# Docker Support

SpellBot can be run directly from docker so that you don't have
to worry about installing anything or managing your environment.

## Database

You can quickly get a PostgreSQL Database running locally with `docker`:

```shell
docker run -i --rm -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:17
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
DD_VERSION="$(git rev-parse --short HEAD)"
DOCKER_BUILDKIT=0 docker buildx build \
    --build-arg DD_VERSION="$DD_VERSION" \
    --ulimit nofile=1024000:1024000 \
    --platform linux/arm64 \
    -t 'lexicalunit/spellbot' .
```

Now you can run SpellBot via `docker run`. You should pass your
configuration into the process via environment variables:

```shell
docker run -it --rm \
    -e DATABASE_URL="postgresql://postgres@host.docker.internal:5432/postgres" \
    -e API_BASE_URL="http://localhost:8080" \
    -e DD_TRACE_ENABLED="false" \
    -e BOT_TOKEN="<Your Discord provided bot token>" \
    -e CONVOKE_API_KEY="<Your Convoke API key>" \
    lexicalunit/spellbot
```

For full functionality you will need to start the API as well:

```shell
docker run -it --rm -p 8080:80 \
    -e HOST="0.0.0.0" \
    -e PORT="80" \
    -e DATABASE_URL="postgresql://postgres@host.docker.internal:5432/postgres" \
    -e DD_TRACE_ENABLED="false" \
    lexicalunit/spellbot ./start.sh spellapi
```

## Metrics

To get datadog metrics working locally you will need to spin up a datadog agent. You can do this with the following command:

```shell
docker run --rm --name datadog-agent \
    -e DD_API_KEY="<your-api-key>" \
    -e DD_SITE="datadoghq.com" \
    -e DD_HOSTNAME="local" \
    -e DD_APM_ENABLED=true \
    -e DD_APM_NON_LOCAL_TRAFFIC=true \
    -e DD_DOGSTATSD_NON_LOCAL_TRAFFIC=true \
    -p 8125:8125/udp \
    -p 8126:8126/tcp \
    gcr.io/datadoghq/agent:latest
```
