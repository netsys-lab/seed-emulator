#!/bin/bash

for run in `seq 1 20`
do
    for num_paths in `seq 1 10`
    do
        rm -rf output
        python bwtest-topo.py \
            --num-paths $num_paths \
            --content-size 10240000 \
            --output-file runs/$RANDOM-$RANDOM-$RANDOM.log
    done
done
