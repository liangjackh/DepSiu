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


class SystemVerilogParser:
    """SystemVerilog解析器"""
    
    def __init__(self):
        self.modules = []
        self.current_module = None
        
    def parse_file(self, filename: str) -> List[ModuleInfo]:
        """解析SystemVerilog文件"""
        try:
            # 创建语法树
            tree = SyntaxTree.fromFile(filename)
            if len(tree.diagnostics) > 0:
                print(f"警告: 文件 {filename} 有语法错误:")
                for diag in tree.diagnostics:
                    print(f"  {diag}")
            
            # 创建编译单元
            compilation = Compilation()
            compilation.addSyntaxTree(tree)
            
            # 解析所有模块
            self._parse_modules(compilation)
            
            return self.modules
            
        except Exception as e:
            print(f"解析文件 {filename} 时出错: {e}")
            return []
    
    def parse_text(self, text: str) -> List[ModuleInfo]:
        """解析SystemVerilog文本"""
        try:
            # 创建语法树
            tree = SyntaxTree.fromText(text)
            if len(tree.diagnostics) > 0:
                print("警告: 文本有语法错误:")
                for diag in tree.diagnostics:
                    print(f"  {diag}")
            
            # 创建编译单元
            compilation = Compilation()
            compilation.addSyntaxTree(tree)
            
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
        
        for instance in top_instances:
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
            
            return ModuleInfo(
                name=module_name,
                ports=ports,
                instances=instances,
                always_blocks=always_blocks,
                assignments=assignments,
                control_flows=control_flows
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
        try:
            sensitivity_list = []
            block_type = "unknown"
            statements = []
            
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
    
    def _get_location(self, obj) -> Optional[str]:
        """获取对象在源码中的位置"""
        try:
            if hasattr(obj, 'location'):
                return str(obj.location)
        except:
            pass
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