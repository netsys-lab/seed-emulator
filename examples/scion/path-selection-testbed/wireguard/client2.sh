#!/bin/bash

INTERFACE=wg0
UAPI_SOCKET="/var/run/wireguard/${INTERFACE}.sock"
ADDRESS="10.78.0.3/24"
LISTEN_PORT=32000
SCION_ENDPOINT="1-101,[10.101.0.71]:32000"


PRIVATE_KEY_HEX=$(base64 -d client2.key | xxd -p -c 256)
SERVER_PUBLIC_KEY_HEX=$(base64 -d server.pub | xxd -p -c 256)

# Start wireguard-go
USE_SCION=1 USE_BATCH=0 ./wireguard-go $INTERFACE

# Configure interface
ip address add "$ADDRESS" dev "$INTERFACE"
ip link set up dev "$INTERFACE"
ip link set mtu 1280 dev "$INTERFACE"

cat << EOF | socat - UNIX-CONNECT:"$UAPI_SOCKET"
set=1
private_key=$PRIVATE_KEY_HEX
listen_port=32000
EOF

# Peer config (with set=1)
cat << EOF | socat - UNIX-CONNECT:"$UAPI_SOCKET"
set=1
public_key=$SERVER_PUBLIC_KEY_HEX
allowed_ip=10.78.0.0/24
scion_endpoint=$SCION_ENDPOINT
persistent_keepalive_interval=25
EOF
