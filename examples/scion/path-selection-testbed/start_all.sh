#!/bin/bash

echo "Starting the emulator..."
cd output && docker compose up -d

sleep 20

echo "Starting Node controls and dashboard..."
cd helper_scripts && ./start_nodes.sh

sleep 1

echo "Starting wireguard endpoints..."
cd helper_scripts && ./start_wireguard.sh

sleep 2

echo "Starting the server..."
cd server && ./start_server.sh

sleep 2

# And the rest..