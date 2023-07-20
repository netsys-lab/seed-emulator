#!/bin/bash

paths1=$(docker exec -it as105h-Operator-10.105.0.71 /bin/zsh -c "scion showpaths 1-106")

echo "$paths1" | grep -q "no path found"

# If grep found the string, it will return 0, so we check if the exit code ($?) is 0
if [ $? -eq 0 ]
then
  echo "Error: no path found"
  exit 1
fi

paths2=$(docker exec -it as106h-Machine-10.106.0.71 /bin/zsh -c "scion showpaths 1-105")

echo "$paths2" | grep -q "no path found"

if [ $? -eq 0 ]
then
  echo "Error: no path found"
  exit 1
fi

echo "starting dmtp server"
docker exec -d as106h-Machine-10.106.0.71 /bin/zsh -c "cd /dmtp && ./dmtp > /dev/null 2>&1 &"
sleep 2
echo "starting dmtp client"
docker exec -d as105h-Operator-10.105.0.71 /bin/zsh -c "cd /dmtp && ./dmtp > /dev/null 2>&1 &"


sleep 10

docker exec -it as105h-Operator-10.105.0.71 /bin/zsh -c "ping 10.72.0.1 -c 1"



