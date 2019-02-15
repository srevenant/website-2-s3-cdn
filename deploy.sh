#!/bin/bash

if [ -z "$AWS_ACCESS_KEY_ID" -o -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "Missing AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY"
    exit 1
fi
docker-compose -f docker/deploy/docker-compose.yml build &&
    docker-compose -f docker/deploy/docker-compose.yml run --rm s3push
