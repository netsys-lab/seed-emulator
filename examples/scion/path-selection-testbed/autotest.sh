#!/bin/bash

# latency 10 20 50 100
# bandwidth 5 10 50 100 200
scenarios=(

    '10,5,10240000' # 10MB
    '20,5,10240000'
    '50,5,10240000'
    '100,5,10240000'

    '10,10,10240000'
    '20,10,10240000'
    '50,10,10240000'
    '100,10,10240000'

    '10,50,102400000' # 100MB
    '20,50,102400000'
    '50,50,102400000'
    '100,50,102400000'

    '10,100,102400000'
    '20,100,102400000'
    '50,100,102400000'
    '100,100,102400000'

    '10,200,102400000'
    '20,200,102400000'
    '50,200,102400000'
    '100,200,102400000'
)

for scenario in "${scenarios[@]}"
do
    while IFS=',' read -r latency bandwidth content; do
        for links in `seq 1 20`
        do
            rm -rf output
            python3 testbed.py \
                --num-links $links \
                --link-latency $latency \
                --link-bandwidth $bandwidth \
                --content-size $content \
                --output-file runs/$RANDOM.log
        done
    done <<< "$scenario"
done
