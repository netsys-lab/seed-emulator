# MPTCP in SEED

Adaptions to Dockerfile for host containers

```Dockerfile 
# Replace FROM $HASH with this
FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
COPY sources.list /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends apt-transport-https ca-certificates
# Install software packages inside the container
RUN apt-get update  \
    && apt-get -y install  \
    iputils-ping \
    iproute2  \
    net-tools \
    dnsutils  \
    mtr-tiny  \
    nano      \
    && apt-get clean
```