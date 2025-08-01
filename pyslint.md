# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About PySlint

PySlint is a SystemVerilog linter built on top of pyslang that provides static analysis and coding standard checks for SystemVerilog code.

## Development Commands

### Running the Linter
- Navigate to `exec_dir/` and run `make` to execute the test suite
- Single file linting: `python3 ../py_src/pyslint.py -t <file.sv>`
- Example: `python3 ../py_src/pyslint.py -t ../sv_tests/test_sv_naming_01_p.sv`

### Configuration
- Main config file: `py_src/config.toml` - controls rule enablement and severity levels
- Each rule can be enabled/disabled and set to WARNING or ERROR severity

## Architecture

### Core Components
- `py_src/pyslint.py` - Main entry point and PySLint class that orchestrates linting
- `py_src/asfigo_linter.py` - Base linter class with logging and configuration handling
- `py_src/af_lint_rule.py` - Base class for all lint rules
- `py_src/rules/` - Directory containing individual rule implementations

### Rule System
- Rules auto-discover and register themselves as subclasses of `AsFigoLintRule`
- Each rule file in `py_src/rules/` implements a specific linting check
- Current rules include: encapsulation checks, variable naming consistency, no global variables, no generic mailbox usage

### Test Structure
- `sv_tests/` - Contains SystemVerilog test files for validation
- Test files follow naming convention: `_f.sv` for files that should fail, `_p.sv` for files that should pass
- Comprehensive test coverage includes naming conventions, SVA checks, UVM patterns, and compatibility rules

### Dependencies
- pyslang - SystemVerilog parser and AST library
- Python 3.x
- tomli for TOML configuration parsing
- string_utils for validation utilities

## Rule Categories
The linter supports various rule categories including:
- Naming conventions (NAME_* rules)
- SystemVerilog Assertions (SVA_* rules) 
- Class/Module structure (CL_*, REUSE_* rules)
- Performance optimizations (PERF_* rules)
- Compatibility checks (COMPAT_* rules)
- Functional constraints (FUNC_* rules)