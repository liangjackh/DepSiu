#!/bin/bash
python3 -m main 6 designs/or1200/or1200_top.v \
  --check_assertions \
  --use_cache true > results/or1200/assertion_check/out.txt
