#!/bin/bash -ue

docker run -it --rm -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:12.6
