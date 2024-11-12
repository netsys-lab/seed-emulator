#!/bin/bash

for run in `seq 1 20`
do
    for strat in `seq 0 8`
    do
        rm -rf output
        python testbed-topo.py \
            --path-strategy $strat \
            --content-size 51200000 \
            --num-nodes 1 \
            --output-file runs/$RANDOM.log
    done
done
