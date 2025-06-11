#!/bin/bash

INTERFACE=wg0
UAPI_SOCKET="/var/run/wireguard/${INTERFACE}.sock"
ADDRESS="10.78.0.1/24"
LISTEN_PORT=32000


PRIVATE_KEY_HEX=$(base64 -d server.key | xxd -p -c 256)
CLIENT1_PUBLIC_KEY_HEX=$(base64 -d client1.pub | xxd -p -c 256)
CLIENT2_PUBLIC_KEY_HEX=$(base64 -d client2.pub | xxd -p -c 256)

# Start wireguard-go
# USE_SCION=1 USE_BATCH=1 ./wireguard-go $INTERFACE

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
public_key=$CLIENT1_PUBLIC_KEY_HEX
allowed_ip=10.78.0.2/32
allowed_ip=172.16.0.0/24
EOF

cat << EOF | socat - UNIX-CONNECT:"$UAPI_SOCKET"
set=1
public_key=$CLIENT2_PUBLIC_KEY_HEX
allowed_ip=10.78.0.3/32
allowed_ip=172.18.0.0/24
EOF

ip route add 172.16.0.0/24 via 10.78.0.2 dev wg0
ip route add 172.18.0.0/24 via 10.78.0.3 dev wg0
iperf3 -s -p 4601 -D
iperf3 -s -p 4602 -D

