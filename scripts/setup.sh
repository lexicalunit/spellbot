#!/bin/bash -ue

usage() {
    echo "usage: ${0##*/} [-h | --help]" 1>&2
    echo "Sets up python virtual env, poetry, and dev dependencies." 1>&2
    exit 1
}

run() {
    echo -n $'\e[38;5;40m$\e[38;5;63m '
    echo -n "$@"
    echo $'\e[0m'
    eval "$@"
    return $?
}

if echo "$*" | grep -Eq -- '--help\b|-h\b'; then
    usage
fi

run "rm -rf env"
run "python3.9 -m venv env"
run "source env/bin/activate" # pick up new env

run "env/bin/pip install --upgrade pip"
run "env/bin/pip install poetry"
run "source env/bin/activate" # pick up poetry

run "env/bin/poetry config virtualenvs.create false"
run "env/bin/poetry env use env/bin/python"
run "env/bin/poetry install"
run "env/bin/pip install -U 'aiohttp==3.8.1' 'pytest-aiohttp==1.0.4'"

echo "$(tput bold)now please run: source env/bin/activate$(tput sgr0)"
