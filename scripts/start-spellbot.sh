#!/bin/bash

# hack: b/c playwright looks for exe in /.cache/ms-playwright/...
ln -s root/.cache .

/start.sh spellbot
