#!/usr/bin/env python3
"""
Always Block 赋值统计分析器
使用pyslang分析SystemVerilog中always block的赋值操作
"""

import pyslang as ps
import sys
import os
from collections import defaultdict

class AlwaysBlockAssignmentAnalyzer:
    """专门分析always block中赋值操作的分析器"""
    
    def __init__(self):
        self.always_blocks = []
        self.assignment_stats = {
            'blocking': defaultdict(int),      # 阻塞赋值统计
            'nonblocking': defaultdict(int),   # 非阻塞赋值统计
            'total_by_variable': defaultdict(int),  # 按变量统计总赋值次数
            'blocks_with_assignments': 0,      # 包含赋值的always块数量
            'total_assignments': 0             # 总赋值操作数
        }
        
    def parse_file(self, verilog_file):
        """解析SystemVerilog文件并统计always block中的赋值"""
        print(f"=== 分析文件: {verilog_file} ===")
        
        try:
            # 创建Driver并解析
            driver = ps.Driver()
            driver.addStandardArgs()
            
            # 创建文件列表
            if verilog_file.endswith('.txt') or verilog_file.endswith('.F'):
                driver.processCommandFiles(verilog_file, True, True)
            else:
                # 为单个文件创建临时文件列表
                flist_path = "temp_filelist.F"
                with open(flist_path, "w") as flist:
                    flist.write(verilog_file + "\n")
                driver.processCommandFiles(flist_path, True, True)
                
            driver.processOptions()
            driver.parseAllSources()
            
            # 创建编译单元
            compilation = driver.createCompilation()
            
            # 检查编译
            success = driver.reportCompilation(compilation, False)
            if not success:
                print("编译失败!")
                return False
                
            print("编译成功!")
            
            # 获取根符号和定义
            root = compilation.getRoot()
            definitions = compilation.getDefinitions()
            
            print(f"找到 {len(definitions)} 个模块定义")
            
            # 分析每个模块中的always块
            for definition in definitions:
                if definition.kind == ps.SymbolKind.Definition:
                    self.analyze_module_always_blocks(definition)
            
            # 也分析根实例中的always块        
            root = compilation.getRoot()
            print(f"\n=== 分析根符号 ===")
            print(f"根符号类型: {root.kind}")
            if hasattr(root, 'topInstances'):
                print(f"顶层实例数量: {len(root.topInstances)}")
                for instance in root.topInstances:
                    print(f"  实例: {instance.name}")
                    if hasattr(instance, 'body') and instance.body:
                        self.analyze_instance_members(instance.body)
                    
            return True
            
        except Exception as e:
            print(f"解析错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def analyze_instance_members(self, instance_body):
        """分析实例体中的成员"""
        print(f"    分析实例体: {instance_body.name}")
        try:
            if hasattr(instance_body, 'members'):
                members = list(instance_body.members)
                print(f"    找到 {len(members)} 个实例成员")
                
                for i, member in enumerate(members):
                    print(f"      成员 {i}: {member.kind} - {getattr(member, 'name', 'unnamed')}")
                    if member.kind == ps.SymbolKind.ProceduralBlock:
                        self.analyze_procedural_block(member, instance_body.name)
                        
        except Exception as e:
            print(f"    分析实例成员时出错: {e}")
    
    def analyze_module_always_blocks(self, module_def):
        """分析模块中的always块"""
        print(f"\n=== 分析模块: {module_def.name} ===")
        
        try:
            if hasattr(module_def, 'body') and module_def.body:
                members = list(module_def.body.members)
                print(f"找到 {len(members)} 个模块成员")
                
                for i, member in enumerate(members):
                    print(f"  成员 {i}: {member.kind} - {getattr(member, 'name', 'unnamed')}")
                    if member.kind == ps.SymbolKind.ProceduralBlock:
                        self.analyze_procedural_block(member, module_def.name)
                    elif hasattr(member, 'kind'):
                        # 打印其他类型的成员用于调试
                        print(f"    其他成员类型: {member.kind}")
                        
        except Exception as e:
            print(f"分析模块时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def analyze_procedural_block(self, block, module_name):
        """分析过程块（always, initial等）"""
        block_type = self.get_block_type(block)
        
        # 只分析always类型的块
        if 'always' not in block_type.lower():
            return
            
        print(f"  分析 {block_type} 块")
        
        block_info = {
            'module': module_name,
            'type': block_type,
            'assignments': [],
            'blocking_count': 0,
            'nonblocking_count': 0
        }
        
        if hasattr(block, 'body') and block.body:
            self.analyze_statement_for_assignments(block.body, block_info)
            
        if block_info['assignments']:
            self.always_blocks.append(block_info)
            self.assignment_stats['blocks_with_assignments'] += 1
            
            print(f"    发现 {len(block_info['assignments'])} 个赋值操作")
            print(f"    阻塞赋值: {block_info['blocking_count']}")
            print(f"    非阻塞赋值: {block_info['nonblocking_count']}")
    
    def get_block_type(self, block):
        """获取过程块的类型"""
        if hasattr(block, 'syntax') and block.syntax:
            # 通过语法树确定always块类型
            syntax = block.syntax
            if hasattr(syntax, 'kind'):
                if syntax.kind == ps.SyntaxKind.AlwaysBlock:
                    return 'always'
                elif syntax.kind == ps.SyntaxKind.AlwaysCombBlock:
                    return 'always_comb'
                elif syntax.kind == ps.SyntaxKind.AlwaysFFBlock:
                    return 'always_ff'
                elif syntax.kind == ps.SyntaxKind.AlwaysLatchBlock:
                    return 'always_latch'
                elif syntax.kind == ps.SyntaxKind.InitialBlock:
                    return 'initial'
                elif syntax.kind == ps.SyntaxKind.FinalBlock:
                    return 'final'
        
        return str(block.kind)
    
    def analyze_statement_for_assignments(self, stmt, block_info):
        """递归分析语句中的赋值操作"""
        if stmt is None:
            return
            
        kind = stmt.kind
        
        if kind == ps.StatementKind.ExpressionStatement:
            # 表达式语句 - 可能包含赋值
            if hasattr(stmt, 'expr'):
                self.analyze_expression_for_assignments(stmt.expr, block_info)
                
        elif kind == ps.StatementKind.Block:
            # 语句块
            if hasattr(stmt, 'body'):
                for sub_stmt in stmt.body:
                    self.analyze_statement_for_assignments(sub_stmt, block_info)
                    
        elif kind == ps.StatementKind.List:
            # 语句列表
            for s in stmt.body:
                self.analyze_statement_for_assignments(s, block_info)
                
        elif kind == ps.StatementKind.Conditional:
            # 条件语句
            if stmt.ifTrue:
                self.analyze_statement_for_assignments(stmt.ifTrue, block_info)
            if stmt.ifFalse:
                self.analyze_statement_for_assignments(stmt.ifFalse, block_info)
                
        elif kind == ps.StatementKind.Case:
            # Case语句
            for case in stmt.cases:
                self.analyze_statement_for_assignments(case.stmt, block_info)
                
        elif kind in [ps.StatementKind.WhileLoop, ps.StatementKind.ForLoop, 
                      ps.StatementKind.RepeatLoop, ps.StatementKind.ForeverLoop]:
            # 循环语句
            if hasattr(stmt, 'body') and stmt.body:
                self.analyze_statement_for_assignments(stmt.body, block_info)
    
    def analyze_expression_for_assignments(self, expr, block_info):
        """分析表达式中的赋值操作"""
        if expr is None:
            return
            
        kind = expr.kind
        
        if kind == ps.ExpressionKind.Assignment:
            # 找到赋值表达式
            self.process_assignment(expr, block_info, 'blocking')
            
        elif kind == ps.ExpressionKind.NonblockingAssignment:
            # 非阻塞赋值
            self.process_assignment(expr, block_info, 'nonblocking')
            
        elif kind in [ps.ExpressionKind.BinaryOp, ps.ExpressionKind.ConditionalOp]:
            # 递归检查二元操作和三元操作
            if hasattr(expr, 'left'):
                self.analyze_expression_for_assignments(expr.left, block_info)
            if hasattr(expr, 'right'):
                self.analyze_expression_for_assignments(expr.right, block_info)
            if hasattr(expr, 'predicate'):
                self.analyze_expression_for_assignments(expr.predicate, block_info)
                
        elif kind == ps.ExpressionKind.Call:
            # 函数调用 - 检查参数
            if hasattr(expr, 'arguments'):
                for arg in expr.arguments:
                    self.analyze_expression_for_assignments(arg, block_info)
    
    def process_assignment(self, assign_expr, block_info, assign_type):
        """处理单个赋值操作"""
        try:
            # 获取左值（被赋值的变量）
            left_value = self.extract_variable_name(assign_expr.left)
            
            # 获取右值表达式
            right_value = self.expression_to_string(assign_expr.right)
            
            assignment_info = {
                'type': assign_type,
                'left': left_value,
                'right': right_value,
                'line': getattr(assign_expr, 'sourceRange', 'unknown')
            }
            
            block_info['assignments'].append(assignment_info)
            
            # 更新统计信息
            if assign_type == 'blocking':
                block_info['blocking_count'] += 1
                self.assignment_stats['blocking'][left_value] += 1
            else:
                block_info['nonblocking_count'] += 1
                self.assignment_stats['nonblocking'][left_value] += 1
                
            self.assignment_stats['total_by_variable'][left_value] += 1
            self.assignment_stats['total_assignments'] += 1
            
            print(f"      {assign_type}赋值: {left_value} = {right_value}")
            
        except Exception as e:
            print(f"      赋值处理错误: {e}")
    
    def extract_variable_name(self, expr):
        """从表达式中提取变量名"""
        if expr is None:
            return "unknown"
            
        kind = expr.kind
        
        if kind == ps.ExpressionKind.NamedValue:
            return expr.symbol.name if hasattr(expr, 'symbol') and expr.symbol else "unknown"
        elif kind == ps.ExpressionKind.ElementSelect:
            # 数组索引：var[index]
            base = self.extract_variable_name(expr.value)
            index = self.expression_to_string(expr.selector)
            return f"{base}[{index}]"
        elif kind == ps.ExpressionKind.RangeSelect:
            # 位选择：var[msb:lsb]
            base = self.extract_variable_name(expr.value)
            left = self.expression_to_string(expr.left)
            right = self.expression_to_string(expr.right)
            return f"{base}[{left}:{right}]"
        elif kind == ps.ExpressionKind.MemberAccess:
            # 结构体成员：struct.member
            base = self.extract_variable_name(expr.value)
            member = expr.member.name if hasattr(expr, 'member') else "unknown"
            return f"{base}.{member}"
        else:
            return f"<{kind}>"
    
    def expression_to_string(self, expr):
        """将表达式转换为字符串表示"""
        if expr is None:
            return "null"
            
        kind = expr.kind
        
        if kind == ps.ExpressionKind.NamedValue:
            return expr.symbol.name if hasattr(expr, 'symbol') and expr.symbol else "unknown"
        elif kind == ps.ExpressionKind.IntegerLiteral:
            return str(expr.value) if hasattr(expr, 'value') else "unknown"
        elif kind == ps.ExpressionKind.StringLiteral:
            return f'"{expr.value}"' if hasattr(expr, 'value') else "unknown"
        elif kind == ps.ExpressionKind.BinaryOp:
            left = self.expression_to_string(expr.left)
            right = self.expression_to_string(expr.right)
            op = str(expr.op) if hasattr(expr, 'op') else "?"
            return f"({left} {op} {right})"
        elif kind == ps.ExpressionKind.UnaryOp:
            operand = self.expression_to_string(expr.operand)
            op = str(expr.op) if hasattr(expr, 'op') else "?"
            return f"({op}{operand})"
        elif kind == ps.ExpressionKind.ConditionalOp:
            cond = self.expression_to_string(expr.predicate)
            true_expr = self.expression_to_string(expr.left)
            false_expr = self.expression_to_string(expr.right)
            return f"({cond} ? {true_expr} : {false_expr})"
        else:
            return f"<{kind}>"
    
    def print_statistics(self):
        """打印详细的赋值统计信息"""
        print(f"\n{'='*60}")
        print(f"Always Block 赋值统计分析结果")
        print(f"{'='*60}")
        
        print(f"\n总体统计:")
        print(f"- 分析的always块数量: {len(self.always_blocks)}")
        print(f"- 包含赋值的always块: {self.assignment_stats['blocks_with_assignments']}")
        print(f"- 总赋值操作数: {self.assignment_stats['total_assignments']}")
        
        # 按赋值类型统计
        total_blocking = sum(self.assignment_stats['blocking'].values())
        total_nonblocking = sum(self.assignment_stats['nonblocking'].values())
        
        print(f"\n赋值类型分布:")
        print(f"- 阻塞赋值 (=): {total_blocking}")
        print(f"- 非阻塞赋值 (<=): {total_nonblocking}")
        
        # 按变量统计赋值次数
        if self.assignment_stats['total_by_variable']:
            print(f"\n变量赋值次数排名:")
            sorted_vars = sorted(self.assignment_stats['total_by_variable'].items(), 
                               key=lambda x: x[1], reverse=True)
            for var, count in sorted_vars[:10]:  # 显示前10个
                blocking = self.assignment_stats['blocking'][var]
                nonblocking = self.assignment_stats['nonblocking'][var]
                print(f"- {var}: {count} 次 (阻塞: {blocking}, 非阻塞: {nonblocking})")
        
        # 详细的always块信息
        print(f"\n详细的Always块分析:")
        for i, block in enumerate(self.always_blocks, 1):
            print(f"\n{i}. 模块 {block['module']} - {block['type']} 块:")
            print(f"   总赋值: {len(block['assignments'])} (阻塞: {block['blocking_count']}, 非阻塞: {block['nonblocking_count']})")
            
            # 显示前5个赋值
            for j, assign in enumerate(block['assignments'][:5]):
                print(f"   {j+1}. {assign['type']}: {assign['left']} = {assign['right']}")
            
            if len(block['assignments']) > 5:
                print(f"   ... 还有 {len(block['assignments']) - 5} 个赋值")

def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python3 always_block_analyzer.py <verilog_file>")
        sys.exit(1)
        
    verilog_file = sys.argv[1]
    if not os.path.exists(verilog_file):
        print(f"文件不存在: {verilog_file}")
        sys.exit(1)
        
    analyzer = AlwaysBlockAssignmentAnalyzer()
    
    if analyzer.parse_file(verilog_file):
        analyzer.print_statistics()
    else:
        print("分析失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()