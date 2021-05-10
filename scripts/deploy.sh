#!/bin/bash

set -eu

usage() {
    echo "usage: ${0##*/} [-h|--help] [-n] <stage|prod> <api|bot|dash>" 1>&2
    echo "Deploys to heroku. Use -n to build only, no deploy." 1>&2
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

DEPLOY="yes"
while getopts "n" opt; do
    case "$opt" in
    n) DEPLOY="no" ;;
    *) usage ;;
    esac
done
shift $((OPTIND - 1))

ENV="$1"
if [[ $ENV != "stage" && $ENV != "prod" ]]; then
    usage
fi

APP="lexicalunit"
REDIRECT_URI="https://lexicalunit-spelldash"
SPELLAPI_BASE_URI="https://lexicalunit-spellapi"
DOCKERFILE="Dockerfile"

PART="$2"
case $PART in
bot)
    APP="$APP-spellbot"
    DOCKERFILE="$DOCKERFILE.bot"
    ;;

dash)
    APP="$APP-spelldash"
    DOCKERFILE="$DOCKERFILE.dash"
    ;;

*)
    usage
    ;;
esac

if [[ $ENV == "stage" ]]; then
    APP="$APP-staging"
    REDIRECT_URI="${REDIRECT_URI}-staging"
    SPELLAPI_BASE_URI="${SPELLAPI_BASE_URI}-staging"
    CLIENT_ID="769702807166386208"
elif [[ $ENV == "prod" ]]; then
    CLIENT_ID="725510263251402832"
fi

NODE_ENV="production"
REDIRECT_URI="${REDIRECT_URI}.herokuapp.com/login"
SPELLAPI_BASE_URI="${SPELLAPI_BASE_URI}.herokuapp.com/"
TAG="registry.heroku.com/$APP/web"

run $'docker build \
    -t "'$TAG'" \
    -f "'$DOCKERFILE'" \
    --build-arg REACT_APP_REDIRECT_URI="'$REDIRECT_URI'" \
    --build-arg REACT_APP_CLIENT_ID="'$CLIENT_ID'" \
    --build-arg REACT_APP_SPELLAPI_BASE_URI="'$SPELLAPI_BASE_URI'" \
    --build-arg NODE_ENV="'$NODE_ENV'" \
    .'

if [[ $DEPLOY == "yes" ]]; then
    run "docker push $TAG"
    run "heroku container:release web --app $APP"
fi
