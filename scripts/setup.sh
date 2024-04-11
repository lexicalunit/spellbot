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

ENVDIR=".venv"

run "rm -rf $ENVDIR"
run "python3.12 -m venv $ENVDIR"
run "source $ENVDIR/bin/activate" # pick up new env

run "$ENVDIR/bin/pip install -U pip"
run "$ENVDIR/bin/pip install -U poetry"
run "source $ENVDIR/bin/activate" # pick up poetry

run "$ENVDIR/bin/poetry config virtualenvs.create false"
run "$ENVDIR/bin/poetry env use $ENVDIR/bin/python"
run "$ENVDIR/bin/poetry install"

echo "$(tput bold)now please run: source $ENVDIR/bin/activate$(tput sgr0)"
