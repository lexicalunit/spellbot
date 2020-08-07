#!/bin/bash

set -e

run() {
    echo -n $'\e[38;5;40m$\e[38;5;63m '
    echo -n "$@"
    echo $'\e[0m'
    eval "$@"
    return $?
}

REPO_ROOT="$(git rev-parse --show-toplevel)"
DOCS_ROOT="$REPO_ROOT/docs"
TMP_DIR=$(mktemp -d -t ci-XXXXXXXXXX)

cleanup() {
    run "rm -rf '$TMP_DIR'"
}
trap cleanup EXIT

run "cd '$TMP_DIR'"
run "git clone git@github.com:daattali/beautiful-jekyll.git"

run "cp -r beautiful-jekyll/_data '$DOCS_ROOT/'"
run "cp -r beautiful-jekyll/_includes '$DOCS_ROOT/'"
run "cp -r beautiful-jekyll/_layouts '$DOCS_ROOT/'"
run "cp -r beautiful-jekyll/assets/css '$DOCS_ROOT/assets/'"
run "cp -r beautiful-jekyll/assets/js '$DOCS_ROOT/assets/'"
run "cp beautiful-jekyll/_config.yml '$DOCS_ROOT/'"
run "cp beautiful-jekyll/beautiful-jekyll-theme.gemspec '$DOCS_ROOT/'"
run "cp beautiful-jekyll/feed.xml '$DOCS_ROOT/'"
run "cp beautiful-jekyll/Gemfile '$DOCS_ROOT/'"
run "cp beautiful-jekyll/LICENSE '$DOCS_ROOT/'"
run "cp beautiful-jekyll/staticman.yml '$DOCS_ROOT/'"
run "cp beautiful-jekyll/tags.html '$DOCS_ROOT/'"
