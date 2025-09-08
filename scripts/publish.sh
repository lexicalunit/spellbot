#!/bin/bash -ue

usage() {
    echo "usage: ${0##*/} [-h | --help] <minor | major | patch>" 1>&2
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

if [[ $KIND != "major" && $KIND != "minor" && $KIND != "patch" ]]; then
    usage
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ $BRANCH != "main" ]]; then
    echo "error: you must be on the main branch to publish" 1>&2
    exit 1
fi

CHANGES="$(git status -su)"
if [[ -n $CHANGES ]]; then
    echo "error: can not publish when there are uncommitted changes" 1>&2
    exit 1
fi

REMOTE_CHANGES="$(git ls-remote origin -h refs/heads/master)"
if [[ -n $REMOTE_CHANGES ]]; then
    echo "error: can not publish when there are remote changes" 1>&2
    exit 1
fi

# bump the version in pyproject.toml
run "uv version --bump '$KIND'"

# fetch the version from pyproject.toml
VERSION="$(grep "^version" <pyproject.toml | cut -d= -f2 | sed 's/"//g;s/ //g;s/^/v/;')"

# promote unreleased changes in the changelog
echo "Updating CHANGELOG.md..."
OLD_CHANGELOG="$REPO_ROOT/CHANGELOG.md"
NEW_CHANGELOG="$REPO_ROOT/CHANGELOG-$VERSION.md"
cat >"$NEW_CHANGELOG" <<EOF
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

EOF

BODY_STARTED="false"
while IFS= read -r line; do
    if [[ $BODY_STARTED == "false" ]]; then
        if [[ $line == *"[Unreleased]"* ]]; then
            BODY_STARTED="true"
            echo "## [$VERSION](https://github.com/lexicalunit/spellbot/releases/tag/$VERSION) - $(date +'%Y-%m-%d')" >>"$NEW_CHANGELOG"
        fi
    else
        echo "$line" >>"$NEW_CHANGELOG"
    fi
done <"$OLD_CHANGELOG"
run "mv '$NEW_CHANGELOG' '$OLD_CHANGELOG'"

# build the release
run "rm -rf dist"
run "uv sync"
run "uv build"

# commit changes
run "git commit -am 'Release $VERSION'"

# make sure that the docker build works before publishing
TAG="lexicalunit/spellbot"
DD_VERSION="$(git rev-parse --short HEAD)"
run "DOCKER_BUILDKIT=0 docker buildx build --ulimit nofile=1024000:1024000 --build-arg DD_VERSION='$DD_VERSION' --platform linux/arm64 -t '$TAG' ."

# publish the release; assumes you've set up non-interactive publishing previously running:
# security add-generic-password -s spellbot -a "$USER" -w YOUR-PYPI-TOKEN
if ! uv publish -n --token "$(security find-generic-password -s spellbot -a "$USER" -w)"; then
    echo "error: publish command failed, see log for details" 1>&2
    run "git reset --hard HEAD~1"
    exit 1
fi

# tag and push changes to origin/main
run "git tag '$VERSION'"
run "git push --tags origin main"

# push updates to docker hub
run "docker push '$TAG'"
echo "Note: Any changes to README.md must be made manually at https://hub.docker.com/r/lexicalunit/spellbot ..."
