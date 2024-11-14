#!/bin/bash

# completelyRandomStrat          = 0
# firstFreeRandomStrat           = 1
# firstFreeShortestStrat         = 2
# firstFreeMostDisjointStrat     = 4
# singleShortestPathStrat        = 6
# firstFreeLowestLatency         = 7
# firstFreeHighestBandwidth      = 8
# firstFreeLowestLatencySubvalue = 9

for run in `seq 1 20`
do
    for strat in 0 1 2 4 6 7 8 9
    do
        rm -rf output
        python testbed-topo.py \
            --path-strategy $strat \
            --content-size 10240000 \
            --num-nodes 1 \
            --output-file runs/$RANDOM.log
    done
done
