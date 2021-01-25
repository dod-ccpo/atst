# syntax = docker/dockerfile:1.0-experimental

FROM ubuntu:bionic

RUN --mount=type=secret,id=mynetrc,dst=/.netrc cat /.netrc
RUN cat /.netrc
