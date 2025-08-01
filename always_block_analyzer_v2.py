#!/usr/bin/env python3
"""
Always Block 赋值统计分析器 (基于语法树)
使用pyslang的语法树分析SystemVerilog中always block的赋值操作
"""

import pyslang as ps
import sys
import os
from collections import defaultdict

class AlwaysBlockAssignmentAnalyzer:
    """基于语法树的always block赋值分析器"""
    
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
            
            # 使用语法树分析always块
            trees = driver.syntaxTrees
            print(f"找到 {len(trees)} 个语法树")
            
            for i, tree in enumerate(trees):
                print(f"\n分析语法树 {i}:")
                self.analyze_syntax_tree(tree.root)
                    
            return True
            
        except Exception as e:
            print(f"解析错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def analyze_syntax_tree(self, node):
        """递归分析语法树寻找always块"""
        if node is None:
            return
            
        # 检查是否是always块
        if hasattr(node, 'kind'):
            if node.kind in [ps.SyntaxKind.AlwaysBlock, ps.SyntaxKind.AlwaysCombBlock, 
                           ps.SyntaxKind.AlwaysFFBlock, ps.SyntaxKind.AlwaysLatchBlock]:
                self.analyze_always_block(node)
        
        # 递归遍历子节点
        try:
            for i in range(len(node)):
                child = node[i]
                self.analyze_syntax_tree(child)
        except (TypeError, AttributeError):
            pass
    
    def analyze_always_block(self, always_node):
        """分析单个always块"""
        block_type = str(always_node.kind).replace('SyntaxKind.', '')
        print(f"  分析 {block_type} 块")
        
        block_info = {
            'type': block_type,
            'assignments': [],
            'blocking_count': 0,
            'nonblocking_count': 0,
            'location': str(always_node.sourceRange) if hasattr(always_node, 'sourceRange') else 'unknown'
        }
        
        # 分析always块的语句
        if hasattr(always_node, 'statement') and always_node.statement:
            self.analyze_statement_syntax(always_node.statement, block_info)
            
        if block_info['assignments']:
            self.always_blocks.append(block_info)
            self.assignment_stats['blocks_with_assignments'] += 1
            
            print(f"    发现 {len(block_info['assignments'])} 个赋值操作")
            print(f"    阻塞赋值: {block_info['blocking_count']}")
            print(f"    非阻塞赋值: {block_info['nonblocking_count']}")
        else:
            print(f"    未发现赋值操作")
    
    def analyze_statement_syntax(self, stmt, block_info, depth=0):
        """递归分析语句语法"""
        if stmt is None:
            return
            
        indent = "    " * depth
        
        try:
            kind = stmt.kind
            print(f"{indent}分析语句: {kind}")
            
            if kind == ps.SyntaxKind.ExpressionStatement:
                # 表达式语句 - 可能包含赋值
                print(f"{indent}  -> 表达式语句")
                if hasattr(stmt, 'expression'):
                    self.analyze_expression_syntax(stmt.expression, block_info, depth + 1)
                    
            elif kind == ps.SyntaxKind.SequentialBlockStatement:
                # begin-end块
                print(f"{indent}  -> Sequential块")
                # 通用子节点遍历
                try:
                    child_count = len(stmt)
                    print(f"{indent}    子节点数量: {child_count}")
                    for i in range(child_count):
                        child = stmt[i]
                        if hasattr(child, 'kind'):
                            print(f"{indent}    子节点 {i}: {child.kind}")
                            self.analyze_statement_syntax(child, block_info, depth + 1)
                except (TypeError, AttributeError) as e:
                    print(f"{indent}    无法遍历子节点: {e}")
                        
            elif kind == ps.SyntaxKind.TimingControlStatement:
                # 时序控制语句，分析其包含的语句
                print(f"{indent}  -> 时序控制语句")
                if hasattr(stmt, 'statement'):
                    self.analyze_statement_syntax(stmt.statement, block_info, depth + 1)
                    
            elif kind == ps.SyntaxKind.ConditionalStatement:
                # if-else语句
                print(f"{indent}  -> 条件语句")
                if hasattr(stmt, 'statement'):
                    self.analyze_statement_syntax(stmt.statement, block_info, depth + 1)
                if hasattr(stmt, 'elseClause') and stmt.elseClause:
                    if hasattr(stmt.elseClause, 'clause'):
                        self.analyze_statement_syntax(stmt.elseClause.clause, block_info, depth + 1)
                        
            elif kind == ps.SyntaxKind.CaseStatement:
                # case语句
                print(f"{indent}  -> Case语句")
                if hasattr(stmt, 'items'):
                    for item in stmt.items:
                        if hasattr(item, 'statement'):
                            self.analyze_statement_syntax(item.statement, block_info, depth + 1)
            else:
                print(f"{indent}  -> 其他语句类型: {kind}")
                # 对于未知类型，尝试通用子节点遍历
                try:
                    child_count = len(stmt)
                    if child_count > 0:
                        print(f"{indent}    通用遍历子节点数量: {child_count}")
                        for i in range(child_count):
                            child = stmt[i]
                            if hasattr(child, 'kind'):
                                self.analyze_statement_syntax(child, block_info, depth + 1)
                except (TypeError, AttributeError):
                    pass
                            
        except Exception as e:
            print(f"{indent}语句分析错误: {e}")
    
    def analyze_expression_syntax(self, expr, block_info, depth=0):
        """分析表达式语法，查找赋值操作"""
        if expr is None:
            return
            
        indent = "    " * depth
        
        try:
            kind = expr.kind
            print(f"{indent}分析表达式: {kind}")
            
            if kind == ps.SyntaxKind.AssignmentExpression:
                # 阻塞赋值 =
                print(f"{indent}  -> 找到阻塞赋值!")
                self.process_assignment_syntax(expr, block_info, 'blocking')
                
            elif kind == ps.SyntaxKind.NonblockingAssignmentExpression:
                # 非阻塞赋值 <=
                print(f"{indent}  -> 找到非阻塞赋值!")
                self.process_assignment_syntax(expr, block_info, 'nonblocking')
            else:
                print(f"{indent}  -> 其他表达式类型: {kind}")
                
        except Exception as e:
            print(f"{indent}表达式分析错误: {e}")
    
    def process_assignment_syntax(self, assign_expr, block_info, assign_type):
        """处理单个赋值操作（语法树版本）"""
        try:
            # 获取左值（被赋值的变量）
            left_value = self.extract_variable_name_from_syntax(assign_expr.left)
            
            # 获取右值表达式
            right_value = self.extract_expression_text_from_syntax(assign_expr.right)
            
            assignment_info = {
                'type': assign_type,
                'left': left_value,
                'right': right_value,
                'location': str(assign_expr.sourceRange) if hasattr(assign_expr, 'sourceRange') else 'unknown'
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
            
            print(f"      找到{assign_type}赋值: {left_value} = {right_value}")
            
        except Exception as e:
            print(f"      赋值处理错误: {e}")
    
    def extract_variable_name_from_syntax(self, expr_node):
        """从语法节点提取变量名"""
        if expr_node is None:
            return "unknown"
            
        try:
            kind = expr_node.kind
            
            if kind == ps.SyntaxKind.IdentifierName:
                if hasattr(expr_node, 'identifier'):
                    return str(expr_node.identifier.value)
                    
            elif kind == ps.SyntaxKind.ElementSelectExpression:
                # 数组索引：var[index]
                base = self.extract_variable_name_from_syntax(expr_node.left)
                index = self.extract_expression_text_from_syntax(expr_node.right)
                return f"{base}[{index}]"
                
            elif kind == ps.SyntaxKind.SimpleRangeSelect:
                # 位选择：var[msb:lsb]
                base = self.extract_variable_name_from_syntax(expr_node.left)
                # 对于范围选择，需要获取范围信息
                return f"{base}[range]"
                
            elif kind == ps.SyntaxKind.MemberAccessExpression:
                # 结构体成员：struct.member
                base = self.extract_variable_name_from_syntax(expr_node.left)
                member = self.extract_expression_text_from_syntax(expr_node.right)
                return f"{base}.{member}"
                
            else:
                return f"<{kind}>"
                
        except Exception as e:
            return f"<error:{e}>"
    
    def extract_expression_text_from_syntax(self, expr_node):
        """从语法节点提取表达式文本"""
        if expr_node is None:
            return "null"
            
        try:
            kind = expr_node.kind
            
            if kind == ps.SyntaxKind.IdentifierName:
                if hasattr(expr_node, 'identifier'):
                    return str(expr_node.identifier.value)
                    
            elif kind == ps.SyntaxKind.IntegerLiteralExpression:
                if hasattr(expr_node, 'literal'):
                    return str(expr_node.literal.value)
                    
            elif kind == ps.SyntaxKind.StringLiteralExpression:
                if hasattr(expr_node, 'literal'):
                    return f'"{expr_node.literal.value}"'
                    
            elif kind in [ps.SyntaxKind.AddExpression, ps.SyntaxKind.SubtractExpression,
                         ps.SyntaxKind.MultiplyExpression, ps.SyntaxKind.DivideExpression,
                         ps.SyntaxKind.LogicalAndExpression, ps.SyntaxKind.LogicalOrExpression,
                         ps.SyntaxKind.BinaryAndExpression, ps.SyntaxKind.BinaryOrExpression]:
                # 二元操作
                left = self.extract_expression_text_from_syntax(expr_node.left)
                right = self.extract_expression_text_from_syntax(expr_node.right)
                op = self.get_operator_text(kind)
                return f"({left} {op} {right})"
                
            elif kind in [ps.SyntaxKind.UnaryPlusExpression, ps.SyntaxKind.UnaryMinusExpression,
                         ps.SyntaxKind.UnaryLogicalNotExpression, ps.SyntaxKind.UnaryBitwiseNotExpression]:
                # 一元操作
                operand = self.extract_expression_text_from_syntax(expr_node.operand)
                op = self.get_operator_text(kind)
                return f"({op}{operand})"
                
            elif kind == ps.SyntaxKind.ConditionalExpression:
                # 三元操作符
                cond = self.extract_expression_text_from_syntax(expr_node.predicate)
                true_expr = self.extract_expression_text_from_syntax(expr_node.left)
                false_expr = self.extract_expression_text_from_syntax(expr_node.right)
                return f"({cond} ? {true_expr} : {false_expr})"
                
            else:
                return f"<{kind}>"
                
        except Exception as e:
            return f"<error:{e}>"
    
    def get_operator_text(self, kind):
        """获取操作符文本"""
        op_map = {
            ps.SyntaxKind.AddExpression: '+',
            ps.SyntaxKind.SubtractExpression: '-',
            ps.SyntaxKind.MultiplyExpression: '*',
            ps.SyntaxKind.DivideExpression: '/',
            ps.SyntaxKind.LogicalAndExpression: '&&',
            ps.SyntaxKind.LogicalOrExpression: '||',
            ps.SyntaxKind.BinaryAndExpression: '&',
            ps.SyntaxKind.BinaryOrExpression: '|',
            ps.SyntaxKind.UnaryPlusExpression: '+',
            ps.SyntaxKind.UnaryMinusExpression: '-',
            ps.SyntaxKind.UnaryLogicalNotExpression: '!',
            ps.SyntaxKind.UnaryBitwiseNotExpression: '~'
        }
        return op_map.get(kind, '?')
    
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
            print(f"\n{i}. {block['type']} 块:")
            print(f"   总赋值: {len(block['assignments'])} (阻塞: {block['blocking_count']}, 非阻塞: {block['nonblocking_count']})")
            
            # 显示所有赋值
            for j, assign in enumerate(block['assignments']):
                symbol = '=' if assign['type'] == 'blocking' else '<='
                print(f"   {j+1}. {assign['left']} {symbol} {assign['right']}")

def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python3 always_block_analyzer_v2.py <verilog_file>")
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