#!/bin/bash -ue
hex=$(openssl rand -hex 33)
hex=${hex:0:65}
echo "$hex"
