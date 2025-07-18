# Design names and top-level modules
#DESIGNS = or1200/buggy-or1200 hackdac2018 hackdac2019 opentitan
DESIGN_NAMES = or1200 hackdac2018 hackdac2019 opentitan
#DESIGNS = "or1200/buggy-or1200" hackdac2018 hackdac2019 opentitan
DESIGNS = or1200 hackdac2018 hackdac2019 opentitan
TOP_or1200 = or1200_top.v
TOP_hackdac2018 = hackdac2018_top.v
TOP_hackdac2019 = hackdac2019_top.v
TOP_opentitan = ibex_top.v

# Paths
DESIGN_PATH = designs/benchmarks/verification-benchmarks/
RESULTS_PATH = results

# Create results directories
.PHONY: init
init:
	mkdir -p $(RESULTS_PATH)
	@for d in $(DESIGNS); do \
		mkdir -p $(RESULTS_PATH)/$$d/explore_cache; \
		mkdir -p $(RESULTS_PATH)/$$d/explore_nocache; \
		mkdir -p $(RESULTS_PATH)/$$d/query_cache; \
		mkdir -p $(RESULTS_PATH)/$$d/query_nocache; \
		mkdir -p $(RESULTS_PATH)/$$d/assertion_check; \
		mkdir -p $(RESULTS_PATH)/$$d/assertion_merge; \
	done

# Run end-to-end 24-hour exploration (adjust explore_time for testing)
.PHONY: explore
explore:
	@for d in $(DESIGNS); do \
		echo "Running exploration on $$d (no cache)..."; \
		python3 -m main 1 $(DESIGN_PATH)/$$d/$(TOP_$$d) \
			--explore_time 86400 \
			--use_cache False > $(RESULTS_PATH)/$$d/explore_nocache/out.txt; \
		echo "Running exploration on $$d (with cache)..."; \
		python3 -m main 1 $(DESIGN_PATH)/$$d/$(TOP_$d) \
			--explore_time 86400 \
			--use_cache true > $(RESULTS_PATH)/$$d/explore_cache/out.txt; \
	done

# Run assertion violation check (6 cycles)
.PHONY: assert-check
assert-check:
	@for d in or1200 hackdac2018 hackdac2019; do \
		echo "Running assertion check on $$d..."; \
		python3 -m main 6 $(DESIGN_PATH)/$$d/$(TOP_$$d) \
			--check_assertions \
			--use_cache true > $(RESULTS_PATH)/$$d/assertion_check/out.txt; \
	done

# Run assertion violation with merge queries enabled
.PHONY: merge-queries
merge-queries:
	@for d in or1200 hackdac2018 hackdac2019; do \
		echo "Running merge query analysis on $$d..."; \
		python3 -m main 6 $(DESIGN_PATH)/$$d/$(TOP_$$d) \
			--check_assertions \
			--use_cache true \
			--use_merge_queries true > $(RESULTS_PATH)/$$d/assertion_merge/out.txt; \
	done

# Run query cache vs no cache comparisons
.PHONY: cache-compare
cache-compare:
	@for d in $(DESIGNS); do \
		echo "Running cache comparison on $$d (no cache)..."; \
		python3 -m main 1 $(DESIGN_PATH)/$$d/$$(TOP_$$d) \
			--explore_time 3600 \
			--use_cache false > $(RESULTS_PATH)/$$d/query_nocache/out.txt; \
		echo "Running cache comparison on $$d (with cache)..."; \
		python3 -m main 1 $(DESIGN_PATH)/$$d/$(TOP_$$d) \
			--explore_time 3600 \
			--use_cache true > $(RESULTS_PATH)/$d/query_cache/out.txt; \
	done

# Run cache analysis manually between property runs
.PHONY: analyze-cache
analyze-cache:
	python3 -m cache_analysis --cache_path cache.rdb --output_dir $(RESULTS_PATH)/cache_analysis
