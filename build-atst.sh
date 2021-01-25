#! /bin/bash

docker build \
    -t atst:1.0.0 \
    --build-arg IMAGE=atst:rhel-py \
    .


docker build -t nginx:rhel-8.2 - < nginx.Dockerfile --build-arg IMAGE=<base-image-tag>
