# Contributing

This bot is a Python based Discord bot built on top of the [`discord.py`](https://github.com/Rapptz/discord.py) library.

It uses [`uv`](usage) to manage dependencies. To install development dependencies use: `uv sync`. This will allow you to run [PyTest](https://docs.pytest.org/en/latest/) and the included scripts.

You can install `uv` with the script [`brew`](https://brew.sh/):

```shell
brew install uv
```

## Installing the application

Install in development mode via `uv`:

```shell
uv sync
```

## Launch Dependencies

SpellBot requires a database to run properly. The connection string for the database you want to use must be stored in the environment variable `DATABASE_URL`.

You can start a local database via Docker by running:

```shell
docker run -i --rm -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15
```

Using this locally will allow you to use the default value for `DATABASE_URL` without having to manually set it to anything.

## Running the application

Make sure that you have [set up your environmental variables](/README.md#-running-spellbot-yourself).

If you wish, you can use a [.env file](https://pypi.org/project/python-dotenv/). Copy the `.env.example` file to get started.

When your environmental variables are set, run:

```shell
uv run spellbot --help
```

This will list some useful flags you can provide to run SpellBot. To get started developing, run:

```shell
uv run spellbot --dev
```

This will start SpellBot and reload it whenever the source code changes.

## Running tests

```shell
uv run pytest --cov --cov-report=html
open coverage/index.html
```

## Formatting and linting

Codebase consistency is maintained by [ruff][ruff].

```shell
uv run pytest -k codebase
```

## Interactive Shell

An interactive shell using [IPyhton](https://ipython.readthedocs.io/en/stable/) can be started by running:

```shell
uv run python shell.py
```

From this shell you will be able to interact with the database using SpellBot models and code. For example:

```shell
$ uv run python shell.py

In [1]: DatabaseSession.query(User).all()
Out[1]: []
```

## Release process

There's two methods for doing a release. You can use a script to handle everything for you automatically, or you can basically do every step in that script manually. Both methods are described below but I recommend the script.

### Scripted

To do a release automatically there is a \*NIX script available in the `scripts`
directory to help. To use it you will need to have non-interactive
`uv publish` enabled by running:

```shell
uv publish --token "YOUR-PYPI-TOKEN-GOES-HERE"
```

If you don't have one, you can create your PyPI token for this command by going to the [PyPI settings for spellbot](https://pypi.org/manage/project/spellbot/settings/) and clicking on the `Create a token for spellbot` button there. Of course you will have to be a collaborator for this project on PyPI to be able to do this. Contact [spellbot@lexicalunit.com](mailto:spellbot@lexicalunit.com) to be added to the project.

Once you have that set up, you can release a new version by running:

```shell
scripts/publish.sh <major | minor | patch>
```

You must select either `major`, `minor`, or `patch` as the release kind. Please follow [semver](https://semver.org/) for guidance on what kind of release to make. But basically:

- Major: Breaking changes.
- Minor: New features.
- Patch: Bug fixes.

### Manually

To release a new version of `spellbot`, use `uv`:

```shell
uv version --bump [major|minor|patch]
uv run pytest # verify that all tests pass
# edit the CHANGELOG.md file to promote all unlreased changes to the new version
uv build
git commit -am "Release vM.N.P"
uv publish # you will be prompted for your PyPI login credentials here
git tag 'vM.N.P'
git push --tags origin main
```

> **Note:** The reason you should run `pytest` after running the `uv version`
> command is to ensure that all test still pass after the version is updated.

You can get the `M.N.P` version numbers from `pyproject.toml` after you've run the `uv version` command. On a \*NIX shell you could also get it automatically like so:

```shell
grep "^version" < pyproject.toml | cut -d= -f2 | sed 's/"//g;s/ //g;s/^/v/;'
```

After publishing you can view the package at its [pypi.org project page](https://pypi.org/project/spellbot/) to see that everything looks good.

## Database migrations

We use [alembic][alembic] for database migrations. It can detect changes you've made compared to an existing database and generate migration scripts necessary to apply _and_ reverse those changes. First, make the changes to the data models. Alembic can detect differences between an existing database and changes made to the models. To autogenerate migration scripts that will bring the database inline with the changes you've made to the models, run:

```shell
uv run scripts/create_db_revision.py \
    "<your-sqlalchemy-database-url>" \
    "<Some description of your changes>"
```

> Note: An example database url: postgresql+psycopg://postgres@localhost:5432/postgres

This will create a revision script in the `src/spellbot/versions/versions` directory with a name like `REVISIONID_some_description_of_your_changes.py`. You may have to edit this script manually to ensure that it is correct as the autogenerate facility of `alembic revision` is not perfect.

### Downgrading

Another migration script is `scripts/downgrade.py` which allows you to pass a revision string to downgrade to. For example, to undo the last migration you could run something like:

```shell
uv run scripts/downgrade.py postgresql+psycopg://postgres@localhost:5432/postgres "-1"
```

## Metrics

SpellBot is set up to integrate with [DataDog][datadog] for system and service
metrics. This requires a few things:

1. [In the container](Dockerfile), we install and configure to run the
   following services:
    - [`dd-agent`][dd-agent]
    - [`trace-agent`][trace-agent]
    - [`process-agent`][process-agent]
1. A source dependency on the python [Datadog APM Client: ddtrace][ddtrace].
1. Instrumentation of code using the [`ddtrace` tracer interface][tracer].
1. A deployment with the correct environment variables to configure `dd-agent`.
    - `DD_API_KEY` = Your DataDog API key.
    - `DD_APP_KEY` = Your DataDog application key.
    - `DD_AGENT_MAJOR_VERSION` = "7"
    - `DD_HOSTNAME` = "spellbot"
    - `DD_ENV` = "dev", "stage", or "prod"
1. A `datadog.yaml` file including the following configuration:

    ```yaml
    apm_config:
      enabled: true
      apm_non_local_traffic: true
    ```

1. When starting the `spellbot` process, start it via `ddtrace-run spellbot`
   so that the APM client hooks are properly installed.

Locally in development you can use the following invocation to quickly spin up a `dd-agent`. And to set up your environment you should use the `.env` file.

```shell
docker run --rm \
    --name dd-agent \
    -p8125:8125 \
    -p8126:8126 \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    -v /proc/:/host/proc/:ro \
    -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
    -e DD_API_KEY="Your DataDog API key" \
    -e DD_APP_KEY="Your DataDog application key" \
    -e DD_AGENT_MAJOR_VERSION="7" \
    -e DD_SERVICE="spellbot" \
    -e DD_HOSTNAME="localhost" \
    -e DD_ENV="dev" \
    gcr.io/datadoghq/agent:7
```

[alembic]: https://alembic.sqlalchemy.org/
[ruff]: https://docs.astral.sh/ruff/
[datadog]: https://www.datadoghq.com/
[dd-agent]: https://github.com/DataDog/dd-agent
[ddtrace]: https://ddtrace.readthedocs.io/en/stable/index.html
[process-agent]: https://docs.datadoghq.com/infrastructure/process/
[trace-agent]: https://docs.datadoghq.com/tracing/setup_overview/
[tracer]: https://ddtrace.readthedocs.io/en/stable/advanced_usage.html
