"""This file is the entrypoint of the execution."""
from __future__ import absolute_import
from __future__ import print_function
import pyverilog
import z3
from z3 import Solver, Int, BitVec, Context, BitVecSort, ExprRef, BitVecRef, If, BitVecVal, And
from pyverilog.vparser.parser import parse
from pyverilog.vparser.ast import Description, ModuleDef, Node, IfStatement, SingleStatement, And, Constant, Rvalue, Plus, Input, Output
from pyverilog.vparser.ast import WhileStatement, ForStatement, CaseStatement, Block, SystemCall, Land, InstanceList, IntConst, Partselect, Ioport
from pyverilog.vparser.ast import Value, Reg, Initial, Eq, Identifier, Initial,  NonblockingSubstitution, Decl, Always, Assign, NotEql, Case
from pyverilog.vparser.ast import Concat, BlockingSubstitution, Parameter, StringConst, Wire, PortArg
import sys
import os
from optparse import OptionParser
from typing import Optional
import random, string
import time
from itertools import product
import logging
import gc
from pyverilog.vparser.preprocessor import preprocess
from engine.execution_manager import ExecutionManager
from engine.symbolic_state import SymbolicState
from helpers.rvalue_parser import tokenize, parse_tokens, evaluate
from strategies.dfs import DepthFirst
from engine.execution_engine import ExecutionEngine
from pyverilog.dataflow.dataflow_analyzer import VerilogDataflowAnalyzer
from pyverilog.dataflow.optimizer import VerilogDataflowOptimizer
from pyverilog.dataflow.graphgen import VerilogGraphGenerator
import pygraphviz as pgv
import pyslang as ps
from helpers.slang_helpers import SlangSymbolVisitor, SlangNodeVisitor, SymbolicDFS
import redis
import threading
import time

gc.collect()

with open('errors.log', 'w'):
    pass
logging.basicConfig(filename='errors.log', level=logging.DEBUG)
logging.debug("Starting over")


INFO = "Verilog Symbolic Execution Engine"
VERSION = pyverilog.__version__
USAGE = "Usage: python3 -m main <num_cycles> <verilog_file>.v > out.txt"
    
def timeout_exit():
    """This only happens when the timer runs out."""
    print("Execution time limit exceeded. Exiting.")
    sys.exit(1)

def showVersion():
    print(INFO)
    print(VERSION)
    print(USAGE)
    sys.exit()
    
def main():
    """Entrypoint of the program."""
    engine: ExecutionEngine = ExecutionEngine()
    search_strategy: DepthFirst = DepthFirst()
    optparser = OptionParser()
    optparser.add_option("-v", "--version", action="store_true", dest="showversion",
                         default=False, help="Show the version")
    optparser.add_option("-I", "--include", dest="include", action="append",
                            default=["designs/benchmarks/verification-benchmarks/"],
                         help="Include path")
    optparser.add_option("-D", dest="define", action="append",
                         default=[], help="Macro Definition")
    optparser.add_option("-B", "--debug", action="store_true", dest="showdebug", help="Debug Mode")
    optparser.add_option("-t", "--top", dest="topmodule",
                         default="top", help="Top module, Default=top")
    optparser.add_option("--nobind", action="store_true", dest="nobind",
                         default=False, help="No binding traversal, Default=False")
    optparser.add_option("--noreorder", action="store_true", dest="noreorder",
                         default=False, help="No reordering of binding dataflow, Default=False")
    optparser.add_option("-o", "--output", dest="outputfile",
                         default="out.png", help="Graph file name, Default=out.png")
    optparser.add_option("-s", "--search", dest="searchtarget", action="append",
                         default=[], help="Search Target Signal")
    optparser.add_option("--sv", action="store_true", dest="sv",
                         default=False, help="enable SystemVerilog parser")
    optparser.add_option("--walk", action="store_true", dest="walk",
                         default=False, help="Walk contineous signals, Default=False")
    optparser.add_option("--identical", action="store_true", dest="identical",
                         default=False, help="# Identical Laef, Default=False")
    optparser.add_option("--step", dest="step", type='int',
                         default=1, help="# Search Steps, Default=1")
    optparser.add_option("--reorder", action="store_true", dest="reorder",
                         default=False, help="Reorder the contineous tree, Default=False")
    optparser.add_option("--delay", action="store_true", dest="delay",
                         default=False, help="Inset Delay Node to walk Regs, Default=False")
    optparser.add_option("--use_cache", action="store_true", dest="use_cache",
                         default=False, help="Use the query caching, Default=False")
    optparser.add_option("--explore_time", help="Time to explore in seconds", dest="explore_time")
    (options, args) = optparser.parse_args()


    num_cycles = args[0]
    filelist = args[1:]

    if options.showversion:
        showVersion()
    
    if options.use_cache:
        engine.cache = redis.Redis(host='localhost', port=6379, db=0)

    timer = None
    if options.explore_time:
        timer = threading.Timer(int(options.explore_time), timeout_exit)
        timer.start()

    if options.showdebug:
        engine.debug = True


    for f in filelist:
        if not os.path.exists(f):
            print(f"file: {f}")
            raise IOError("file not found: " + f)

    # If more than one file, create a .F file listing all files
    if len(filelist) > 1:
        flist_path = "filelist.F"
        with open(flist_path, "w") as flist:
            for f in filelist:
                flist.write(f + "\n")
        filelist = [flist_path]

    if len(filelist) == 0:
        showVersion()
    
    if options.sv:
        start = time.process_time()
        driver = ps.Driver()
        driver.addStandardArgs()
        driver.processCommandFiles(filelist[0], True, True)
        driver.processOptions()
        driver.parseAllSources()

        #ast = ps.ASTContext()
        #ast_comp = ast.getCompilation()
        #comp = ps.Compilation()
        #ast_ctx = ps.ASTContext(comp)
        #print(f"ast_ctx: {type(ast_ctx)}")

        compilation = driver.createCompilation()
        definitionLookupRes = compilation.DefinitionLookupResult()
        print(f"parse name: {type(compilation.parseName('top'))}")
        print(f"configRoot: {definitionLookupRes.configRoot}")
        print(f"defaultLibrary: {compilation.defaultLibrary}")

        printer = ps.SyntaxPrinter()
        trees = driver.syntaxTrees
        for tree in trees:
            printer.print(tree)
        print(f"[print tree end] ............................")
        root = trees[0].root
        for item in trees:
            print(f"syntaxTreeNode: {item}")
        modules =  compilation.getDefinitions() # list[DefinitionSymbol]
        print(f"modules type: {type(modules)}")
        for item in modules:
            print(f"module type: {type(item)}")
            print(f"{item.name} hierachicalPath: {item.hierarchicalPath}")
            print(f"{item.name} lexicalPath: {item.lexicalPath}")
            print(f"{item.name}  syntax type: {type(item.syntax)}")
        #always_blocks = compilation.getProceduralBlocks()
        #for item in always_blocks:
        #    print(f"always block: {type(item)}")
        successful_compilation = driver.reportCompilation(compilation, True)
        print(f"modules:{modules}")
        print(f"successful_compilation: {successful_compilation}")
        if successful_compilation:
            print(f"reportMacros:")
            driver.reportMacros()
            my_visitor_for_symbol = SymbolicDFS(num_cycles)
            print(f"[main]my_visitor_for_symbol: {my_visitor_for_symbol}")
            symbol_visitor = SlangSymbolVisitor(num_cycles)
            engine.execute_sv(my_visitor_for_symbol, modules, None, num_cycles)

            #module: DefinitionSymbol
            for module in modules: 
                symbol_visitor.visit(module)
            print(f"symbol_visitor branches:{symbol_visitor.branch_points}")
            print(f"symbol_visitor paths:{symbol_visitor.paths}")
            
        end = time.process_time()
        print(f"Elapsed time {end - start}")
        if timer:
            timer.cancel()
        exit()

        # for item in tree.root.members:
        #     print(item)
        #     print(type(item))
            # for item2 in item.members:
            #     print(item2)
            #     print(type(item2))
        # print(mod.header.name.value)
        # print(mod.members[0])
        # print(mod.members[1])

    text = preprocess(filelist, include=options.include, define=options.define)
    if options.include:
        for filename in os.listdir(options.include[0]):
            f = os.path.join(options.include[0], filename)
            # checking if it is a file
            if os.path.isfile(f):
                print(f)
                filelist.append(str(f))
        ast, directives = parse(filelist,
                            preprocess_include=options.include,
                            preprocess_define=options.define)
    else:
        ast, directives = parse(filelist, preprocess_define=options.define)
    # analyzer = VerilogDataflowAnalyzer(filelist, options.topmodule,
    #                                    noreorder=options.noreorder,
    #                                    nobind=options.nobind,
    #                                    preprocess_include=options.include,
    #                                    preprocess_define=options.define)
    # analyzer.generate()

    # directives = analyzer.get_directives()
    # terms = analyzer.getTerms()
    # binddict = analyzer.getBinddict()

    # optimizer = VerilogDataflowOptimizer(terms, binddict)

    # optimizer.resolveConstant()
    # resolved_terms = optimizer.getResolvedTerms()
    # resolved_binddict = optimizer.getResolvedBinddict()
    # constlist = optimizer.getConstlist()

    # graphgen = VerilogGraphGenerator(options.topmodule, terms, binddict,
    #                                  resolved_terms, resolved_binddict, constlist, options.outputfile)

    # for target in options.searchtarget:
    #     graphgen.generate(target, walk=options.walk, identical=options.identical,
    #                       step=options.step)

    # graphgen.draw()

    #ast.show()
    #print(ast.children()[0].definitions)

    description: Description = ast.children()[0]
    top_level_module: ModuleDef = description.children()[0]
    modules = description.definitions
    start = time.process_time()
    engine.execute(top_level_module, modules, None, directives, num_cycles)
    end = time.process_time()
    if options.use_cache and hasattr(engine, "cache"):
        try:
            engine.cache.save()
            print("Redis cache saved to RDB.")
        except Exception as e:
            print(f"Failed to save Redis cache: {e}")
    print(f"Elapsed time {end - start}")

if __name__ == '__main__':
    main()



#     def seen_all_cases(self, m: ExecutionManager, bit_index: int, nested_ifs: int) -> bool:
#         """Checks if we've seen all the cases for this index in the bit string.
#         We know there are no more nested conditionals within the block, just want to check 
#         that we have seen the path where this bit was turned on but the thing to the left of it
#         could vary."""
#         # first check if things less than me have been added.
#         # so index 29 shouldnt be completed before 30
#         for i in range(bit_index + 1, 32):
#             if not i in m.completed:
#                 return False
#         count = 0
#         seen = m.seen
#         #print(seen)
#         for path in seen[m.curr_module]:
#             if path[bit_index] == '1':
#                 count += 1
#         if count >  2 * nested_ifs:
#             return True
#         return False

#     def module_count(self, m: ExecutionManager, items) -> None:
#         """Traverse a top level module and count up the instances of each type of module."""
#         if isinstance(items, Block):
#             items = items.statements
#         if hasattr(items, '__iter__'):
#             for item in items:
#                 if isinstance(item, InstanceList):
#                     if item.module in m.instance_count:
#                         m.instance_count[item.module] += 1
#                     else:
#                         m.instance_count[item.module] = 1
#                     self.module_count(m, item.instances)
#                 if isinstance(item, Block):
#                     self.module_count(m, item.items)
#                 elif isinstance(item, Always):
#                     self.module_count(m, item.statement)             
#                 elif isinstance(item, Initial):
#                     self.module_count(m, item.statement)
#         elif items != None:
#                 if isinstance(items, InstanceList):
#                     if items.module in m.instance_count:
#                         m.instance_count[items.module] += 1
#                     else:
#                         m.instance_count[items.module] = 1
#                     self.module_count(m, items.instances)

    

#     def populate_child_paths(self, manager: ExecutionManager) -> None:
#         """Populates child path codes based on number of paths."""
#         for child in manager.child_num_paths:
#             manager.child_path_codes[child] = []
#             if manager.piece_wise:
#                 manager.child_path_codes[child] = []
#                 for i in manager.child_range:
#                     manager.child_path_codes[child].append(to_binary(i))
#             else:
#                 for i in range(manager.child_num_paths[child]):
#                     manager.child_path_codes[child].append(to_binary(i))

#     def populate_seen_mod(self, manager: ExecutionManager) -> None:
#         """Populates child path codes but in a format to keep track of corresponding states that we've seen."""
#         for child in manager.child_num_paths:
#             manager.seen_mod[child] = {}
#             for i in range(manager.child_num_paths[child]):
#                 manager.seen_mod[child][(to_binary(i))] = {}


#     def piece_wise_execute(self, ast: ModuleDef, manager: Optional[ExecutionManager], modules) -> None:
#         """Drives symbolic execution piecewise when number of paths is too large not to breakup. 
#         We break it up to avoid the memory blow up."""

#         self.module_depth += 1
#         manager.piece_wise = True
#         state: SymbolicState = SymbolicState()
#         if manager is None:
#             manager: ExecutionManager = ExecutionManager()
#             manager.debugging = False
#         modules_dict = {}
#         for module in modules:
#             modules_dict[module.name] = module
#             manager.child_path_codes[module.name] = to_binary(0)
#             manager.seen_mod[module.name] = {}
#             sub_manager = ExecutionManager()
#             manager.names_list.append(module.name)
#             self.init_run(sub_manager, module)
#             self.module_count(manager, module.items)
#             manager.child_num_paths[module.name] = sub_manager.num_paths
#             manager.config[module.name] = to_binary(0)
#             state.store[module.name] = {}

#         total_paths = sum(manager.child_num_paths.values())
#         print(total_paths)
#         manager.piece_wise = True
#         #TODO: things piecewise, say 10,000 at a time.
#         for i in range(0, total_paths, 10000):
#             manager.child_range = range(i*10000, i*10000+10000)
#             self.populate_child_paths(manager)
#             if len(modules) > 1:
#                 self.populate_seen_mod(manager)
#                 manager.opt_1 = True
#             else:
#                 manager.opt_1 = False
#             manager.modules = modules_dict
#             paths = list(product(*manager.child_path_codes.values()))
#             #print(f" Upper bound on num paths {len(paths)}")
#             self.init_run(manager, ast)

#             manager.seen = {}
#             for name in manager.names_list:
#                 manager.seen[name] = []
#             manager.curr_module = manager.names_list[0]

#             for i in range(len(paths)):
#                 for j in range(len(paths[i])):
#                     manager.config[manager.names_list[j]] = paths[i][j]
#                 manager.path_code = manager.config[manager.names_list[0]]
#                 if self.check_dup(manager):
#                 # #if False:
#                     continue
#                 else:
#                     print("------------------------")
#                     #print(f"{ast.name} Path {i}")
#                 self.visit_module(manager, state, ast, modules_dict)
#                 manager.seen[ast.name].append(manager.path_code)
#                 if (manager.assertion_violation):
#                     print("Assertion violation")
#                     manager.assertion_violation = False
#                     self.solve_pc(state.pc)
#                 manager.curr_level = 0
#                 manager.dependencies = {}
#                 state.pc.reset()
#             #manager.path_code = to_binary(0)
#             #print(f" finishing {ast.name}")
#             self.module_depth -= 1
