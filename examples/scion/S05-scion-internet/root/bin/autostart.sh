#!/bin/bash

until [ -e /run/shm/dispatcher/default.sock ]; do sleep 1; done
sleep 10
addr="$(scion address):1337"
echo "connect to capacityseeker at ${addr}"
capacityseeker -local ${addr} > /dev/null
