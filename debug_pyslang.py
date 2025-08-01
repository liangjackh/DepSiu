#!/usr/bin/env python3
"""
调试pyslang符号访问 - 找出为什么找不到always块
"""

import pyslang as ps
import sys

def debug_pyslang_structure(verilog_file):
    """调试pyslang的结构访问"""
    print(f"=== 调试 {verilog_file} ===")
    
    try:
        # 创建Driver
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
        success = driver.reportCompilation(compilation, False)
        
        if not success:
            print("编译失败")
            return
            
        print("编译成功!")
        
        # 1. 检查语法树
        print("\n=== 语法树分析 ===")
        trees = driver.syntaxTrees
        print(f"语法树数量: {len(trees)}")
        
        for i, tree in enumerate(trees):
            print(f"\n语法树 {i}:")
            print(f"  文件名: {getattr(tree, 'fileName', 'unknown')}")
            print(f"  根节点: {tree.root}")
            print(f"  根节点类型: {type(tree.root)}")
            if hasattr(tree.root, 'kind'):
                print(f"  根节点kind: {tree.root.kind}")
            
            # 遍历语法树寻找always块
            print("  搜索always块...")
            count = find_always_in_syntax_tree(tree.root, 0)
            print(f"  找到 {count} 个always块")
        
        # 2. 检查符号表
        print("\n=== 符号表分析 ===")
        root = compilation.getRoot()
        definitions = compilation.getDefinitions()
        
        print(f"根符号: {root}")
        print(f"定义数量: {len(definitions)}")
        
        for definition in definitions:
            print(f"\n定义: {definition.name} (kind: {definition.kind})")
            debug_symbol_hierarchy(definition, 0)
            
        print(f"\n顶层实例数量: {len(root.topInstances)}")
        for instance in root.topInstances:
            print(f"\n实例: {instance.name}")
            debug_symbol_hierarchy(instance, 0)
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

def find_always_in_syntax_tree(node, depth):
    """在语法树中搜索always块"""
    count = 0
    indent = "  " * depth
    
    if node is None:
        return count
        
    # 检查节点类型
    if hasattr(node, 'kind'):
        if node.kind in [ps.SyntaxKind.AlwaysBlock, ps.SyntaxKind.AlwaysCombBlock, 
                         ps.SyntaxKind.AlwaysFFBlock, ps.SyntaxKind.AlwaysLatchBlock]:
            print(f"{indent}找到: {node.kind}")
            count += 1
            
            # 分析always块的内容
            if hasattr(node, 'statement') and node.statement:
                print(f"{indent}  语句: {node.statement.kind}")
                analyze_statement_syntax(node.statement, depth + 1)
    
    # 递归遍历子节点
    try:
        for i in range(len(node)):
            child = node[i]
            count += find_always_in_syntax_tree(child, depth + 1)
    except (TypeError, AttributeError):
        pass
        
    return count

def analyze_statement_syntax(stmt, depth):
    """分析语句语法"""
    indent = "  " * depth
    
    if stmt is None:
        return
        
    try:
        print(f"{indent}语句: {stmt.kind}")
        
        if stmt.kind == ps.SyntaxKind.ExpressionStatement:
            if hasattr(stmt, 'expression'):
                analyze_expression_syntax(stmt.expression, depth + 1)
        elif stmt.kind == ps.SyntaxKind.SequentialBlockStatement:
            if hasattr(stmt, 'body') and hasattr(stmt.body, 'statements'):
                for sub_stmt in stmt.body.statements:
                    analyze_statement_syntax(sub_stmt, depth + 1)
        elif stmt.kind == ps.SyntaxKind.ConditionalStatement:
            print(f"{indent}  条件语句")
            if hasattr(stmt, 'statement'):
                analyze_statement_syntax(stmt.statement, depth + 1)
            if hasattr(stmt, 'elseClause') and stmt.elseClause:
                if hasattr(stmt.elseClause, 'clause'):
                    analyze_statement_syntax(stmt.elseClause.clause, depth + 1)
                    
    except Exception as e:
        print(f"{indent}语句分析错误: {e}")

def analyze_expression_syntax(expr, depth):
    """分析表达式语法"""
    indent = "  " * depth
    
    if expr is None:
        return
        
    try:
        if hasattr(expr, 'kind'):
            if expr.kind == ps.SyntaxKind.AssignmentExpression:
                print(f"{indent}阻塞赋值")
            elif expr.kind == ps.SyntaxKind.NonblockingAssignmentExpression:
                print(f"{indent}非阻塞赋值")
            else:
                print(f"{indent}表达式: {expr.kind}")
                
    except Exception as e:
        print(f"{indent}表达式分析错误: {e}")

def debug_symbol_hierarchy(symbol, depth):
    """调试符号层级结构"""
    indent = "  " * depth
    
    if symbol is None:
        return
        
    try:
        print(f"{indent}符号: {getattr(symbol, 'name', 'unnamed')} (kind: {symbol.kind})")
        
        # 特别检查过程块
        if symbol.kind == ps.SymbolKind.ProceduralBlock:
            print(f"{indent}  -> 找到过程块!")
            if hasattr(symbol, 'syntax'):
                print(f"{indent}     语法类型: {symbol.syntax.kind}")
            
        # 递归访问成员
        if hasattr(symbol, 'members') and depth < 3:  # 限制深度避免无限递归
            members = list(symbol.members)
            if members:
                print(f"{indent}  成员数量: {len(members)}")
                for member in members[:5]:  # 只显示前5个成员
                    debug_symbol_hierarchy(member, depth + 1)
                if len(members) > 5:
                    print(f"{indent}  ... 还有 {len(members) - 5} 个成员")
                    
    except Exception as e:
        print(f"{indent}符号分析错误: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 debug_pyslang.py <verilog_file>")
        sys.exit(1)
        
    debug_pyslang_structure(sys.argv[1])