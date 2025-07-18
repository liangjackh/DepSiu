#!/bin/bash
python3 -m main 1 designs/or1200/or1200_top.v \
  --explore_time 86400 \
  --use_cache true > results/or1200/explore_cache/out.txt
