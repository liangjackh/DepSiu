#!/usr/bin/env python3
"""
SystemVerilog语法解析工具
使用pyslang库解析SystemVerilog代码，识别模块、always块、赋值语句和控制流语句
"""

import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pyslang import *


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    ports: List[str]
    instances: List[str]
    always_blocks: List[Dict[str, Any]]
    assignments: List[Dict[str, Any]]
    control_flows: List[Dict[str, Any]]
    assertions: List[Dict[str, Any]]


@dataclass
class AlwaysBlockInfo:
    """Always块信息"""
    sensitivity_list: List[str]
    block_type: str  # combinational, sequential, etc.
    statements: List[Dict[str, Any]]


@dataclass
class AssignmentInfo:
    """赋值语句信息"""
    assignment_type: str  # blocking, non-blocking, continuous
    target: str
    source: str
    location: Optional[str] = None


@dataclass
class ControlFlowInfo:
    """控制流语句信息"""
    statement_type: str  # if, case, for, while, etc.
    condition: Optional[str] = None
    location: Optional[str] = None


@dataclass
class AssertInfo:
    """断言语句信息"""
    assert_type: str  # assert, assume, cover, etc.
    condition: str
    signals: List[str]  # 断言中涉及的信号
    location: Optional[str] = None


class SystemVerilogParser:
    """SystemVerilog解析器"""
    
    def __init__(self):
        self.modules = []
        self.current_module = None
        self.source_manager = None
        self.source_text = None  # 保存源码文本用于行号计算
        
    def parse_file(self, filename: str) -> List[ModuleInfo]:
        """解析SystemVerilog文件"""
        try:
            # 读取源码文本
            with open(filename, 'r', encoding='utf-8') as f:
                self.source_text = f.read()
            
            # 创建语法树
            tree = SyntaxTree.fromFile(filename)
            if len(tree.diagnostics) > 0:
                print(f"警告: 文件 {filename} 有语法错误:")
                for diag in tree.diagnostics:
                    print(f"  {diag}")
            
            # 创建编译单元
            compilation = Compilation()
            compilation.addSyntaxTree(tree)
            print(f"compilation type: {type(compilation)}")
            
            # 保存源码管理器用于位置信息转换
            self.source_manager = compilation.sourceManager
            
            # 解析所有模块
            self._parse_modules(compilation)
            
            return self.modules
            
        except Exception as e:
            print(f"解析文件 {filename} 时出错: {e}")
            return []
    
    def parse_text(self, text: str) -> List[ModuleInfo]:
        """解析SystemVerilog文本"""
        try:
            # 保存源码文本
            self.source_text = text
            
            # 创建语法树
            tree = SyntaxTree.fromText(text)
            if len(tree.diagnostics) > 0:
                print("警告: 文本有语法错误:")
                for diag in tree.diagnostics:
                    print(f"  {diag}")
            
            # 创建编译单元
            compilation = Compilation()
            compilation.addSyntaxTree(tree)
            
            # 保存源码管理器用于位置信息转换
            self.source_manager = compilation.sourceManager
            
            # 解析所有模块
            self._parse_modules(compilation)
            
            return self.modules
            
        except Exception as e:
            print(f"解析文本时出错: {e}")
            return []
    
    def _parse_modules(self, compilation: Compilation):
        """解析所有模块"""
        self.modules = []
        
        # 获取顶层实例
        top_instances = compilation.getRoot().topInstances
        
        for instance in top_instances: # instanceSymbol
            print(f"解析模块 from top: {instance.name}, type: {type(instance)}")
            module_info = self._parse_module(instance)
            if module_info:
                self.modules.append(module_info)
    
    def _parse_module(self, instance) -> Optional[ModuleInfo]:
        """解析单个模块"""
        try:
            module_name = instance.name
            
            # 获取端口信息
            ports = self._extract_ports(instance)
            
            # 获取实例信息
            instances = self._extract_instances(instance)
            
            # 获取always块
            always_blocks = self._extract_always_blocks(instance)
            
            # 获取赋值语句
            assignments = self._extract_assignments(instance)
            
            # 获取控制流语句
            control_flows = self._extract_control_flows(instance)
            
            # 获取断言语句
            assertions = self._extract_assertions(instance)
            
            return ModuleInfo(
                name=module_name,
                ports=ports,
                instances=instances,
                always_blocks=always_blocks,
                assignments=assignments,
                control_flows=control_flows,
                assertions=assertions
            )
            
        except Exception as e:
            print(f"解析模块时出错: {e}")
            return None
    
    def _extract_ports(self, instance) -> List[str]:
        """提取端口信息"""
        ports = []
        try:
            for port in instance.getPortConnections():
                if hasattr(port, 'name'):
                    ports.append(port.name)
        except:
            pass
        return ports
    
    def _extract_instances(self, instance) -> List[str]:
        """提取实例信息"""
        instances = []
        try:
            for member in instance.body:
                if hasattr(member, 'kind') and 'Instance' in str(member.kind):
                    instances.append(member.name)
        except:
            pass
        return instances
    
    def _extract_always_blocks(self, instance) -> List[Dict[str, Any]]:
        """提取always块信息"""
        always_blocks = []
        
        class AlwaysBlockVisitor:
            def __init__(self):
                self.blocks = []
            
            def __call__(self, obj):
                if isinstance(obj, ProceduralBlockSymbol):
                    block_info = self._parse_always_block(obj)
                    if block_info:
                        self.blocks.append(block_info)
        
        visitor = AlwaysBlockVisitor()
        visitor._parse_always_block = self._parse_always_block
        
        try:
            instance.visit(visitor)
            always_blocks = visitor.blocks
        except:
            pass
            
        return always_blocks
    
    def _parse_always_block(self, block) -> Optional[Dict[str, Any]]:
        """解析always块"""
        print(f"[DEBUG] analyzing always_block: {block.name}, type: {type(block)}")
        try:
            sensitivity_list = []
            block_type = "unknown"
            statements = []

            if hasattr(block, 'body'):
                print(f"[DEBUG] always_block {block.kind} body: {block.body}, type: {type(block.body)}")
            else:
                print(f"[DEBUG] always_block {block.kind} has no body")
            
            # 获取敏感列表
            if hasattr(block, 'body') and isinstance(block.body, TimedStatement):
                timing_control = block.body.timing
                if isinstance(timing_control, TimingControl):
                    sensitivity_list = self._extract_sensitivity_list(timing_control)
                    
                    # 判断块类型
                    if any('clk' in var.lower() or 'clock' in var.lower() for var in sensitivity_list):
                        block_type = "sequential"
                    elif '*' in str(timing_control) or len(sensitivity_list) > 1:
                        block_type = "combinational"
                
                # 提取语句
                statements = self._extract_statements(block.body.stmt)
            
            return {
                'sensitivity_list': sensitivity_list,
                'block_type': block_type,
                'statements': statements
            }
            
        except Exception as e:
            print(f"解析always块时出错: {e}")
            return None
    
    def _extract_sensitivity_list(self, timing_control) -> List[str]:
        """提取敏感列表"""
        sensitivity_vars = []
        
        class SensitivityExtractor:
            def __init__(self):
                self.vars = []
            
            def __call__(self, obj):
                if isinstance(obj, SignalEventControl):
                    if isinstance(obj.expr, NamedValueExpression):
                        var_ref = obj.expr.getSymbolReference()
                        if var_ref:
                            self.vars.append(var_ref.name)
        
        try:
            extractor = SensitivityExtractor()
            timing_control.visit(extractor)
            sensitivity_vars = extractor.vars
        except:
            pass
            
        return sensitivity_vars
    
    def _extract_statements(self, stmt) -> List[Dict[str, Any]]:
        """提取语句信息"""
        statements = []
        
        class StatementVisitor:
            def __init__(self):
                self.stmts = []
            
            def __call__(self, obj):
                if isinstance(obj, Statement):
                    stmt_info = self._parse_statement(obj)
                    if stmt_info:
                        self.stmts.append(stmt_info)
        
        visitor = StatementVisitor()
        visitor._parse_statement = self._parse_statement
        
        try:
            stmt.visit(visitor)
            statements = visitor.stmts
        except:
            pass
            
        return statements
    
    def _parse_statement(self, stmt) -> Optional[Dict[str, Any]]:
        """解析单个语句"""
        try:
            stmt_type = str(stmt.kind).replace('StatementKind.', '')
            
            return {
                'type': stmt_type,
                'location': self._get_location(stmt)
            }
        except:
            return None
    
    def _extract_assignments(self, instance) -> List[Dict[str, Any]]:
        """提取赋值语句"""
        assignments = []
        
        class AssignmentVisitor:
            def __init__(self):
                self.assignments = []
            
            def __call__(self, obj):
                # 连续赋值
                if hasattr(obj, 'kind') and obj.kind == SymbolKind.ContinuousAssign:
                    assign_info = {
                        'type': 'continuous',
                        'target': str(obj.assignment.left) if hasattr(obj, 'assignment') else 'unknown',
                        'source': str(obj.assignment.right) if hasattr(obj, 'assignment') else 'unknown',
                        'location': self._get_location(obj)
                    }
                    self.assignments.append(assign_info)
                
                # 过程赋值
                elif isinstance(obj, AssignmentExpression):
                    assign_type = 'blocking' if obj.isBlocking else 'non_blocking'
                    assign_info = {
                        'type': assign_type,
                        'target': str(obj.left),
                        'source': str(obj.right),
                        'location': self._get_location(obj)
                    }
                    self.assignments.append(assign_info)
        
        visitor = AssignmentVisitor()
        visitor._get_location = self._get_location
        
        try:
            instance.visit(visitor)
            assignments = visitor.assignments
        except:
            pass
            
        return assignments
    
    def _extract_control_flows(self, instance) -> List[Dict[str, Any]]:
        """提取控制流语句"""
        control_flows = []
        
        class ControlFlowVisitor:
            def __init__(self):
                self.flows = []
            
            def __call__(self, obj):
                if isinstance(obj, Statement):
                    stmt_kind = str(obj.kind)
                    
                    if 'If' in stmt_kind:
                        condition_str = None
                        try:
                            if hasattr(obj, 'cond'):
                                condition_str = str(obj.cond)
                        except:
                            condition_str = None
                            
                        flow_info = {
                            'type': 'if',
                            'condition': condition_str,
                            'location': self._get_location(obj)
                        }
                        self.flows.append(flow_info)
                    
                    elif 'Case' in stmt_kind:
                        condition_str = None
                        try:
                            if hasattr(obj, 'expr'):
                                condition_str = str(obj.expr)
                        except:
                            condition_str = None
                        
                        flow_info = {
                            'type': 'case',
                            'condition': condition_str,
                            'location': self._get_location(obj)
                        }
                        self.flows.append(flow_info)
                    
                    elif 'For' in stmt_kind:
                        flow_info = {
                            'type': 'for',
                            'location': self._get_location(obj)
                        }
                        self.flows.append(flow_info)
                    
                    elif 'While' in stmt_kind:
                        condition_str = None
                        try:
                            if hasattr(obj, 'cond'):
                                condition_str = str(obj.cond)
                        except:
                            condition_str = None
                            
                        flow_info = {
                            'type': 'while',
                            'condition': condition_str,
                            'location': self._get_location(obj)
                        }
                        self.flows.append(flow_info)
        
        visitor = ControlFlowVisitor()
        visitor._get_location = self._get_location
        
        try:
            instance.visit(visitor)
            control_flows = visitor.flows
        except:
            pass
            
        return control_flows
    
    def _extract_assertions(self, instance) -> List[Dict[str, Any]]:
        """提取断言语句"""
        assertions = []
        
        class AssertionVisitor:
            def __init__(self):
                self.assertions = []
            
            def __call__(self, obj):
                if isinstance(obj, Statement):
                    stmt_kind = str(obj.kind)
                    
                    if 'Assert' in stmt_kind or 'Assume' in stmt_kind or 'Cover' in stmt_kind:
                        assert_type = stmt_kind.replace('StatementKind.', '').lower()
                        condition_str = None
                        signals = []
                        
                        try:
                            # 处理不同类型的断言
                            if 'Immediate' in stmt_kind:
                                # 立即断言 (assert, assume, cover)
                                if hasattr(obj, 'cond'):
                                    condition_str = str(obj.cond)
                                    signals = self._extract_signals_from_expression(obj.cond)
                                elif hasattr(obj, 'expr'):
                                    condition_str = str(obj.expr)
                                    signals = self._extract_signals_from_expression(obj.expr)
                            elif 'Concurrent' in stmt_kind:
                                # 并发断言 (property assertions)
                                if hasattr(obj, 'propertySpec') and obj.propertySpec:
                                    condition_str = str(obj.propertySpec)
                                    # 尝试从property spec中提取信号
                                    signals = self._extract_signals_from_expression(obj.propertySpec)
                                elif hasattr(obj, 'body') and obj.body:
                                    condition_str = str(obj.body)
                                    signals = self._extract_signals_from_expression(obj.body)
                        except Exception as e:
                            print(f"解析断言条件时出错: {e}")
                            condition_str = None
                        
                        assert_info = {
                            'type': assert_type,
                            'condition': condition_str,
                            'signals': signals,
                            'location': self._get_location(obj)
                        }
                        self.assertions.append(assert_info)
        
        visitor = AssertionVisitor()
        visitor._get_location = self._get_location
        visitor._extract_signals_from_expression = self._extract_signals_from_expression
        
        try:
            instance.visit(visitor)
            assertions = visitor.assertions
        except Exception as e:
            print(f"提取断言时出错: {e}")
            pass
            
        return assertions
    
    def _extract_signals_from_expression(self, expr) -> List[str]:
        """从表达式中提取信号名称"""
        signals = []
        
        class SignalExtractor:
            def __init__(self):
                self.signals = set()
            
            def __call__(self, obj):
                if isinstance(obj, NamedValueExpression):
                    symbol_ref = obj.getSymbolReference()
                    if symbol_ref and hasattr(symbol_ref, 'name'):
                        self.signals.add(symbol_ref.name)
                elif hasattr(obj, 'symbol') and hasattr(obj.symbol, 'name'):
                    self.signals.add(obj.symbol.name)
        
        try:
            extractor = SignalExtractor()
            
            # 处理不同类型的表达式
            if hasattr(expr, 'visit'):
                expr.visit(extractor)
            elif hasattr(expr, 'expr') and hasattr(expr.expr, 'visit'):
                # 对于ClockingAssertionExpr等复合表达式，递归访问子表达式
                expr.expr.visit(extractor)
            elif hasattr(expr, 'body') and hasattr(expr.body, 'visit'):
                expr.body.visit(extractor)
            else:
                # 尝试直接从字符串表示中提取信号名（粗略方法）
                expr_str = str(expr)
                import re
                # 简单的正则表达式匹配可能的信号名
                potential_signals = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expr_str)
                for sig in potential_signals:
                    # 过滤掉常见的关键字、操作符和类名
                    if sig not in ['posedge', 'negedge', 'disable', 'iff', 'property', 'assert', 'assume', 'cover', 'past',
                                   'AssertionExpr', 'AssertionExprKind', 'Clocking', 'Expression', 'ExpressionKind', 'BinaryOp']:
                        extractor.signals.add(sig)
            
            signals = list(extractor.signals)
        except Exception as e:
            print(f"从表达式提取信号时出错: {e}")
            # 最后的备用方案：从字符串表示中提取
            try:
                expr_str = str(expr)
                import re
                potential_signals = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expr_str)
                signals = [sig for sig in potential_signals 
                          if sig not in ['posedge', 'negedge', 'disable', 'iff', 'property', 'assert', 'assume', 'cover', 'past',
                                         'AssertionExpr', 'AssertionExprKind', 'Clocking', 'Expression', 'ExpressionKind', 'BinaryOp']]
                signals = list(set(signals))  # 去重
            except:
                pass
            
        return signals
    
    def _get_location(self, obj) -> Optional[str]:
        """获取对象在源码中的位置"""
        try:
            # 尝试多种可能的位置属性
            if hasattr(obj, 'location') and obj.location:
                loc = obj.location
                return self._format_location(loc)
            elif hasattr(obj, 'sourceRange') and obj.sourceRange:
                return self._format_location(obj.sourceRange)
            elif hasattr(obj, 'syntax') and obj.syntax and hasattr(obj.syntax, 'sourceRange'):
                return self._format_location(obj.syntax.sourceRange)
            elif hasattr(obj, 'getLocation'):
                loc = obj.getLocation()
                if loc:
                    return self._format_location(loc)
            elif hasattr(obj, 'range'):
                return self._format_location(obj.range)
        except Exception as e:
            print(f"获取位置信息时出错: {e}")
            pass
        return None
    
    def _format_location(self, loc) -> str:
        """格式化位置信息"""
        try:
            # 尝试使用SourceManager转换位置信息
            if self.source_manager and hasattr(loc, 'start'):
                try:
                    # 对于SourceRange，获取开始位置
                    start_loc = loc.start
                    if hasattr(start_loc, 'buffer') and hasattr(start_loc, 'offset'):
                        # 尝试从源码管理器获取行列信息
                        line_col = self.source_manager.getLineColumn(start_loc)
                        if line_col:
                            line, col = line_col
                            return f"行 {line}:{col}"
                except:
                    pass
            
            # 尝试获取行列信息
            if hasattr(loc, 'start') and hasattr(loc, 'end'):
                start = loc.start
                end = loc.end
                if hasattr(start, 'line') and hasattr(start, 'column'):
                    if hasattr(end, 'line') and hasattr(end, 'column'):
                        return f"行 {start.line}:{start.column}-{end.line}:{end.column}"
                    else:
                        return f"行 {start.line}:{start.column}"
                elif hasattr(start, 'offset'):
                    # 尝试手动计算行号
                    line_col = self._offset_to_line_column(start.offset)
                    if line_col:
                        line, col = line_col
                        return f"行 {line}:{col}"
                    return f"偏移 {start.offset}"
            elif hasattr(loc, 'line') and hasattr(loc, 'column'):
                return f"行 {loc.line}:{loc.column}"
            elif hasattr(loc, 'offset'):
                line_col = self._offset_to_line_column(loc.offset)
                if line_col:
                    line, col = line_col
                    return f"行 {line}:{col}"
                return f"偏移 {loc.offset}"
            else:
                # 如果无法提取具体信息，返回字符串表示
                loc_str = str(loc)
                if 'line' in loc_str.lower() or 'offset' in loc_str.lower():
                    return loc_str
                else:
                    return f"位置 {loc_str}"
        except Exception as e:
            print(f"格式化位置信息时出错: {e}")
            pass
        return str(loc)
    
    def _offset_to_line_column(self, offset: int) -> Optional[tuple]:
        """将字符偏移转换为行列号"""
        if not self.source_text or offset < 0:
            return None
        
        try:
            # 计算行号
            text_before_offset = self.source_text[:offset]
            line = text_before_offset.count('\n') + 1
            
            # 计算列号
            last_newline = text_before_offset.rfind('\n')
            if last_newline == -1:
                column = offset + 1
            else:
                column = offset - last_newline
            
            return (line, column)
        except:
            return None
    
    def print_analysis(self, modules: List[ModuleInfo]):
        """打印分析结果"""
        print("=" * 60)
        print("SystemVerilog 代码分析结果")
        print("=" * 60)
        
        for i, module in enumerate(modules):
            print(f"\n模块 {i+1}: {module.name}")
            print("-" * 40)
            
            # 端口信息
            if module.ports:
                print(f"端口 ({len(module.ports)}): {', '.join(module.ports)}")
            
            # 实例信息
            if module.instances:
                print(f"实例 ({len(module.instances)}): {', '.join(module.instances)}")
            
            # Always块信息
            if module.always_blocks:
                print(f"\nAlways块 ({len(module.always_blocks)}):")
                for j, block in enumerate(module.always_blocks):
                    print(f"  块 {j+1}: {block['block_type']}")
                    if block['sensitivity_list']:
                        print(f"    敏感列表: {', '.join(block['sensitivity_list'])}")
                    print(f"    语句数量: {len(block['statements'])}")
            
            # 赋值语句信息
            if module.assignments:
                print(f"\n赋值语句 ({len(module.assignments)}):")
                for assign in module.assignments[:5]:  # 只显示前5个
                    print(f"  {assign['type']}: {assign['target']} = {assign['source']}")
                if len(module.assignments) > 5:
                    print(f"  ... 还有 {len(module.assignments) - 5} 个赋值语句")
            
            # 控制流语句信息
            if module.control_flows:
                print(f"\n控制流语句 ({len(module.control_flows)}):")
                for flow in module.control_flows[:5]:  # 只显示前5个
                    try:
                        if flow.get('condition'):
                            print(f"  {flow['type']}: {flow['condition']}")
                        else:
                            print(f"  {flow['type']}")
                    except Exception as e:
                        print(f"  {flow['type']}: <无法显示条件>")
                if len(module.control_flows) > 5:
                    print(f"  ... 还有 {len(module.control_flows) - 5} 个控制流语句")
            
            # 断言语句信息
            if module.assertions:
                print(f"\n断言语句 ({len(module.assertions)}):")
                for assertion in module.assertions:
                    try:
                        print(f"  {assertion['type']}: {assertion['condition']}")
                        if assertion['signals']:
                            print(f"    涉及信号: {', '.join(assertion['signals'])}")
                    except Exception as e:
                        print(f"  {assertion['type']}: <无法显示断言信息>")


def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python sv_parser.py <systemverilog_file>")
        sys.exit(1)
    
    filename = sys.argv[1]
    parser = SystemVerilogParser()
    
    try:
        modules = parser.parse_file(filename)
        parser.print_analysis(modules)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()