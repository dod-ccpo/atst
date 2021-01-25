#! /bin/bash
docker build \
    -t nginx:rhel-8.2 \
    -f nginx.Dockerfile \
    --build-arg IMAGE=atst:rhel-py \
    .