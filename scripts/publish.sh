#!/bin/bash

set -eu

usage() {
    echo "usage: ${0##*/} [minor|major|patch] [-h|--help]" 1>&2
    echo "Bumps the minor, major, or patch version and releases the package." 1>&2
    exit 1
}

run() {
    echo -n $'\e[38;5;40m$\e[38;5;63m '
    echo -n "$@"
    echo $'\e[0m'
    eval "$@"
    return $?
}


if echo "$*" | grep -Eq -- '--help\b|-h\b' || [[ -z $1 ]]; then
    usage
fi

KIND="$1"

if [[ "$KIND" != "major" && "$KIND" != "minor" && "$KIND" != "patch" ]]; then
    usage
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ $BRANCH != "master" ]]; then
    echo "error: you must be on the master branch to publish" 1>&2
    exit 1
fi

CHANGES="$(git status -su)"
if [[ -n "$CHANGES" ]]; then
    echo "error: can not publish when there are uncomitted changes" 1>&2
    exit 1
fi

# bump the version in pyproject.toml
run "poetry version '$KIND'"

# run tests to ensure the build is good
run "tox"

# fetch the version from pyproject.toml
VERSION="$(grep "^version" < pyproject.toml | cut -d= -f2 | sed 's/"//g;s/ //g;s/^/v/;')"

# build the release
run "poetry build"

# commit changes
run "git commit -am 'Release $VERSION'"

# publish the release; assumes you've set up non-interactive publishing by
# previously having run: `poetry config pypi-token.pypi "YOUR-PYPI-TOKEN-GOES-HERE"`
if ! poetry publish -n; then
    echo "error: publish command failed, see log for details" 1>&2
    run "git reset --hard HEAD~1"
    exit 1
fi

# tag and push changes to origin/master
run "git tag '$VERSION'"
run "git push --tags origin master"
