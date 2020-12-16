#!/bin/bash

set -eu

usage() {
    echo "usage: ${0##*/} <stage|prod> <api|bot|dash> [-h|--help]" 1>&2
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

ENV="$1"
if [[ "$ENV" != "stage" && "$ENV" != "prod" ]]; then
    usage
fi

APP="lexicalunit"
REDIRECT_URI="https://lexicalunit-spelldash"
SPELLAPI_BASE_URI="https://lexicalunit-spellapi"
DOCKERFILE="Dockerfile"
WORKING_DIR=""

PART="$2"
case $PART in
    api)
        APP="$APP-spellapi"
        DOCKERFILE="$DOCKERFILE.api"
        WORKING_DIR="."
        ;;

    bot)
        APP="$APP-spellbot"
        DOCKERFILE="$DOCKERFILE.bot"
        WORKING_DIR="."
        ;;

    dash)
        APP="$APP-spelldash"
        DOCKERFILE="$DOCKERFILE.dash"
        WORKING_DIR="dash"
        ;;

    *)
        usage
        ;;
esac

if [[ "$ENV" == "stage" ]]; then
    APP="$APP-staging"
    REDIRECT_URI="${REDIRECT_URI}-staging"
    SPELLAPI_BASE_URI="${SPELLAPI_BASE_URI}-staging"
    CLIENT_ID="769702807166386208"
elif [[ "$ENV" == "prod" ]]; then
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
    '$WORKING_DIR''
run "docker push $TAG"
run "heroku container:release web --app $APP"
