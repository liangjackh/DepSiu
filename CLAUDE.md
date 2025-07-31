# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

DepSiu is a symbolic execution engine for Verilog designs that supports both traditional Verilog parsing (via PyVerilog) and SystemVerilog parsing (via pyslang). The tool performs symbolic execution on hardware designs to explore execution paths and detect assertion violations.

## Core Architecture

### Main Components

- **`main.py`**: Entry point that orchestrates the symbolic execution process
- **`engine/`**: Core execution engine components
  - `execution_engine.py`: Primary execution engine with both traditional and SystemVerilog support
  - `execution_manager.py`: Manages execution state and path exploration  
  - `symbolic_state.py`: Maintains symbolic state during execution
- **`helpers/`**: Utility modules for parsing and conversion
  - `slang_helpers.py`: SystemVerilog AST visitors and symbolic execution helpers
  - `rvalue_parser.py` & `rvalue_to_z3.py`: Expression parsing and Z3 conversion
- **`strategies/`**: Search strategies for path exploration
  - `dfs.py`: Depth-first search for traditional Verilog
  - `dfs_slang.py`: DFS implementation for SystemVerilog via pyslang

### Execution Modes

The tool operates in two main modes:
1. **Traditional Verilog**: Uses PyVerilog for parsing and analysis
2. **SystemVerilog**: Uses pyslang library for more comprehensive SystemVerilog support (enabled with `--sv` flag)

## Common Commands

### Basic Execution
```bash
# Run symbolic execution on a single Verilog file for N cycles
python3 -m main <num_cycles> <verilog_file>.v > out.txt

# Run with SystemVerilog support
python3 -m main <num_cycles> <file>.sv --sv > out.txt

# Run with caching enabled
python3 -m main <num_cycles> <file>.v --use_cache > out.txt
```

### Using the Makefile
```bash
# Initialize result directories
make init

# Run 24-hour exploration on all benchmark designs
make explore

# Run assertion violation checks (6 cycles)
make assert-check

# Run assertion checks with merge queries
make merge-queries

# Compare cache vs no-cache performance
make cache-compare

# Analyze cache performance
make analyze-cache
```

### Quick Testing
```bash
# Basic test run
./run.sh

# Test with SystemVerilog and caching
./test.sh
```

## Design Benchmarks

The repository includes several hardware design benchmarks in `designs/benchmarks/`:

- **hackatdac18/**: PULPissimo RISC-V SoC from Hack@DAC 2018
- **hackatdac19/**: Ariane RISC-V core from Hack@DAC 2019  
- **hackatdac21/**: Hack@DAC 2021 challenge design
- **or1200/**: OpenRISC 1200 processor (including buggy version)
- **verification-benchmarks/**: Additional test designs

## Key Features

### Caching System
- Redis-based query caching to improve performance on repeated runs
- Enable with `--use_cache` flag
- Requires Redis server running on localhost:6379

### Path Exploration
- Configurable exploration time limits (`--explore_time` in seconds)
- Multiple search strategies (DFS-based)
- Branch point detection and path enumeration

### Assertion Checking
- Built-in assertion violation detection
- Support for merge queries to optimize assertion checking
- Configurable cycle limits for bounded model checking

## Dependencies

- **PyVerilog**: Traditional Verilog parsing and analysis
- **pyslang**: SystemVerilog parsing and compilation
- **Z3**: SMT solver for symbolic execution
- **Redis**: Optional caching backend
- **Standard libraries**: time, threading, logging, etc.

## Configuration

The tool supports various command-line options:
- `--sv`: Enable SystemVerilog parser
- `--use_cache`: Enable Redis caching
- `--explore_time`: Set exploration time limit in seconds
- `--check_assertions`: Enable assertion violation checking
- `--use_merge_queries`: Enable merge query optimization
- `-I/--include`: Include paths for preprocessing
- `-D`: Macro definitions
- `--debug`: Enable debug mode