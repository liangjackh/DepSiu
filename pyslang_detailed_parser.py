#!/usr/bin/env python3
"""
完整的pyslang SystemVerilog解析示例
展示如何解析模块、实例、语句和表达式的细粒度信息
"""

import pyslang as ps
import sys
import os

class DetailedSystemVerilogParser:
    """详细的SystemVerilog解析器，支持细粒度解析到表达式级别"""
    
    def __init__(self):
        self.modules = {}
        self.instances = {}
        self.assignments = []
        self.always_blocks = []
        self.expressions = []
        
    def parse_file(self, verilog_file):
        """解析SystemVerilog文件"""
        print(f"=== 开始解析文件: {verilog_file} ===")
        
        try:
            # 1. 创建Driver并解析
            driver = ps.Driver()
            driver.addStandardArgs()
            
            # 处理文件列表或单个文件
            if verilog_file.endswith('.txt') or verilog_file.endswith('.F'):
                # 文件列表格式
                driver.processCommandFiles(verilog_file, True, True)
            else:
                # 单个文件
                driver.addSourceText(verilog_file)
                
            driver.processOptions()
            driver.parseAllSources()
            
            # 2. 创建编译单元
            compilation = driver.createCompilation()
            
            # 3. 检查编译是否成功
            success = driver.reportCompilation(compilation, False)  # 不输出详细信息
            if not success:
                print("编译失败!")
                return False
                
            print(f"编译成功!")
            
            # 4. 获取根符号和所有模块定义
            root = compilation.getRoot()
            definitions = compilation.getDefinitions()
            
            print(f"找到 {len(definitions)} 个模块定义")
            
            # 5. 解析每个模块
            for definition in definitions:
                if definition.kind == ps.SymbolKind.Definition:
                    self.parse_module(definition)
                
            # 6. 解析顶层实例
            print(f"\n=== 顶层实例 ===")
            for instance in root.topInstances:
                self.parse_instance(instance)
                
            return True
            
        except Exception as e:
            print(f"解析过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def parse_module(self, module_def):
        """解析模块定义"""
        print(f"\n=== 解析模块: {module_def.name} ===")
        print(f"模块类型: {type(module_def)}")
        print(f"层次路径: {module_def.hierarchicalPath}")
        
        # 存储模块信息
        module_info = {
            'name': module_def.name,
            'kind': module_def.kind,
            'ports': [],
            'parameters': [],
            'variables': [],
            'nets': [],
            'instances': [],
            'procedural_blocks': [],
            'continuous_assigns': []
        }
        
        # 遍历模块的所有成员 - 使用正确的API
        try:
            # 对于DefinitionSymbol，我们需要遍历其body中的成员
            if hasattr(module_def, 'body') and module_def.body:
                members = list(module_def.body.members)
                print(f"模块成员数量: {len(members)}")
                
                for member in members:
                    self.parse_module_member(member, module_info)
            else:
                print("模块没有body或members")
                
        except Exception as e:
            print(f"遍历模块成员时出错: {e}")
            
        self.modules[module_def.name] = module_info
        
        # 打印模块摘要
        self.print_module_summary(module_info)
    
    def parse_module_member(self, member, module_info):
        """解析模块成员"""
        if member.kind == ps.SymbolKind.Port:
            port_info = {
                'name': member.name,
                'direction': str(member.direction) if hasattr(member, 'direction') else 'unknown',
                'type': str(member.type) if hasattr(member, 'type') else 'unknown'
            }
            module_info['ports'].append(port_info)
            print(f"  端口: {member.name} ({port_info['direction']}, {port_info['type']})")
            
        elif member.kind == ps.SymbolKind.Parameter:
            param_info = {
                'name': member.name,
                'type': str(member.type) if hasattr(member, 'type') else 'unknown',
                'value': str(member.value) if hasattr(member, 'value') else 'unknown'
            }
            module_info['parameters'].append(param_info)
            print(f"  参数: {member.name} = {param_info['value']}")
            
        elif member.kind == ps.SymbolKind.Variable:
            var_info = {
                'name': member.name,
                'type': str(member.type) if hasattr(member, 'type') else 'unknown'
            }
            module_info['variables'].append(var_info)
            print(f"  变量: {member.name} ({var_info['type']})")
            
        elif member.kind == ps.SymbolKind.Net:
            net_info = {
                'name': member.name,
                'type': str(member.type) if hasattr(member, 'type') else 'unknown'
            }
            module_info['nets'].append(net_info)
            print(f"  线网: {member.name} ({net_info['type']})")
            
        elif member.kind == ps.SymbolKind.Instance:
            instance_info = self.parse_instance(member)
            module_info['instances'].append(instance_info)
            
        elif member.kind == ps.SymbolKind.ProceduralBlock:
            block_info = self.parse_procedural_block(member)
            module_info['procedural_blocks'].append(block_info)
            
        elif member.kind == ps.SymbolKind.ContinuousAssign:
            assign_info = self.parse_continuous_assign(member)
            module_info['continuous_assigns'].append(assign_info)
            
    def parse_instance(self, instance):
        """解析模块实例"""
        print(f"  实例: {instance.name}")
        definition_name = "unknown"
        
        try:
            if hasattr(instance, 'body') and instance.body:
                definition_name = instance.body.name
            elif hasattr(instance, 'definition') and instance.definition:
                definition_name = instance.definition.name
        except:
            pass
            
        print(f"    定义: {definition_name}")
        
        instance_info = {
            'name': instance.name,
            'definition': definition_name,
            'connections': []
        }
        
        # 解析端口连接
        try:
            if hasattr(instance, 'body') and instance.body and hasattr(instance.body, 'portConnections'):
                for connection in instance.body.portConnections:
                    conn_info = self.parse_port_connection(connection)
                    instance_info['connections'].append(conn_info)
        except Exception as e:
            print(f"    端口连接解析失败: {e}")
                
        return instance_info
    
    def parse_port_connection(self, connection):
        """解析端口连接"""
        try:
            port_name = "unknown"
            expr_text = "unconnected"
            
            if hasattr(connection, 'port') and connection.port:
                port_name = connection.port.name
                
            if hasattr(connection, 'expression') and connection.expression:
                expr_text = self.parse_expression(connection.expression)
                
            conn_info = {
                'port': port_name,
                'expression': expr_text
            }
            print(f"      连接: .{conn_info['port']}({conn_info['expression']})")
            return conn_info
        except Exception as e:
            print(f"      端口连接解析错误: {e}")
            return {'port': 'error', 'expression': 'error'}
    
    def parse_procedural_block(self, block):
        """解析过程块(always, initial等)"""
        print(f"  过程块: {block.kind}")
        
        block_info = {
            'kind': str(block.kind),
            'statements': []
        }
        
        if hasattr(block, 'body') and block.body:
            statements = self.parse_statement(block.body)
            block_info['statements'] = statements
            
        return block_info
    
    def parse_continuous_assign(self, assign):
        """解析连续赋值语句"""
        print(f"  连续赋值")
        
        try:
            left_expr = "unknown"
            right_expr = "unknown"
            
            if hasattr(assign, 'assignment') and assign.assignment:
                if hasattr(assign.assignment, 'left'):
                    left_expr = self.parse_expression(assign.assignment.left)
                if hasattr(assign.assignment, 'right'):
                    right_expr = self.parse_expression(assign.assignment.right)
            
            assign_info = {
                'left': left_expr,
                'right': right_expr
            }
            
            print(f"    {assign_info['left']} = {assign_info['right']}")
            return assign_info
        except Exception as e:
            print(f"    连续赋值解析错误: {e}")
            return {'left': 'error', 'right': 'error'}
    
    def parse_statement(self, stmt):
        """递归解析语句"""
        if stmt is None:
            return []
            
        statements = []
        kind = stmt.kind
        
        print(f"    语句类型: {kind}")
        
        if kind == ps.StatementKind.ExpressionStatement:
            # 表达式语句
            expr_info = self.parse_expression(stmt.expr)
            statements.append({
                'type': 'expression',
                'expression': expr_info
            })
            
        elif kind == ps.StatementKind.Block:
            # 语句块
            if hasattr(stmt, 'body'):
                for sub_stmt in stmt.body:
                    statements.extend(self.parse_statement(sub_stmt))
                    
        elif kind == ps.StatementKind.Conditional:
            # 条件语句 (if-else)
            cond_info = {
                'type': 'conditional',
                'condition': None,
                'if_true': [],
                'if_false': []
            }
            
            if stmt.conditions:
                cond_info['condition'] = self.parse_expression(stmt.conditions[0].expr)
                print(f"      条件: {cond_info['condition']}")
                
            if stmt.ifTrue:
                cond_info['if_true'] = self.parse_statement(stmt.ifTrue)
                
            if stmt.ifFalse:
                cond_info['if_false'] = self.parse_statement(stmt.ifFalse)
                
            statements.append(cond_info)
            
        elif kind == ps.StatementKind.Case:
            # Case语句
            case_info = {
                'type': 'case',
                'expression': self.parse_expression(stmt.expr),
                'cases': []
            }
            
            for case in stmt.cases:
                case_item = {
                    'values': [self.parse_expression(e) for e in case.exprs],
                    'statement': self.parse_statement(case.stmt)
                }
                case_info['cases'].append(case_item)
                
            statements.append(case_info)
            
        elif kind in [ps.StatementKind.WhileLoop, ps.StatementKind.ForLoop]:
            # 循环语句
            loop_info = {
                'type': 'loop',
                'kind': str(kind),
                'condition': None,
                'body': []
            }
            
            if hasattr(stmt, 'cond') and stmt.cond:
                loop_info['condition'] = self.parse_expression(stmt.cond)
                
            if hasattr(stmt, 'body') and stmt.body:
                loop_info['body'] = self.parse_statement(stmt.body)
                
            statements.append(loop_info)
            
        elif kind == ps.StatementKind.List:
            # 语句列表
            for s in stmt.body:
                statements.extend(self.parse_statement(s))
                
        return statements
    
    def parse_expression(self, expr):
        """递归解析表达式，提取左值和右值"""
        if expr is None:
            return "null"
            
        kind = expr.kind
        
        if kind == ps.ExpressionKind.NamedValue:
            # 变量名
            name = expr.symbol.name if hasattr(expr, 'symbol') and expr.symbol else "unknown"
            print(f"        变量引用: {name}")
            return name
            
        elif kind == ps.ExpressionKind.IntegerLiteral:
            # 整数字面量
            value = str(expr.value) if hasattr(expr, 'value') else "unknown"
            print(f"        整数: {value}")
            return value
            
        elif kind == ps.ExpressionKind.StringLiteral:
            # 字符串字面量
            value = str(expr.value) if hasattr(expr, 'value') else "unknown"
            print(f"        字符串: {value}")
            return f'"{value}"'
            
        elif kind == ps.ExpressionKind.BinaryOp:
            # 二元操作
            left = self.parse_expression(expr.left)
            right = self.parse_expression(expr.right)
            op = str(expr.op) if hasattr(expr, 'op') else "?"
            result = f"({left} {op} {right})"
            print(f"        二元操作: {result}")
            return result
            
        elif kind == ps.ExpressionKind.UnaryOp:
            # 一元操作
            operand = self.parse_expression(expr.operand)
            op = str(expr.op) if hasattr(expr, 'op') else "?"
            result = f"({op}{operand})"
            print(f"        一元操作: {result}")
            return result
            
        elif kind == ps.ExpressionKind.Assignment:
            # 赋值表达式
            left = self.parse_expression(expr.left)   # 左值
            right = self.parse_expression(expr.right) # 右值
            op = "=" if not hasattr(expr, 'op') else str(expr.op)
            result = f"{left} {op} {right}"
            print(f"        赋值: {result}")
            print(f"          左值: {left}")
            print(f"          右值: {right}")
            return result
            
        elif kind == ps.ExpressionKind.ConditionalOp:
            # 三元操作符 (condition ? true_expr : false_expr)
            cond = self.parse_expression(expr.predicate)
            true_expr = self.parse_expression(expr.left)
            false_expr = self.parse_expression(expr.right)
            result = f"({cond} ? {true_expr} : {false_expr})"
            print(f"        三元操作: {result}")
            return result
            
        elif kind == ps.ExpressionKind.Concatenation:
            # 拼接操作 {a, b, c}
            operands = [self.parse_expression(op) for op in expr.operands]
            result = "{" + ", ".join(operands) + "}"
            print(f"        拼接: {result}")
            return result
            
        elif kind == ps.ExpressionKind.ElementSelect:
            # 数组/向量索引 a[index]
            base = self.parse_expression(expr.value)
            index = self.parse_expression(expr.selector)
            result = f"{base}[{index}]"
            print(f"        索引: {result}")
            return result
            
        elif kind == ps.ExpressionKind.RangeSelect:
            # 范围选择 a[msb:lsb]
            base = self.parse_expression(expr.value)
            left = self.parse_expression(expr.left)
            right = self.parse_expression(expr.right)
            result = f"{base}[{left}:{right}]"
            print(f"        范围选择: {result}")
            return result
            
        elif kind == ps.ExpressionKind.MemberAccess:
            # 成员访问 struct.member
            base = self.parse_expression(expr.value)
            member = expr.member.name if hasattr(expr, 'member') else "unknown"
            result = f"{base}.{member}"
            print(f"        成员访问: {result}")
            return result
            
        elif kind == ps.ExpressionKind.Call:
            # 函数调用
            func_name = expr.subroutine.name if hasattr(expr, 'subroutine') else "unknown"
            args = [self.parse_expression(arg) for arg in expr.arguments] if hasattr(expr, 'arguments') else []
            result = f"{func_name}({', '.join(args)})"
            print(f"        函数调用: {result}")
            return result
            
        else:
            # 其他表达式类型
            result = f"<{kind}>"
            print(f"        未知表达式: {result}")
            return result
    
    def print_module_summary(self, module_info):
        """打印模块摘要"""
        print(f"\n--- 模块 {module_info['name']} 摘要 ---")
        print(f"端口数量: {len(module_info['ports'])}")
        print(f"参数数量: {len(module_info['parameters'])}")
        print(f"变量数量: {len(module_info['variables'])}")
        print(f"线网数量: {len(module_info['nets'])}")
        print(f"实例数量: {len(module_info['instances'])}")
        print(f"过程块数量: {len(module_info['procedural_blocks'])}")
        print(f"连续赋值数量: {len(module_info['continuous_assigns'])}")
    
    def print_detailed_analysis(self):
        """打印详细分析结果"""
        print(f"\n{'='*50}")
        print(f"详细分析结果")
        print(f"{'='*50}")
        
        print(f"\n总共解析了 {len(self.modules)} 个模块:")
        for name, info in self.modules.items():
            print(f"- {name}")
            
        # 分析所有赋值语句中的左值和右值
        print(f"\n连续赋值语句分析:")
        for module_name, module_info in self.modules.items():
            if module_info['continuous_assigns']:
                print(f"\n模块 {module_name}:")
                for i, assign in enumerate(module_info['continuous_assigns']):
                    print(f"  赋值 {i+1}: {assign['left']} = {assign['right']}")
                    
        # 分析过程块中的赋值
        print(f"\n过程块赋值语句分析:")
        for module_name, module_info in self.modules.items():
            if module_info['procedural_blocks']:
                print(f"\n模块 {module_name}:")
                for i, block in enumerate(module_info['procedural_blocks']):
                    print(f"  过程块 {i+1} ({block['kind']}):")
                    self.analyze_statements_for_assignments(block['statements'], indent="    ")
    
    def analyze_statements_for_assignments(self, statements, indent=""):
        """分析语句中的赋值操作"""
        for stmt in statements:
            if isinstance(stmt, dict):
                if stmt.get('type') == 'expression':
                    expr = stmt['expression']
                    if '=' in str(expr):
                        print(f"{indent}赋值: {expr}")
                elif stmt.get('type') == 'conditional':
                    print(f"{indent}条件分支:")
                    print(f"{indent}  条件: {stmt['condition']}")
                    if stmt['if_true']:
                        print(f"{indent}  真分支:")
                        self.analyze_statements_for_assignments(stmt['if_true'], indent + "    ")
                    if stmt['if_false']:
                        print(f"{indent}  假分支:")
                        self.analyze_statements_for_assignments(stmt['if_false'], indent + "    ")

def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python3 pyslang_detailed_parser.py <verilog_file>")
        sys.exit(1)
        
    verilog_file = sys.argv[1]
    if not os.path.exists(verilog_file):
        print(f"文件不存在: {verilog_file}")
        sys.exit(1)
        
    parser = DetailedSystemVerilogParser()
    
    if parser.parse_file(verilog_file):
        parser.print_detailed_analysis()
    else:
        print("解析失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()