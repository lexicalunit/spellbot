# Contributing

This bot is a Python based Discord bot built on top of the
[`discord.py`](https://github.com/Rapptz/discord.py) library.

It uses [`poetry`](usage) to manage dependencies. To install development
dependencies use: `poetry install`. This will allow you to run
[PyTest](https://docs.pytest.org/en/latest/) and the included scripts.

You can install `poetry` with the script `install-poetry.py`:

```shell
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -
```

## Installing the application

Install in development mode via `poetry`:

```shell
poetry install
```

> **Note:** On some systems such as most Linux ones you may also need to install
> `python3-venv` using your system's package manager as `poetry` depends on it.

## Running the application

Make sure that you have [set up your environmental variables](/README.md#-running-spellbot-yourself).

If you wish, you can use a [.env file](https://pypi.org/project/python-dotenv/). Copy the `.env.example` file to get started.

When your environmental variables are set, run:

```shell
poetry run spellbot --help
```

This will list some useful flags you can provide to run SpellBot. To get started developing, run:

```shell
poetry run spellbot --dev
```

This will start SpellBot and reload it whenever the source code changes.

## Running tests

We use [tox](https://tox.readthedocs.io/en/latest/) to manage test execution.
It can be installed with `pip`:

```shell
pip install -U tox
```

Whenever you ran the `poetry install` command for the first time it created a
virtual environment for you based on which python environment you installed
`poetry` into.

Our `tox` configuration has tests set to run against multiple python
environments. So you will need to manage multiple installs of python to be able
to support testing in multiple environments. Thankfully
[`pyenv`](https://github.com/pyenv/pyenv) and
[`tox-pyenv`](https://pypi.org/project/tox-pyenv/) make this straightforward and
seamless.

First [install `pyenv`](https://github.com/pyenv/pyenv#installation) on your
machine. There are various methods to do this, some easier than others. On macOS
I'd use [Homebrew](https://brew.sh/) and for other systems I, and the author of
`pyenv`, recommend
[`pyenv-installer`](https://github.com/pyenv/pyenv-installer).

Now install [`tox-pyenv`](https://pypi.org/project/tox-pyenv/) so that `tox` can
automatically find your environments:

```shell
pip install -U tox-pyenv
```

Now let's create the python environments you'll need. The following commands
will do this on any \*NIX system. For other systems hopefully what I'm doing here
is instructive. Details on each command are given with inline comments.

```shell
# install a plugin that allows pyenv to know how to fetch the latest versions
rm -rf "$(pyenv root)"/plugins/xxenv-latest
git clone https://github.com/momo-lab/xxenv-latest.git "$(pyenv root)"/plugins/xxenv-latest

# for each python environment in the tox configuration, create it using pyenv
# this step takes a while, but you will only need to do this setup once
tox -l | while read -r py; do
    # translate a tox env name like "py39" into a number like "39"
    number="$(echo "$py" | sed "s/^py//")"

    # translate a number like "39" into a python version like "3.9"
    version="${number:0:1}.${number:1:1}"

    # install the latest python interpreter for that version
    pyenv latest install "$version"
done

# configure tox-pyenv to use the interpreters we just installed
pyenv local $(pyenv versions --bare | tr '\n' ' ')
```

The above script, **at the time of this writing**, amounts to running the
following commands:

```shell
pyenv install 3.9.6
pyenv local 3.9.6
```

But over time newer versions of python will become available and the above
script should automatically handle that for you. Also not that over time
you may need to run `pyenv uninstall` on old and unused python versions.

> **Note:** If your `pyenv install` command fails, please read
> [this](https://github.com/pyenv/pyenv/wiki/common-build-problems) help
> documentation provided by `pyenv`. You probably need to install some
> prerequisites on your system using your system's package manager.

Now you should be able to run the entire test suite against all python
environments with:

```shell
tox
```

Or a specific set of tests and environment. For example all tests pertaining to
users using the `py39` environment:

```shell
tox -e py39 -- -k user
```

After running the _full test suite_ you can view code coverage reports in the
`coverage` directory broken out by python environment.

```shell
open coverage/py39/index.html
```

## Formatting and linting

Codebase consistency is maintained by the industry standard [black][black]. For
linting we use [flake8](https://flake8.pycqa.org/en/latest/) with configuration
to work alongside the formatter. Imports are kept in order by
[isort](https://timothycrosley.github.io/isort/). The included test suite can
run these tools against the codebase and report on any errors:

```shell
tox -- -k codebase
```

## Release process

There's two methods for doing a release. You can use a script to handle
everything for you automatically, or you can basically do every step in that
script manually. Both methods are described below but I recommend the script.

### Scripted

To do a release automatically there is a \*NIX script available in the `scripts`
directory to help. To use it you will need to have non-interactive
`poetry publish` enabled by running:

```shell
poetry config pypi-token.pypi "YOUR-PYPI-TOKEN-GOES-HERE"
```

If you don't have one, you can create your PyPI token for this command by going
to the
[PyPI settings for spellbot](https://pypi.org/manage/project/spellbot/settings/)
and clicking on the `Create a token for spellbot` button there. Of course you
will have to be a collaborator for this project on PyPI to be able to do this.
Contact [spellbot@lexicalunit.com](mailto:spellbot@lexicalunit.com) to be added
to the project.

Once you have that set up, you can release a new version by running:

```shell
scripts/publish.sh <major | minor | patch>
```

You must select either `major`, `minor`, or `patch` as the release kind. Please
follow [semver](https://semver.org/) for guidance on what kind of release to
make. But basically:

- Major: Breaking changes.
- Minor: New features.
- Patch: Bug fixes.

### Manually

To release a new version of `spellbot`, use `poetry`:

```shell
poetry version [major|minor|patch]
tox # verify that all tests pass for all environments
# edit the CHANGELOG.md file to promote all unlreased changes to the new version
poetry build
git commit -am "Release vM.N.P"
poetry publish
git tag 'vM.N.P'
git push --tags origin main
```

> **Note:** The reason you should run `tox` after running the `poetry version`
> command is to ensure that all test still pass after the version is updated.

You can get the `M.N.P` version numbers from `pyproject.toml` after you've run
the `poetry version` command. On a \*NIX shell you could also get it automatically like so:

```shell
grep "^version" < pyproject.toml | cut -d= -f2 | sed 's/"//g;s/ //g;s/^/v/;'
```

When you use the `poetry publish` command you will be prompted for your
[PyPI](https://pypi.org/) credentials.

After publishing you can view the package at its
[pypi.org project page](https://pypi.org/project/spellbot/) to see that
everything looks good.

## Deployment Process

Below is a script for deploying SpellBot to Heroku. You can also use the `publish.sh`
script included in this repository rather than running these manually.

```shell
# You have to be logged into the Heroku container registry
docker login
heroku login
heroku container:login

APP="<the name of your heroku app>"

docker build -t "registry.heroku.com/$APP/web" .
docker push "registry.heroku.com/$APP/web"
heroku container:release web --app $APP
```

## Database migrations

We use [alembic][alembic] for database migrations. It can detect changes you've
made compared to an existing database and generate migration scripts necessary
to apply _and_ reverse those changes. First, make the changes to the data
models. Alembic can detect differences between an existing database and changes
made to the models. To autogenerate migration scripts that will bring the
database inline with the changes you've made to the models, run:

```shell
poetry run scripts/create_db_revision.py \
    "<your-sqlalchemy-database-url>" \
    "<Some description of your changes>"
```

This will create a revision script in the `src/spellbot/versions/versions`
directory with a name like `REVISIONID_some_description_of_your_changes.py`.
You may have to edit this script manually to ensure that it is correct as
the autogenerate facility of `alembic revision` is not perfect.

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

Locally in development you can use the following invocation to quickly spin
up a `dd-agent`. And to set up your environment you should use the `.env` file.

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
    -e DD_HOSTNAME="spellbot" \
    -e DD_ENV="dev" \
    gcr.io/datadoghq/agent:7
```

[alembic]: https://alembic.sqlalchemy.org/
[black]: https://github.com/psf/black
[datadog]: https://www.datadoghq.com/
[dd-agent]: https://github.com/DataDog/dd-agent
[ddtrace]: https://ddtrace.readthedocs.io/en/stable/index.html
[process-agent]: https://docs.datadoghq.com/infrastructure/process/
[trace-agent]: https://docs.datadoghq.com/tracing/setup_overview/
[tracer]: https://ddtrace.readthedocs.io/en/stable/advanced_usage.html
[wiki]: https://animalcrossing.fandom.com/
