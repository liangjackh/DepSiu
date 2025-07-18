#!/bin/bash
python3 -m main 1 designs/or1200/or1200_top.v \
  --explore_time 3600 \
  --use_cache false > results/or1200/query_nocache/out.txt
