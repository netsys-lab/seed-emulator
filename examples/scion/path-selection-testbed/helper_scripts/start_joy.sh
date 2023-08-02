#!/bin/bash

docker exec -d as105h-Operator-10.105.0.71 /bin/zsh -c "cd /server && python3 joy_sender.py > /dev/null 2>&1 &"

docker exec -d as106h-Machine-10.106.0.71 /bin/zsh -c "cd /dmtp && python3 joy_receiver.py  > /dev/null 2>&1 &"
