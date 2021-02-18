#! /bin/bash

env DOCKER_BUILDKIT=1 docker build \
    -t atat:rhel-py \
    -f python.Dockerfile \
    --build-arg IMAGE=$REGISTRY_NAME/rhelubi:8.3 \
    --secret id=redhat_username,src=redhat_username.secret \
    --secret id=redhat_password,src=redhat_password.secret \
    .
