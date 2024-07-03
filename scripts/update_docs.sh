#!/bin/bash -ue

WORKDIR="$(mktemp -d)"
REPO_ROOT="$(git rev-parse --show-toplevel)"

cleanup() {
    rm -rf "$WORKDIR"
}

trap cleanup EXIT

cd "$WORKDIR"

# download the latest version of beautiful-jekyll
wget https://github.com/daattali/beautiful-jekyll/archive/refs/heads/master.zip
unzip master.zip
cd beautiful-jekyll-master

# delete cruft
rm aboutme.md CHANGELOG.md screenshot.png index.html 404.html .gitignore README.md
rm -rf _posts/* assets/img/* .github/*

# copy over the new files
rsync -ac . "$REPO_ROOT/docs/"
