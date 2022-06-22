#!/bin/bash -ue

set -eu

usage() {
    echo "usage: ${0##*/} [-h | --help] -a APP <stage | prod>" 1>&2
    echo "Deploys to heroku." 1>&2
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

APP=""
while getopts "a:" opt; do
    case "$opt" in
    a) APP="$OPTARG" ;;
    *) usage ;;
    esac
done
shift $((OPTIND - 1))

ENV="$1"

if [[ $ENV != "stage" && $ENV != "prod" || -z $APP ]]; then
    usage
fi

[[ $ENV == "stage" ]] && APP="$APP-staging"
TAG="registry.heroku.com/$APP/web"

run "DOCKER_BUILDKIT=0 docker buildx build --ulimit nofile=1024000:1024000 --platform linux/amd64 -t '$TAG' ."
run "docker push '$TAG'"
run "heroku container:release web --app '$APP'"
