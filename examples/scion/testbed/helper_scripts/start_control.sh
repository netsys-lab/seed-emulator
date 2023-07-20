#!/bin/bash

echo "starting mosquitto"
docker exec -d as106h-Machine-10.106.0.71 /bin/zsh -c "mosquitto > /dev/null 2>&1 &"

sleep 2

brs=("as101r-br0-10.101.0.254" "as101r-br0-10.101.0.254")
brs+=("as102r-br0-10.102.0.254" "as102r-br0-10.102.0.254")
brs+=("as103r-br0-10.103.0.254" "as103r-br0-10.103.0.254")
brs+=("as105r-br0-10.105.0.254" "as105r-br0-10.105.0.254")
brs+=("as104r-br0-10.104.0.254" "as104r-br0-10.104.0.254")
brs+=("as106r-br0-10.106.0.254" "as106r-br0-10.106.0.254")

for br in "${brs[@]}"
do
    echo "starting $br"
    docker exec -d $br /bin/zsh -c "cd /node && python3 node_control.py > /dev/null 2>&1 &"
done

echo "starting dash"

# docker exec -d as105h-Operator-10.105.0.71 /bin/zsh -c "cd /server && python3 dashboard.py > /dev/null 2>&1 &"