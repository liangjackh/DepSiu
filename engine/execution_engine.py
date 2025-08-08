import z3
from z3 import Solver, Int, BitVec, Context, BitVecSort, ExprRef, BitVecRef, If, BitVecVal, And
from pyverilog.vparser.parser import parse
from pyverilog.vparser.ast import Description, ModuleDef, Node, IfStatement, SingleStatement, And, Constant, Rvalue, Plus, Input, Output
from pyverilog.vparser.ast import WhileStatement, ForStatement, CaseStatement, Block, SystemCall, Land, InstanceList, IntConst, Partselect, Ioport
from pyverilog.vparser.ast import Value, Reg, Initial, Eq, Identifier, Initial,  NonblockingSubstitution, Decl, Always, Assign, NotEql, Case, Pointer
from pyverilog.vparser.ast import Concat, BlockingSubstitution, Parameter, StringConst, Wire, PortArg, Instance
from .execution_manager import ExecutionManager
from .symbolic_state import SymbolicState
from .cfg import CFG
import re
import os
from optparse import OptionParser
from typing import Optional
import random, string
import time
import gc
from itertools import product
import logging
from helpers.utils import to_binary
from strategies.dfs import DepthFirst
import sys
from copy import deepcopy
from helpers.slang_helpers import get_module_name, init_state
from pyslang import  DefinitionSymbol, VisitAction
#import pyslang

CONDITIONALS = (IfStatement, ForStatement, WhileStatement, CaseStatement)

class ExecutionEngine:
    module_depth: int = 0
    search_strategy = DepthFirst()
    debug: bool = False
    done: bool = False

    def check_pc_SAT(self, s: Solver, constraint: ExprRef) -> bool:
        """Check if pc is satisfiable before taking path."""
        # the push adds a backtracking point if unsat
        s.push()
        s.add(constraint)
        result = s.check()
        if str(result) == "sat":
            return True
        else:
            s.pop()
            return False

    def check_dup(self, m: ExecutionManager) -> bool:
        """Checks if the current path is a duplicate/worth exploring."""
        for i in range(len(m.path_code)):
            if m.path_code[i] == "1" and i in m.completed:
                return True
        return False

    def solve_pc(self, s: Solver) -> bool:
        """Solve path condition."""
        result = str(s.check())
        if str(result) == "sat":
            model = s.model()
            return True
        else:
            return False

    def count_conditionals_2(self, m:ExecutionManager, items) -> int:
        """Rewrite to actually return an int."""
        stmts = items
        if isinstance(items, Block):
            stmts = items.statements
            items.cname = "Block"

        if hasattr(stmts, '__iter__'):
            for item in stmts:
                if isinstance(item, CONDITIONALS):
                    if isinstance(item, IfStatement):
                        return self.count_conditionals_2(m, item.true_statement) + self.count_conditionals_2(m, item.false_statement)  + 1
                    elif isinstance(items, CaseStatement):
                        return self.count_conditionals_2(m, items.caselist) + 1
                    elif isinstance(items, ForStatement):
                        return self.count_conditionals_2(m, items.statement) + 1
                if isinstance(item, Block):
                    return self.count_conditionals_2(m, item.items)
                elif isinstance(item, Always):
                   return self.count_conditionals_2(m, item.statement)             
                elif isinstance(item, Initial):
                    return self.count_conditionals_2(m, item.statement)
        elif items != None:
            if isinstance(items, IfStatement):
                return  ( self.count_conditionals_2(m, items.true_statement) + 
                self.count_conditionals_2(m, items.false_statement)) + 1
            if isinstance(items, CaseStatement):
                return self.count_conditionals_2(m, items.caselist) + len(items.caselist)
            if isinstance(items, ForStatement):
                return self.count_conditionals_2(m, items.statement) + 1
        return 0

    def count_conditionals(self, m: ExecutionManager, items):
        """Identify control flow structures to count total number of paths."""
        stmts = items
        if isinstance(items, Block):
            stmts = items.statements
            items.cname = "Block"
        if hasattr(stmts, '__iter__'):
            for item in stmts:
                if isinstance(item, CONDITIONALS):
                    if isinstance(item, IfStatement):
                        m.num_paths *= 2
                        self.count_conditionals(m, item.true_statement)
                        self.count_conditionals(m, item.false_statement)
                    elif isinstance(item, CaseStatement):
                        for case in item.caselist:
                            m.num_paths *= 2
                            self.count_conditionals(m, case.statement)
                    elif isinstance(item, ForStatement):
                        m.num_paths *= 2
                        self.count_conditionals(m, item.statement) 
                if isinstance(item, Block):
                    self.count_conditionals(m, item.items)
                elif isinstance(item, Always):
                    self.count_conditionals(m, item.statement)             
                elif isinstance(item, Initial):
                    self.count_conditionals(m, item.statement)
                elif isinstance(item, Case):
                    self.count_conditionals(m, item.statement)
        elif items != None:
            if isinstance(items, IfStatement):
                m.num_paths *= 2
                self.count_conditionals(m, items.true_statement)
                self.count_conditionals(m, items.false_statement)
            if isinstance(items, CaseStatement):
                for case in items.caselist:
                    m.num_paths *= 2
                    self.count_conditionals(m, case.statement)
            if isinstance(items, ForStatement):
                m.num_paths *= 2
                self.count_conditionals(m, items.statement) 

    def lhs_signals(self, m: ExecutionManager, items):
        """Take stock of which signals are written to in which always blocks for COI analysis."""
        stmts = items
        if isinstance(items, Block):
            stmts = items.statements
            items.cname = "Block"
        if hasattr(stmts, '__iter__'):
            for item in stmts:
                if isinstance(item, IfStatement) or isinstance(item, CaseStatement):
                    if isinstance(item, IfStatement):
                        self.lhs_signals(m, item.true_statement)
                        self.lhs_signals(m, item.false_statement)
                    if isinstance(item, CaseStatement):
                        for case in item.caselist:
                            self.lhs_signals(m, case.statement)
                if isinstance(item, Block):
                    self.lhs_signals(m, item.items)
                elif isinstance(item, Always):
                    m.curr_always = item
                    m.always_writes[item] = []
                    self.lhs_signals(m, item.statement)             
                elif isinstance(item, Initial):
                    self.lhs_signals(m, item.statement)
                elif isinstance(item, Case):
                    self.lhs_signals(m, item.statement)
                elif isinstance(item, Assign):
                    if isinstance(item.left.var, Partselect):
                        if m.curr_always is not None and item.left.var.var.name not in m.always_writes[m.curr_always]:
                            m.always_writes[m.curr_always].append(item.left.var.var.name)
                    elif isinstance(item.left.var, Pointer):
                        if m.curr_always is not None and item.left.var.var.name not in m.always_writes[m.curr_always]:
                            m.always_writes[m.curr_always].append(item.left.var.ptr)
                    elif isinstance(item.left.var, Concat) and m.curr_always is not None:
                        for sub_item in item.left.var.list:
                            m.always_writes[m.curr_always].append(sub_item.name)
                    elif m.curr_always is not None and item.left.var.name not in m.always_writes[m.curr_always]:
                        m.always_writes[m.curr_always].append(item.left.var.name)
                elif isinstance(item, NonblockingSubstitution):
                    if isinstance(item.left.var, Partselect):
                        if m.curr_always is not None and item.left.var.var.name not in m.always_writes[m.curr_always]:
                            m.always_writes[m.curr_always].append(item.left.var.var.name)
                    elif isinstance(item.left.var, Concat):
                        for sub_item in item.left.var.list:
                            if isinstance(sub_item, Partselect):
                                if m.curr_always is not None and sub_item.var.name not in m.always_writes[m.curr_always]:
                                    m.always_writes[m.curr_always].append(sub_item.var.name)
                            elif isinstance(sub_item, Pointer):
                                if m.curr_always is not None and sub_item.var.name not in m.always_writes[m.curr_always]:
                                    m.always_writes[m.curr_always].append(sub_item.var.name)
                            else:
                                m.always_writes[m.curr_always].append(sub_item.name)
                    elif isinstance(item.left.var, Pointer):
                        if m.curr_always is not None and item.left.var.var.name not in m.always_writes[m.curr_always]:
                            m.always_writes[m.curr_always].append(item.left.var.var.name)
                    elif m.curr_always is not None and item.left.var.name not in m.always_writes[m.curr_always]:
                        m.always_writes[m.curr_always].append(item.left.var.name)
                elif isinstance(item, BlockingSubstitution):
                    if isinstance(item.left.var, Partselect):
                        if m.curr_always is not None and item.left.var.var.name not in m.always_writes[m.curr_always]:
                            m.always_writes[m.curr_always].append(item.left.var.var.name)
                    elif isinstance(item.left.var, Pointer):
                        if m.curr_always is not None and item.left.var.var.name not in m.always_writes[m.curr_always]:
                            m.always_writes[m.curr_always].append(item.left.var.var.name)
                    elif m.curr_always is not None and item.left.var.name not in m.always_writes[m.curr_always]:
                        m.always_writes[m.curr_always].append(item.left.var.name)
        elif items != None:
            if isinstance(items, IfStatement):
                self.lhs_signals(m, items.true_statement)
                self.lhs_signals(m, items.false_statement)
            if isinstance(items, CaseStatement):
                for case in items.caselist:
                    self.lhs_signals(m, case.statement)
            elif isinstance(items, Assign):
                if m.curr_always is not None and items.left.var.name not in m.always_writes[m.curr_always]:
                    m.always_writes[m.curr_always].append(items.left.var.name)
            elif isinstance(items, NonblockingSubstitution):
                if isinstance(items.left.var, Concat):
                    for sub_item in items.left.var.list:
                        if sub_item.name not in m.always_writes[m.curr_always]:
                            m.always_writes[m.curr_always].append(sub_item.name)
                elif isinstance(items.left.var, Partselect):
                    if m.curr_always is not None and items.left.var.var.name not in m.always_writes[m.curr_always]:
                        m.always_writes[m.curr_always].append(item.left.var.var.name)
                elif isinstance(items.left.var, Pointer):
                    if m.curr_always is not None and items.left.var.var.name not in m.always_writes[m.curr_always]:
                        m.always_writes[m.curr_always].append(items.left.var.var.name)
                elif m.curr_always is not None and items.left.var.name not in m.always_writes[m.curr_always]:
                    m.always_writes[m.curr_always].append(items.left.var.name)
            elif isinstance(items, BlockingSubstitution):
                if isinstance(items.left.var, Pointer):
                    if m.curr_always is not None and items.left.var.var.name not in m.always_writes[m.curr_always]:
                        m.always_writes[m.curr_always].append(items.left.var.var.name)
                elif isinstance(items.left.var, Partselect):
                    if m.curr_always is not None and items.left.var.var.name not in m.always_writes[m.curr_always]:
                        m.always_writes[m.curr_always].append(item.left.var.var.name)
                else:
                    if m.curr_always is not None and items.left.var.name not in m.always_writes[m.curr_always]:
                        m.always_writes[m.curr_always].append(items.left.var.name)



    def get_assertions(self, m: ExecutionManager, items):
        """Traverse the AST and get the assertion violating conditions."""
        stmts = items
        if isinstance(items, Block):
            stmts = items.statements
            items.cname = "Block"
        if hasattr(stmts, '__iter__'):
            for item in stmts:
                if isinstance(item, IfStatement) or isinstance(item, CaseStatement):
                    if isinstance(item, IfStatement):
                        # starting to check for the assertions
                        if isinstance(item.true_statement, Block):
                            if isinstance(item.true_statement.statements[0], SingleStatement):
                                if isinstance(item.true_statement.statements[0].statement, SystemCall) and "ASSERTION" in item.true_statement.statements[0].statement.args[0].value:
                                    m.assertions.append(item.cond)
                                    #print("assertion found")
                            else:     
                                self.get_assertions(m, item.true_statement)
                            #self.get_assertions(m, item.false_statement)
                    if isinstance(item, CaseStatement):
                        for case in item.caselist:
                            self.get_assertions(m, case.statement)
                elif isinstance(item, Block):
                    self.get_assertions(m, item.items)
                elif isinstance(item, Always):
                    self.get_assertions(m, item.statement)             
                elif isinstance(item, Initial):
                    self.get_assertions(m, item.statement)
                elif isinstance(item, Case):
                    self.get_assertions(m, item.statement)
        elif items != None:
            if isinstance(items, IfStatement):
                self.get_assertions(m, items.true_statement)
                self.get_assertions(m, items.false_statement)
            if isinstance(items, CaseStatement):
                for case in items.caselist:
                    self.get_assertions(m, case.statement)

    def map_assertions_signals(self, m: ExecutionManager):
        """Map the assertions to a list of relevant signals."""
        signals = []
        for assertion in m.assertions:
            # TODO write function to exhaustively get all the signals from assertions
            # this is just grabbing the left most
            if isinstance(assertion.right, IntConst):
                ...
            elif isinstance(assertion.right.left, Identifier):
                signals.append(assertion.right.left.name)
        return signals

    def assertions_always_intersect(self, m: ExecutionManager):
        """Get the always blocks that have the signals relevant to the assertions."""
        signals_of_interest = self.map_assertions_signals(m)
        blocks_of_interest = []
        for block in m.always_writes:
            for signal in signals_of_interest:
                if signal in m.always_writes[block]:
                    blocks_of_interest.append(block)
        m.blocks_of_interest = blocks_of_interest


    def seen_all_cases(self, m: ExecutionManager, bit_index: int, nested_ifs: int) -> bool:
        """Checks if we've seen all the cases for this index in the bit string.
        We know there are no more nested conditionals within the block, just want to check 
        that we have seen the path where this bit was turned on but the thing to the left of it
        could vary."""
        # first check if things less than me have been added.
        # so index 29 shouldnt be completed before 30
        for i in range(bit_index + 1, 32):
            if not i in m.completed:
                return False
        count = 0
        seen = m.seen
        for path in seen[m.curr_module]:
            if path[bit_index] == '1':
                count += 1
        if count >  2 * nested_ifs:
            return True
        return False

    def module_count_sv(self, m: ExecutionManager, items) -> None: # item: DefinitionSymbol
        """Traverse a top level module and count up the instances of each type of module
        for SystemVerilog."""
        # TODO need to figure out what the node type is for instances
        # TODO do this check for the other block types

        if items.__class__.__name__ == "ProceduralBlockSyntax":
            items = items.statement.statements
        if hasattr(items, '__iter__'):
            for item in items:
                print(f"name: {item.getKindString()}")
                #m.instance_count[item.get]
                #if isinstance(item, InstanceList):
                #    self.module_count(m, item.instances)
                #elif isinstance(item, Instance):
                #    if item.module in m.instance_count:
                #        m.instance_count[item.module] += 1
                #        ...
                #    else:
                #        m.instance_count[item.module] = 1
                #if item.__class__.__name__ == "ProceduralBlockSyntax":
                #    # Always Block
                #    self.module_count(m, item.statement.statement.items)           
                #elif isinstance(item, Initial):
                #    self.module_count(m, item.statement)
        elif items != None:
                print(f"name: {items.getKindString()}")
                #if isinstance(items, InstanceList):
                #    if items.module in m.instance_count:
                #        m.instance_count[items.module] += 1
                #    else:
                #        m.instance_count[items.module] = 1
                #    self.module_count(m, items.instances)

    def module_count(self, m: ExecutionManager, items) -> None:
        """Traverse a top level module and count up the instances of each type of module."""
        if isinstance(items, Block):
            items = items.statements
        if hasattr(items, '__iter__'):
            for item in items:
                if isinstance(item, InstanceList):
                    self.module_count(m, item.instances)
                elif isinstance(item, Instance):
                    if item.module in m.instance_count:
                        m.instance_count[item.module] += 1
                        ...
                    else:
                        m.instance_count[item.module] = 1
                if isinstance(item, Block):
                    self.module_count(m, item.items)
                elif isinstance(item, Always):
                    self.module_count(m, item.statement)             
                elif isinstance(item, Initial):
                    self.module_count(m, item.statement)
        elif items != None:
                if isinstance(items, InstanceList):
                    if items.module in m.instance_count:
                        m.instance_count[items.module] += 1
                    else:
                        m.instance_count[items.module] = 1
                    self.module_count(m, items.instances)



    def init_run(self, m: ExecutionManager, module: ModuleDef) -> None:
        """Initalize run."""
        m.init_run_flag = True
        # come back to this stuff 
        # TODO change to members and redo 
        # self.count_conditionals(m, module.items)
        # self.lhs_signals(m, module.items)
        # self.get_assertions(m, module.items)
        m.init_run_flag = False
        #self.module_count(m, module.items)

    #def count_conditionals_sv(self, m: ExecutionManager, items):
    #    print("counting conditionals")
    #def lhs_signals_sv(self, m: ExecutionManager, items):
    #    print("lhs signals sv")
    #def get_assertions_sv(self, m: ExecutionManager, items):
    #    print("get assertions sv")


    def count_conditionals_sv(self, m: ExecutionManager, module) -> None: # DefinitionSymbol
        """Count control flow paths for PySlang AST."""
        try:
            # Import pyslang modules we need
            import pyslang as ps
            from pyslang import SymbolKind, ProceduralBlockSymbol, Statement
            
            print(f"[count_conditionals_sv] ========== Starting Analysis ==========")
            print(f"[count_conditionals_sv] Module: {module.name}")
            print(f"[count_conditionals_sv] Module Type: {type(module)}")
            print(f"[count_conditionals_sv] Initial paths: {m.num_paths}")
            
            # Debug: Show module properties
            if hasattr(module, 'definitionKind'):
                print(f"[count_conditionals_sv] Definition Kind: {module.definitionKind}")
            if hasattr(module, 'defaultNetType'):
                print(f"[count_conditionals_sv] Default Net Type: {module.defaultNetType}")
                
            # Initialize path counting visitor
            class ConditionalCounter:
                def __init__(self, manager: ExecutionManager):
                    self.manager = manager
                    self.conditional_count = 0
                    self.if_count = 0
                    self.case_count = 0 
                    self.loop_count = 0
                    self.ternary_count = 0  # Add counter for ternary operators
                    self.procedural_blocks = 0
                    self.total_nodes_visited = 0
                    self.node_types_seen = set()
                    
                def __call__(self, obj):
                    """Visit function for pyslang AST traversal"""
                    try:
                        self.total_nodes_visited += 1
                        node_type = type(obj).__name__
                        self.node_types_seen.add(node_type)
                        
                        ## Debug: Log every 100th node visit to avoid spam
                        #if self.total_nodes_visited % 100 == 0:
                        #    print(f"[count_conditionals_sv] Visited {self.total_nodes_visited} nodes so far...")
                        
                        # Check if this is a Statement
                        if isinstance(obj, Statement):
                            stmt_kind = str(obj.kind)
                            
                            print(f"[count_conditionals_sv] Processing Statement: {stmt_kind}")
                            
                            # Count conditional statements and update paths
                            if 'If' in stmt_kind:
                                old_paths = self.manager.num_paths
                                self.manager.num_paths *= 2
                                self.conditional_count += 1
                                self.if_count += 1
                                print(f"[count_conditionals_sv] Found If statement #{self.if_count}")
                                print(f"[count_conditionals_sv]   Paths: {old_paths} -> {self.manager.num_paths}")
                                
                                # Try to extract condition information
                                try:
                                    if hasattr(obj, 'cond') and obj.cond:
                                        print(f"[count_conditionals_sv]   Condition: {str(obj.cond)[:100]}")
                                except:
                                    pass
                                
                            elif 'Case' in stmt_kind:
                                # For case statements, we need to count the number of cases
                                # Default to 2 paths if we can't determine case count
                                case_multiplier = 2
                                try:
                                    if hasattr(obj, 'items') and obj.items:
                                        case_multiplier = len(obj.items)
                                        print(f"[count_conditionals_sv]   Case has {case_multiplier} items")
                                    else:
                                        print(f"[count_conditionals_sv]   Case items not accessible, using default multiplier")
                                except Exception as e:
                                    print(f"[count_conditionals_sv]   Error accessing case items: {e}")
                                    pass
                                
                                old_paths = self.manager.num_paths
                                self.manager.num_paths *= case_multiplier
                                self.conditional_count += 1
                                self.case_count += 1
                                print(f"[count_conditionals_sv] Found Case statement #{self.case_count}")
                                print(f"[count_conditionals_sv]   Paths: {old_paths} -> {self.manager.num_paths} (x{case_multiplier})")
                                
                                # Try to extract case expression
                                try:
                                    if hasattr(obj, 'expr') and obj.expr:
                                        print(f"[count_conditionals_sv]   Expression: {str(obj.expr)[:100]}")
                                except:
                                    pass
                                
                            elif 'For' in stmt_kind or 'While' in stmt_kind:
                                old_paths = self.manager.num_paths
                                self.manager.num_paths *= 2  # Loop vs no-loop paths
                                self.conditional_count += 1
                                self.loop_count += 1
                                print(f"[count_conditionals_sv] Found Loop statement #{self.loop_count} ({stmt_kind})")
                                print(f"[count_conditionals_sv]   Paths: {old_paths} -> {self.manager.num_paths}")
                                
                        # Check if this is a procedural block (always/initial)
                        elif isinstance(obj, ProceduralBlockSymbol):
                            self.procedural_blocks += 1
                            print(f"[count_conditionals_sv] Found procedural block #{self.procedural_blocks}: {obj.name}")
                            print(f"[count_conditionals_sv]   Block kind: {obj.kind if hasattr(obj, 'kind') else 'unknown'}")
                            
                            # Visit the body of the procedural block
                            if hasattr(obj, 'body') and obj.body:
                                try:
                                    print(f"[count_conditionals_sv]   Visiting block body...")
                                    obj.body.visit(self)
                                    print(f"[count_conditionals_sv]   Finished visiting block body")
                                except Exception as e:
                                    print(f"[count_conditionals_sv]   Error visiting block body: {e}")
                                    pass
                            else:
                                print(f"[count_conditionals_sv]   Block has no body or body not accessible")
                                    
                    except Exception as e:
                        # Don't let individual node errors stop the traversal
                        print(f"[count_conditionals_sv] Error processing node {node_type}: {e}")
                        if self.manager.debug:
                            import traceback
                            print(f"[count_conditionals_sv] Traceback: {traceback.format_exc()}")
                        pass
            
            # Create visitor instance
            counter = ConditionalCounter(m)
            
            # Visit the module to count conditionals
            print(f"[count_conditionals_sv] Starting module traversal...")
            try:
                # Visit the module symbol itself
                module.visit(counter)
                
                # Visit the syntax tree to find procedural blocks and statements
                print(f"[count_conditionals_sv] Visiting module syntax tree...")
                if hasattr(module, 'syntax') and module.syntax:
                    try:
                        # Only visit the module items (body), not the entire syntax tree
                        self._visit_module_items(module.syntax, counter)
                    except Exception as e:
                        print(f"[count_conditionals_sv] Error visiting syntax tree: {e}")
                
                # Try to access module body through symbol hierarchy
                print(f"[count_conditionals_sv] Looking for module body...")
                try:
                    # Look for body in the module's scope
                    if hasattr(module, 'body') and module.body:
                        print(f"[count_conditionals_sv] Found module body, visiting...")
                        module.body.visit(counter)
                            
                except Exception as e:
                    print(f"[count_conditionals_sv] Error accessing module body: {e}")
                
                print(f"[count_conditionals_sv] Module traversal completed")
            except Exception as e:
                print(f"[count_conditionals_sv] Error visiting module {module.name}: {e}")
                import traceback
                print(f"[count_conditionals_sv] Traceback: {traceback.format_exc()}")
                # Fallback: assume at least 1 path if no conditionals found
                if m.num_paths == 1 and counter.conditional_count == 0:
                    m.num_paths = 1
            
            # Print comprehensive summary
            print(f"[count_conditionals_sv] ========== Analysis Summary ==========")
            print(f"[count_conditionals_sv] Module: {module.name}")
            print(f"[count_conditionals_sv] Total nodes visited: {counter.total_nodes_visited}")
            print(f"[count_conditionals_sv] Node types seen: {sorted(list(counter.node_types_seen))}")
            print(f"[count_conditionals_sv] Procedural blocks found: {counter.procedural_blocks}")
            print(f"[count_conditionals_sv] Control flow breakdown:")
            print(f"[count_conditionals_sv]   - If statements: {counter.if_count}")
            print(f"[count_conditionals_sv]   - Case statements: {counter.case_count}")
            print(f"[count_conditionals_sv]   - Loop statements: {counter.loop_count}")
            print(f"[count_conditionals_sv]   - Ternary operators: {counter.ternary_count}")
            print(f"[count_conditionals_sv]   - Total conditionals: {counter.conditional_count}")
            print(f"[count_conditionals_sv] Path count: 1 -> {m.num_paths}")
            print(f"[count_conditionals_sv] ==========================================")
                    
        except Exception as e:
            print(f"[count_conditionals_sv] Fatal error in count_conditionals_sv: {e}")
            import traceback
            print(f"[count_conditionals_sv] Traceback: {traceback.format_exc()}")
            # Ensure we have at least 1 path
            if m.num_paths < 1:
                m.num_paths = 1
    
    def _visit_module_items(self, module_syntax, counter):
        """Helper method to visit only module items (body content)"""
        try:
            print(f"[count_conditionals_sv] Looking for module items in: {type(module_syntax).__name__}")
            
            # For ModuleDeclarationSyntax, we want to find the items (member list)
            if hasattr(module_syntax, 'items') and module_syntax.items:
                print(f"[count_conditionals_sv] Found module items list")
                for item in module_syntax.items:
                    if item and hasattr(item, 'kind'):
                        kind_str = str(item.kind)
                        # Visit procedural blocks and continuous assignments
                        if any(relevant in kind_str for relevant in ['ProceduralBlock', 'ContinuousAssign', 'DataDeclaration']):
                            print(f"[count_conditionals_sv] Processing module item: {kind_str}")
                            self._visit_syntax_node(item, counter)
                        else:
                            # Still visit other items but don't print debug info for simple declarations
                            self._visit_syntax_node(item, counter)
            
            # Alternative: look for members attribute
            elif hasattr(module_syntax, 'members') and module_syntax.members:
                print(f"[count_conditionals_sv] Found module members list")
                for member in module_syntax.members:
                    if member and hasattr(member, 'kind'):
                        self._visit_syntax_node(member, counter)
            
            # Try to access child nodes that might contain module items
            else:
                print(f"[count_conditionals_sv] Searching for module content recursively")
                for attr_name in ['items', 'members', 'statements', 'body']:
                    if hasattr(module_syntax, attr_name):
                        attr = getattr(module_syntax, attr_name)
                        if attr and hasattr(attr, '__iter__') and not isinstance(attr, str):
                            for item in attr:
                                if item and hasattr(item, 'kind'):
                                    kind_str = str(item.kind)
                                    if 'ProceduralBlock' in kind_str or 'Always' in kind_str:
                                        print(f"[count_conditionals_sv] Found procedural content: {kind_str}")
                                        self._visit_syntax_node(item, counter)
                                    elif any(flow in kind_str for flow in ['If', 'Case', 'Loop', 'For', 'While']):
                                        print(f"[count_conditionals_sv] Found control flow: {kind_str}")
                                        self._visit_syntax_node(item, counter)
                        break
                        
        except Exception as e:
            print(f"[count_conditionals_sv] Error in _visit_module_items: {e}")
            if counter.manager.debug:
                import traceback
                print(f"[count_conditionals_sv] Traceback: {traceback.format_exc()}")
    
    def _visit_syntax_node(self, syntax_node, counter):
        """Helper method to recursively visit syntax tree nodes for control flow analysis"""
        try:
            # Import required pyslang syntax node types
            from pyslang import ProceduralBlockSyntax
            
            node_type = type(syntax_node).__name__
            
            # Check for procedural blocks (always, initial)
            if isinstance(syntax_node, ProceduralBlockSyntax):
                print(f"[count_conditionals_sv] Found ProceduralBlockSyntax")
                counter.procedural_blocks += 1
                # Visit the statement inside the procedural block
                if hasattr(syntax_node, 'statement') and syntax_node.statement:
                    print(f"[count_conditionals_sv] Visiting procedural block statement: {type(syntax_node.statement).__name__}")
                    self._visit_syntax_node(syntax_node.statement, counter)
                else:
                    print(f"[count_conditionals_sv] Procedural block has no statement attribute")
                    # Try alternative attributes
                    for attr in ['body', 'stmt', 'statements']:
                        if hasattr(syntax_node, attr):
                            attr_val = getattr(syntax_node, attr)
                            if attr_val:
                                print(f"[count_conditionals_sv] Found alternative attribute {attr}: {type(attr_val).__name__}")
                                self._visit_syntax_node(attr_val, counter)
                                break
                return
            
            # Check for conditional statements by examining the kind
            if hasattr(syntax_node, 'kind') and syntax_node.kind:
                kind_str = str(syntax_node.kind)
                
                # Only count specific conditional statement types
                if kind_str == 'SyntaxKind.ConditionalStatement':
                    old_paths = counter.manager.num_paths
                    counter.manager.num_paths *= 2
                    counter.conditional_count += 1
                    counter.if_count += 1
                    print(f"[count_conditionals_sv] Found ConditionalStatement #{counter.if_count}")
                    print(f"[count_conditionals_sv]   Paths: {old_paths} -> {counter.manager.num_paths}")
                    
                elif 'CaseStatement' in kind_str:
                    # Try to count case items
                    case_multiplier = 2  # Default
                    try:
                        if hasattr(syntax_node, 'items') and syntax_node.items:
                            case_multiplier = len(list(syntax_node.items))
                    except:
                        pass
                    
                    old_paths = counter.manager.num_paths
                    counter.manager.num_paths *= case_multiplier
                    counter.conditional_count += 1
                    counter.case_count += 1
                    print(f"[count_conditionals_sv] Found CaseStatement #{counter.case_count}")
                    print(f"[count_conditionals_sv]   Paths: {old_paths} -> {counter.manager.num_paths}")
                    
                elif any(loop_type in kind_str for loop_type in ['LoopStatement', 'ForLoopStatement', 'WhileLoopStatement']):
                    old_paths = counter.manager.num_paths
                    counter.manager.num_paths *= 2
                    counter.conditional_count += 1
                    counter.loop_count += 1
                    print(f"[count_conditionals_sv] Found LoopStatement #{counter.loop_count}")
                    print(f"[count_conditionals_sv]   Paths: {old_paths} -> {counter.manager.num_paths}")
                    
                elif 'ConditionalExpression' in kind_str:
                    # Handle ternary operators (condition ? true_expr : false_expr)
                    old_paths = counter.manager.num_paths
                    counter.manager.num_paths *= 2
                    counter.conditional_count += 1
                    counter.ternary_count += 1
                    print(f"[count_conditionals_sv] Found ConditionalExpression (ternary) #{counter.ternary_count}")
                    print(f"[count_conditionals_sv]   Paths: {old_paths} -> {counter.manager.num_paths}")
            
            # Handle continuous assignments - need to check their expressions for conditional operators
            if hasattr(syntax_node, 'kind') and 'ContinuousAssign' in str(syntax_node.kind):
                print(f"[count_conditionals_sv] Found ContinuousAssign, checking for conditional expressions")
                # Visit the assignment to look for ternary operators in the RHS expression
            
            # Recursively visit relevant child nodes
            # Try multiple ways to access child nodes
            visited_child = False
            
            # Method 1: statement attribute
            if hasattr(syntax_node, 'statement') and syntax_node.statement:
                self._visit_syntax_node(syntax_node.statement, counter)
                visited_child = True
                
            # Method 1.5: expression attribute (for assignments)
            elif hasattr(syntax_node, 'expr') and syntax_node.expr:
                self._visit_syntax_node(syntax_node.expr, counter)
                visited_child = True
                
            # Method 2: statements attribute (list)
            elif hasattr(syntax_node, 'statements') and syntax_node.statements:
                for stmt in syntax_node.statements:
                    if stmt and hasattr(stmt, 'kind'):
                        self._visit_syntax_node(stmt, counter)
                visited_child = True
                
            # Method 3: iterate through the node if it's iterable
            elif hasattr(syntax_node, '__iter__'):
                try:
                    children = list(syntax_node)
                    if children:
                        for child in children:
                            if child and hasattr(child, 'kind'):
                                # Only recurse into control flow relevant nodes and expressions
                                child_kind = str(child.kind)
                                if any(relevant in child_kind for relevant in ['Statement', 'Block', 'List', 'Expression', 'Assignment']):
                                    self._visit_syntax_node(child, counter)
                        visited_child = True
                except Exception as e:
                    if counter.manager.debug:
                        print(f"[count_conditionals_sv] Error iterating children: {e}")
                    pass
                        
        except Exception as e:
            print(f"[count_conditionals_sv] Error in _visit_syntax_node: {e}")
            if counter.manager.debug:
                import traceback
                print(f"[count_conditionals_sv] Traceback: {traceback.format_exc()}")
            pass

        #def lhs_signals_sv(self, m: ExecutionManager, items) -> None:
        #    """Collect written signals for PySlang AST."""
        #    if isinstance(items, pyslang.ast.BlockStatement):
        #        stmts = items.items
        #    else:
        #        stmts = items if isinstance(items, list) else [items]

        #    for item in stmts:
        #        if isinstance(item, pyslang.ast.IfStatement):
        #            self.lhs_signals_sv(m, item.true_stmt)
        #            self.lhs_signals_sv(m, item.false_stmt)
        #        elif isinstance(item, pyslang.ast.CaseStatement):
        #            for case in item.items:
        #                self.lhs_signals_sv(m, case.stmt)
        #        elif isinstance(item, pyslang.ast.ProceduralBlock):
        #            m.curr_always = item
        #            m.always_writes[item] = []
        #            self.lhs_signals_sv(m, item.stmt)
        #        elif isinstance(item, (pyslang.ast.AssignmentExpression, 
        #                              pyslang.ast.BlockingAssignment,
        #                              pyslang.ast.NonblockingAssignment)):
        #            # Handle LHS signal extraction
        #            lhs = item.left
        #            if isinstance(lhs, pyslang.ast.Identifier):
        #                if m.curr_always and lhs.name not in m.always_writes[m.curr_always]:
        #                    m.always_writes[m.curr_always].append(lhs.name)
        #            elif isinstance(lhs, pyslang.ast.ElementSelect):
        #                if m.curr_always and lhs.value.name not in m.always_writes[m.curr_always]:
        #                    m.always_writes[m.curr_always].append(lhs.value.name)
        #            elif isinstance(lhs, pyslang.ast.Concatenation):
        #                for expr in lhs.expressions:
        #                    if isinstance(expr, pyslang.ast.Identifier) and m.curr_always:
        #                        if expr.name not in m.always_writes[m.curr_always]:
        #                            m.always_writes[m.curr_always].append(expr.name)

    def get_assertions_sv(self, m: ExecutionManager, items) -> None:
        """Collect assertions for PySlang AST."""
        if isinstance(items, pyslang.ast.BlockStatement):
            stmts = items.items
        else:
            stmts = items if isinstance(items, list) else [items]

        for item in stmts:
            if isinstance(item, pyslang.ast.IfStatement):
                if isinstance(item.true_stmt, pyslang.ast.ConcurrentAssertion):
                    m.assertions.append(item.condition)
                else:
                    self.get_assertions_sv(m, item.true_stmt)
                    self.get_assertions_sv(m, item.false_stmt)
            elif isinstance(item, pyslang.ast.ProceduralBlock):
                self.get_assertions_sv(m, item.stmt)
            elif isinstance(item, pyslang.ast.ConcurrentAssertion):
                # Direct assertions not inside conditionals
                m.assertions.append(item.expr)

    def init_run_sv(self, m: ExecutionManager, module: DefinitionSymbol) -> None:
        """Initialize run for PySlang AST."""
        print("init run sv")
        m.init_run_flag = True
        #TODO
        self.count_conditionals_sv(m, module) # module:DefinitionSymbol
        #print(f"init_runs, {module.name} has CONDITIONALs: {m.conditional_num}, FOR statements: {m.stmt_for_num}, CASE statements: {m.stmt_case_num}")
        print(f"init_runs, {module.name} has {module.name}.num_paths = {m.num_paths}") 
        #self.lhs_signals_sv(m, module.items)
        #self.get_assertions_sv(m, module.items)
        m.init_run_flag = False

    def populate_child_paths(self, manager: ExecutionManager) -> None:
        """Populates child path codes based on number of paths."""
        for child in manager.child_num_paths:
            manager.child_path_codes[child] = []
            if manager.piece_wise:
                manager.child_path_codes[child] = []
                for i in manager.child_range:
                    manager.child_path_codes[child].append(to_binary(i))
            else:
                for i in range(manager.child_num_paths[child]):
                    manager.child_path_codes[child].append(to_binary(i))

    def populate_seen_mod(self, manager: ExecutionManager) -> None:
        """Populates child path codes but in a format to keep track of corresponding states that we've seen."""
        for child in manager.child_num_paths:
            manager.seen_mod[child] = {}
            if manager.piece_wise:
                for i in manager.child_range:
                    manager.seen_mod[child][(to_binary(i))] = {}
            else:
                for i in range(manager.child_num_paths[child]):
                    manager.seen_mod[child][(to_binary(i))] = {}

    def piece_wise_execute(self, ast: ModuleDef, manager: Optional[ExecutionManager], modules) -> None:
        """Drives symbolic execution piecewise when number of paths is too large not to breakup. 
        We break it up to avoid the memory blow up."""
        self.module_depth += 1
        manager.piece_wise = True
        state: SymbolicState = SymbolicState()
        if manager is None:
            manager: ExecutionManager = ExecutionManager()
            manager.debugging = False
        modules_dict = {}
        for module in modules:
            modules_dict[module.name] = module
            manager.seen_mod[module.name] = {}
            sub_manager = ExecutionManager()
            manager.names_list.append(module.name)
            self.init_run(sub_manager, module)
            self.module_count(manager, module.items)
            if module.name in manager.instance_count:
                manager.instances_seen[module.name] = 0
                manager.instances_loc[module.name] = ""
                num_instances = manager.instance_count[module.name]
                for i in range(num_instances):
                    instance_name = f"{module.name}_{i}"
                    manager.names_list.append(instance_name)
                    manager.child_path_codes[instance_name] = to_binary(0)
                    manager.child_num_paths[instance_name] = sub_manager.num_paths
                    manager.config[instance_name] = to_binary(0)
                    state.store[instance_name] = {}
                    manager.dependencies[instance_name] = {}
                    manager.intermodule_dependencies[instance_name] = {}
                    manager.cond_assigns[instance_name] = {}
                manager.names_list.remove(module.name)
            else:
                manager.child_path_codes[module.name] = to_binary(0)
                manager.child_num_paths[module.name] = sub_manager.num_paths
                manager.config[module.name] = to_binary(0)
                state.store[module.name] = {}
                manager.dependencies[module.name] = {}
                instance_name = module.name
                manager.intermodule_dependencies[instance_name] = {}
                manager.cond_assigns[module.name] = {}

        total_paths = sum(manager.child_num_paths.values())
        #print(total_paths)
        manager.piece_wise = True
        #TODO: things piecewise, say 10,000 at a time.
        for i in range(0, total_paths, 10):
            manager.child_range = range(i*10, i*10+10)
            self.populate_child_paths(manager)
            if len(modules) >= 1:
                self.populate_seen_mod(manager)
                #manager.opt_1 = True
            else:
                manager.opt_1 = False
            manager.modules = modules_dict
            paths = list(product(*manager.child_path_codes.values()))
            #print(f" Upper bound on num paths {len(paths)}")
            self.init_run(manager, ast)
            manager.seen = {}
            for name in manager.names_list:
                manager.seen[name] = []
            manager.curr_module = manager.names_list[0]

            stride_length = len(manager.names_list)
            # for each combinatoin of multicycle paths
            for i in range(len(paths)):
                manager.cycle = 0

                for j in range(0, len(paths[i])):
                    for name in manager.names_list:
                        manager.config[name] = paths[i][j]

                manager.path_code = paths[i][0]
                manager.prev_store = state.store
                init_state(state, manager.prev_store, ast)
                self.search_strategy.visit_module(manager, state, ast, modules_dict)
                manager.cycle += 1
                manager.curr_level = 0
                if self.check_dup(manager):
                # #if False:
                    if self.debug:
                        print("----------------------")
                    ...
                else:
                    if self.debug:
                        print("------------------------")
                    ...
                    #print(f"{ast.name} Path {i}")
                manager.seen[ast.name].append(manager.path_code)
                if (manager.assertion_violation):
                    print("Assertion violation")
                    counterexample = {}
                    symbols_to_values = {}
                    solver_start = time.process_time()
                    if self.solve_pc(state.pc):
                        solver_end = time.process_time()
                        manager.solver_time += solver_end - solver_start
                        solved_model = state.pc.model()
                        decls =  solved_model.decls()
                        for item in decls:
                            symbols_to_values[item.name()] = solved_model[item]

                        # plug in phase
                        for module in state.store:
                            for signal in state.store[module]:
                                for symbol in symbols_to_values:
                                    if state.store[module][signal] == symbol:
                                        counterexample[signal] = symbols_to_values[symbol]

                        print(counterexample)
                    else:
                        print("UNSAT")
                    return 
                for module in manager.dependencies:
                    module = {}
                for module in manager.intermodule_dependencies:
                    module = {}
                state.pc.reset()

                manager.ignore = False
                manager.abandon = False
                manager.reg_writes.clear()
                for name in manager.names_list:
                    state.store[name] = {}

            #manager.path_code = to_binary(0)
            #print(f" finishing {ast.name}")
            self.module_depth -= 1

    def multicycle_helper(self, ast: ModuleDef, modules_dict, paths,  s: SymbolicState, manager: ExecutionManager, num_cycles: int) -> None:
        """Recursive Helper to resolve multi cycle execution."""
        #TODO: Add in the merging state element to this helper function
        for a in range(num_cycles):
            for i in range(len(paths)):
                for j in range(len(paths[i])):
                    manager.config[manager.names_list[j]] = paths[i][j]
    
    #def visitSlangModule(self, module: Symbol) -> VisitAction:
    #    act = VisitAction()

    def execute_sv(self, visitor, modules, manager: Optional[ExecutionManager], num_cycles: int) -> None:
        """Drives symbolic execution for SystemVerilog designs."""
        # modules => List of DefinitionSymbol
        # visitor => SymbolicDFS
        gc.collect()
        print(f"Executing for {num_cycles} clock cycles")
        self.module_depth += 1
        state: SymbolicState = SymbolicState()
        if manager is None:
            manager: ExecutionManager = ExecutionManager()
            manager.cache = self.cache
            manager.sv = True
            manager.debugging = False
            modules_dict = {}
            # a dictionary keyed by module name, that gives the list of cfgs
            cfgs_by_module = {}
            cfg_count_by_module = {}
            for module in modules:
                sv_module_name = get_module_name(module)
                print(f"sv_module_name: {sv_module_name}")
                modules_dict[sv_module_name] = sv_module_name
                always_blocks_by_module = {sv_module_name: []}
                manager.seen_mod[sv_module_name] = {}
                cfgs_by_module[sv_module_name] = []
                sub_manager = ExecutionManager()
                print(f"type of {module.name}: {type(module)}")
                #self.init_run(sub_manager, module)
                #print(f"[execute_sv]getKindString: f{module.getKindString()}")
                instanceCount = module.instanceCount
                print(f"instanceCount of {module.getArticleKindString()}: {instanceCount}")
                self.init_run_sv(sub_manager, module) # module : DefinitionSymbol
                print(f"module_count_sv:")
                self.module_count_sv(manager, module) 
                if sv_module_name in manager.instance_count:
                    manager.instances_seen[sv_module_name] = 0
                    manager.instances_loc[sv_module_name] = ""
                    num_instances = manager.instance_count[sv_module_name]
                    cfgs_by_module.pop(sv_module_name, None)
                    for i in range(num_instances):
                        instance_name = f"{sv_module_name}_{i}"
                        manager.names_list.append(instance_name)
                        cfgs_by_module[instance_name] = []
                        # build X CFGx for the particular module 
                        cfg = CFG()
                        cfg.reset()
                        cfg.get_always(manager, state, module.items)
                        cfg_count = len(cfg.always_blocks)
                        for k in range(cfg_count):
                            cfg.basic_blocks(manager, state, cfg.always_blocks[k])
                            cfg.partition()
                            # print(cfg.all_nodes)
                            # print(cfg.partition_points)
                            # print(len(cfg.basic_block_list))
                            # print(cfg.edgelist)
                            cfg.build_cfg(manager, state)
                            cfg.module_name = ast.name

                            cfgs_by_module[instance_name].append(deepcopy(cfg))
                            cfg.reset()
                            #print(cfg.paths)
                        state.store[instance_name] = {}
                        manager.dependencies[instance_name] = {}
                        manager.intermodule_dependencies[instance_name] = {}
                        manager.cond_assigns[instance_name] = {}
                else: 
                    manager.names_list.append(sv_module_name)
                    # build X CFGx for the particular module 
                    cfg = CFG()
                    cfg.all_nodes = []
                    #cfg.partition_points = []
                    cfg.get_always_sv(manager, state, module)
                    cfg_count = len(cfg.always_blocks)
                    always_blocks_by_module[sv_module_name] = deepcopy(cfg.always_blocks)
                    for k in range(cfg_count):
                        cfg.basic_blocks(manager, state, always_blocks_by_module[sv_module_name][k])
                        cfg.partition()
                        # print(cfg.partition_points)
                        # print(len(cfg.basic_block_list))
                        # print(cfg.edgelist)
                        cfg.build_cfg(manager, state)
                        #print(cfg.cfg_edges)
                        cfg.module_name = ast.name
                        cfgs_by_module[sv_module_name].append(deepcopy(cfg))
                        cfg.reset()
                        #print(cfg.paths)

                    state.store[sv_module_name] = {}
                    manager.dependencies[sv_module_name] = {}
                    manager.intermodule_dependencies[sv_module_name] = {}
                    manager.cond_assigns[sv_module_name] = {}
            total_paths = 1
            for x in manager.child_num_paths.values():
                total_paths *= x

            # have do do things piece wise
            manager.debug = self.debug
            if total_paths > 100:
                start = time.process_time()
                self.piece_wise_execute(ast, manager, modules)
                end = time.process_time()
                print(f"Elapsed time {end - start}")
                print(f"Solver time {manager.solver_time}")
                sys.exit()
            self.populate_child_paths(manager)
            if len(modules) > 1:
                self.populate_seen_mod(manager)
                #manager.opt_1 = True
            else:
                manager.opt_1 = False
            manager.modules = modules_dict

            mapped_paths = {}
            
            #print(total_paths)

        print(f"[execute_sv]Branch points explored: {manager.branch_count}")
        if self.debug:
            manager.debug = True
        self.assertions_always_intersect(manager)

        manager.seen = {}
        for name in manager.names_list:
            manager.seen[name] = []

            # each module has a mapping table of cfg idx to path list
            mapped_paths[name] = {}
        manager.curr_module = manager.names_list[0]

        # index into cfgs list
        curr_cfg = 0
        for module_name in cfgs_by_module:
            for cfg in cfgs_by_module[module_name]:
                mapped_paths[module_name][curr_cfg] = cfg.paths
                curr_cfg += 1
            curr_cfg = 0

        stride_length = cfg_count
        single_paths_by_module = {}
        total_paths_by_module = {}
        for module_name in cfgs_by_module:
            single_paths_by_module[module_name] = list(product(*mapped_paths[module_name].values()))
            total_paths_by_module[module_name] = list(tuple(product(single_paths_by_module[module_name], repeat=int(num_cycles))))
        # {total_paths_by_module}")
        keys, values = zip(*total_paths_by_module.items())
        total_paths = [dict(zip(keys, path)) for path in product(*values)]
        #print(total_paths)
        
        #single_paths = list(product(*mapped_paths[manager.curr_module].values()))
        #total_paths = list(tuple(product(single_paths, repeat=int(num_cycles))))

        # for each combinatoin of multicycle paths

        print(f"Total paths: {len(total_paths)}")
        for i in range(len(total_paths)):
            manager.prev_store = state.store
            print("------------------------")
            print("initializing state")
            init_state(state, manager.prev_store, module, visitor) # state, module, SymbolicDFS
            # initalize inputs with symbols for all submodules too
            for module_name in manager.names_list:
                manager.curr_module = module_name
                # actually want to terminate this part after the decl and comb part
                # TODO:compilation.getRoot().visit(my_visitor_for_symbol.visit)
                print(f"module name: {type(modules_dict[module_name])}")
                visitor.dfs(modules_dict[module_name])
                #self.search_strategy.visit_module(manager, state, ast, modules_dict)
                
            for cfg_idx in range(cfg_count):
                for node in cfgs_by_module[manager.curr_module][cfg_idx].decls:
                    visitor.dfs(node)
                    #self.search_strategy.visit_stmt(manager, state, node, modules_dict, None)
                for node in cfgs_by_module[manager.curr_module][cfg_idx].comb:
                    visitor.dfs(node)
                    #self.search_strategy.visit_stmt(manager, state, node, modules_dict, None) 
   
            manager.curr_module = manager.names_list[0]
            # makes assumption top level module is first in line
            # ! no longer path code as in bit string, but indices

            
            self.check_state(manager, state)

            curr_path = total_paths[i]
            modules_seen = 0
            for module_name in curr_path:
                manager.curr_module = manager.names_list[modules_seen]
                manager.cycle = 0
                for complete_single_cycle_path in curr_path[module_name]:
                    for cfg_path in complete_single_cycle_path:
                        directions = cfgs_by_module[module_name][complete_single_cycle_path.index(cfg_path)].compute_direction(cfg_path)
                        k: int = 0
                        for basic_block_idx in cfg_path:
                            if basic_block_idx < 0: 
                                # dummy node
                                continue
                            else:
                                direction = directions[k]
                                k += 1
                                basic_block = cfgs_by_module[module_name][complete_single_cycle_path.index(cfg_path)].basic_block_list[basic_block_idx]
                                for stmt in basic_block:
                                    # print(f"updating curr mod {manager.curr_module}")
                                    #self.check_state(manager, state)
                                    self.search_strategy.visit_stmt(manager, state, stmt, modules_dict, direction)
                    # only do once, and the last CFG 
                    #for node in cfgs_by_module[module_name][complete_single_cycle_path.index(cfg_path)].comb:
                        #self.search_strategy.visit_stmt(manager, state, node, modules_dict, None)  
                    manager.cycle += 1
                modules_seen += 1
            manager.cycle = 0
            self.done = True
            self.check_state(manager, state)
            self.done = False

            manager.curr_level = 0
            for module_name in manager.instances_seen:
                manager.instances_seen[module_name] = 0
                manager.instances_loc[module_name] = ""
            if self.debug:
                print("------------------------")
            if (manager.assertion_violation):
                print("Assertion violation")
                #manager.assertion_violation = False
                counterexample = {}
                symbols_to_values = {}
                solver_start = time.process_time()
                if self.solve_pc(state.pc):
                    solver_end = time.process_time()
                    manager.solver_time += solver_end - solver_start
                    solved_model = state.pc.model()
                    decls =  solved_model.decls()
                    for item in decls:
                        symbols_to_values[item.name()] = solved_model[item]

                    # plug in phase
                    for module in state.store:
                        for signal in state.store[module]:
                            for symbol in symbols_to_values:
                                if state.store[module][signal] == symbol:
                                    counterexample[signal] = symbols_to_values[symbol]

                    print(counterexample)
                else:
                    print("UNSAT")
                return
            
            state.pc.reset()

            for module in manager.dependencies:
                module = {}
                
            
            manager.ignore = False
            manager.abandon = False
            manager.reg_writes.clear()
            for name in manager.names_list:
                state.store[name] = {}

        self.module_depth -= 1

    #@profile     
    def execute(self, ast: ModuleDef, modules, manager: Optional[ExecutionManager], directives, num_cycles: int) -> None:
        """Drives symbolic execution."""
        gc.collect()
        print(f"Executing for {num_cycles} clock cycles")
        self.module_depth += 1
        state: SymbolicState = SymbolicState()
        if manager is None:
            manager: ExecutionManager = ExecutionManager()
            manager.debugging = False
            modules_dict = {}
            # a dictionary keyed by module name, that gives the list of cfgs
            cfgs_by_module = {}
            cfg_count_by_module = {}
            for module in modules:
                modules_dict[module.name] = module
                always_blocks_by_module = {module.name: []}
                manager.seen_mod[module.name] = {}
                cfgs_by_module[module.name] = []
                sub_manager = ExecutionManager()
                self.init_run(sub_manager, module)
                self.module_count(manager, module.items) 
                if module.name in manager.instance_count:
                    manager.instances_seen[module.name] = 0
                    manager.instances_loc[module.name] = ""
                    num_instances = manager.instance_count[module.name]
                    cfgs_by_module.pop(module.name, None)
                    for i in range(num_instances):
                        instance_name = f"{module.name}_{i}"
                        manager.names_list.append(instance_name)
                        cfgs_by_module[instance_name] = []
                        # build X CFGx for the particular module 
                        cfg = CFG()
                        cfg.reset()
                        cfg.get_always(manager, state, module.items)
                        cfg_count = len(cfg.always_blocks)
                        for k in range(cfg_count):
                            cfg.basic_blocks(manager, state, cfg.always_blocks[k])
                            cfg.partition()
                            # print(cfg.all_nodes)
                            # print(cfg.partition_points)
                            # print(len(cfg.basic_block_list))
                            # print(cfg.edgelist)
                            cfg.build_cfg(manager, state)
                            cfg.module_name = ast.name

                            cfgs_by_module[instance_name].append(deepcopy(cfg))
                            cfg.reset()
                            #print(cfg.paths)


                        state.store[instance_name] = {}
                        manager.dependencies[instance_name] = {}
                        manager.intermodule_dependencies[instance_name] = {}
                        manager.cond_assigns[instance_name] = {}
                else: 
                    manager.names_list.append(module.name)
                    # build X CFGx for the particular module 
                    cfg = CFG()
                    cfg.all_nodes = []
                    #cfg.partition_points = []
                    cfg.get_always(manager, state, ast.items)
                    cfg_count = len(cfg.always_blocks)
                    always_blocks_by_module[module.name] = deepcopy(cfg.always_blocks)
                    for k in range(cfg_count):
                        cfg.basic_blocks(manager, state, always_blocks_by_module[module.name][k])
                        cfg.partition()
                        # print(cfg.partition_points)
                        # print(len(cfg.basic_block_list))
                        # print(cfg.edgelist)
                        cfg.build_cfg(manager, state)
                        #print(cfg.cfg_edges)
                        cfg.module_name = ast.name
                        cfgs_by_module[module.name].append(deepcopy(cfg))
                        cfg.reset()
                        #print(cfg.paths)

                    state.store[module.name] = {}
                    manager.dependencies[module.name] = {}
                    manager.intermodule_dependencies[module.name] = {}
                    manager.cond_assigns[module.name] = {}
            total_paths = 1
            for x in manager.child_num_paths.values():
                total_paths *= x

            # have do do things piece wise
            manager.debug = self.debug
            if total_paths > 100:
                start = time.process_time()
                self.piece_wise_execute(ast, manager, modules)
                end = time.process_time()
                print(f"Elapsed time {end - start}")
                print(f"Solver time {manager.solver_time}")
                sys.exit()
            self.populate_child_paths(manager)
            if len(modules) > 1:
                self.populate_seen_mod(manager)
                #manager.opt_1 = True
            else:
                manager.opt_1 = False
            manager.modules = modules_dict

            mapped_paths = {}
            #print(total_paths)

        if self.debug:
            manager.debug = True
        self.assertions_always_intersect(manager)

        manager.seen = {}
        for name in manager.names_list:
            manager.seen[name] = []

            # each module has a mapping table of cfg idx to path list
            mapped_paths[name] = {}
        manager.curr_module = manager.names_list[0]

        # index into cfgs list
        curr_cfg = 0
        for module_name in cfgs_by_module:
            for cfg in cfgs_by_module[module_name]:
                mapped_paths[module_name][curr_cfg] = cfg.paths
                curr_cfg += 1
            curr_cfg = 0

        print(mapped_paths)

        stride_length = cfg_count
        single_paths_by_module = {}
        total_paths_by_module = {}
        for module_name in cfgs_by_module:
            single_paths_by_module[module_name] = list(product(*mapped_paths[module_name].values()))
            total_paths_by_module[module_name] = list(tuple(product(single_paths_by_module[module_name], repeat=int(num_cycles))))
        #print(f"tp {total_paths_by_module}")
        keys, values = zip(*total_paths_by_module.items())
        total_paths = [dict(zip(keys, path)) for path in product(*values)]
        #print(total_paths)
        
        #single_paths = list(product(*mapped_paths[manager.curr_module].values()))
        #total_paths = list(tuple(product(single_paths, repeat=int(num_cycles))))

        # for each combinatoin of multicycle paths

        for i in range(len(total_paths)):
            manager.prev_store = state.store
            init_state(state, manager.prev_store, ast)
            # initalize inputs with symbols for all submodules too
            for module_name in manager.names_list:
                manager.curr_module = module_name
                # actually want to terminate this part after the decl and comb part
                self.search_strategy.visit_module(manager, state, ast, modules_dict)
                
            for cfg_idx in range(cfg_count):
                for node in cfgs_by_module[manager.curr_module][cfg_idx].decls:
                    self.search_strategy.visit_stmt(manager, state, node, modules_dict, None)
                for node in cfgs_by_module[manager.curr_module][cfg_idx].comb:
                    self.search_strategy.visit_stmt(manager, state, node, modules_dict, None) 

   
            manager.curr_module = manager.names_list[0]
            # makes assumption top level module is first in line
            # ! no longer path code as in bit string, but indices

            
            self.check_state(manager, state)

            curr_path = total_paths[i]

            modules_seen = 0
            for module_name in curr_path:
                manager.curr_module = manager.names_list[modules_seen]
                manager.cycle = 0
                for complete_single_cycle_path in curr_path[module_name]:
                    for cfg_path in complete_single_cycle_path:
                        directions = cfgs_by_module[module_name][complete_single_cycle_path.index(cfg_path)].compute_direction(cfg_path)
                        k: int = 0
                        for basic_block_idx in cfg_path:
                            if basic_block_idx < 0: 
                                # dummy node
                                continue
                            else:
                                direction = directions[k]
                                k += 1
                                basic_block = cfgs_by_module[module_name][complete_single_cycle_path.index(cfg_path)].basic_block_list[basic_block_idx]
                                for stmt in basic_block:
                                    # print(f"updating curr mod {manager.curr_module}")
                                    #self.check_state(manager, state)
                                    self.search_strategy.visit_stmt(manager, state, stmt, modules_dict, direction)
                                            # only do once, and the last CFG 
                    for node in cfgs_by_module[module_name][cfg_count-1].comb:
                        self.search_strategy.visit_stmt(manager, state, node, modules_dict, None)  
                        print(state.store)
                    manager.cycle += 1
                modules_seen += 1
            manager.cycle = 0
            self.done = True
            self.check_state(manager, state)
            self.done = False

            manager.curr_level = 0
            for module_name in manager.instances_seen:
                manager.instances_seen[module_name] = 0
                manager.instances_loc[module_name] = ""
            if self.debug:
                print("------------------------")
            if (manager.assertion_violation):
                print("Assertion violation")
                #manager.assertion_violation = False
                counterexample = {}
                symbols_to_values = {}
                solver_start = time.process_time()
                if self.solve_pc(state.pc):
                    solver_end = time.process_time()
                    manager.solver_time += solver_end - solver_start
                    solved_model = state.pc.model()
                    decls =  solved_model.decls()
                    for item in decls:
                        symbols_to_values[item.name()] = solved_model[item]

                    # plug in phase
                    for module in state.store:
                        for signal in state.store[module]:
                            for symbol in symbols_to_values:
                                if state.store[module][signal] == symbol:
                                    counterexample[signal] = symbols_to_values[symbol]

                    print(counterexample)
                else:
                    print("UNSAT")
                return
            
            state.pc.reset()

            for module in manager.dependencies:
                module = {}
                
            
            manager.ignore = False
            manager.abandon = False
            manager.reg_writes.clear()
            for name in manager.names_list:
                state.store[name] = {}

        self.module_depth -= 1


    def execute_child(self, ast: ModuleDef, state: SymbolicState, manager: Optional[ExecutionManager]) -> None:
        """Drives symbolic execution of child modules."""
        # different manager
        # same state
        # dont call pc solve
        manager_sub = ExecutionManager()
        manager_sub.is_child = True
        manager_sub.curr_module = ast.name
        self.init_run(manager_sub, ast)

        manager_sub.path_code = manager.config[ast.name]
        manager_sub.seen = manager.seen

        # mark this exploration of the submodule as seen and store the state so we don't have to explore it again.
        if manager.seen_mod[ast.name][manager_sub.path_code] == {}:
            manager.seen_mod[ast.name][manager_sub.path_code] = state.store
        else:
            ...
            #print("already seen this")
        # i'm pretty sure we only ever want to do 1 loop here
        for i in range(1):
        #for i in range(manager_sub.num_paths):
            manager_sub.path_code = manager.config[ast.name]

            self.search_strategy.visit_module(manager_sub, state, ast, manager.modules)
            if (manager.assertion_violation):
                print("Assertion violation")
                manager.assertion_violation = False
                counterexample = {}
                symbols_to_values = {}
                solver_start = time.process_time()
                if self.solve_pc(state.pc):
                    solver_end = time.process_time()
                    manager.solver_time += solver_end - solver_start
                    solved_model = state.pc.model()
                    decls =  solved_model.decls()
                    for item in decls:
                        symbols_to_values[item.name()] = solved_model[item]

                    # plug in phase
                    for module in state.store:
                        for signal in state.store[module]:
                            for symbol in symbols_to_values:
                                if state.store[module][signal] == symbol:
                                    counterexample[signal] = symbols_to_values[symbol]

                    print(counterexample)
                else:
                    print("UNSAT")
            manager.curr_level = 0
            #state.pc.reset()
        #manager.path_code = to_binary(0)
        if manager_sub.ignore:
            manager.ignore = True
        self.module_depth -= 1
        #manager.is_child = False


    def check_state(self, manager, state):
        """Checks the status of the execution and displays the state."""
        if self.done and manager.debug and not manager.is_child and not manager.init_run_flag and not manager.ignore and not manager.abandon:
            print(f"Cycle {manager.cycle} final state:")
            print(state.store)
    
            print(f"Cycle {manager.cycle} final path condition:")
            print(state.pc)
        elif self.done and not manager.is_child and manager.assertion_violation and not manager.ignore and not manager.abandon:
            print(f"Cycle {manager.cycle} initial state:")
            print(manager.initial_store)

            print(f"Cycle {manager.cycle} final state:")
            print(state.store)
    
            print(f"Cycle {manager.cycle} final path condition:")
            print(state.pc)
        elif manager.debug and not manager.is_child and not manager.init_run_flag and not manager.ignore:
            print("Initial state:")
            print(state.store)
                
