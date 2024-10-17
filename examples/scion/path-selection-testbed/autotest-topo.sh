#!/bin/bash

for run in `seq 1 10`
do
    for strat in `seq 0 5`
    do
        rm -rf output
        python testbed-topo.py \
            --path-strategy $strat \
            --content-size 10240000 \
            --output-file runs/$RANDOM.log
    done
done
