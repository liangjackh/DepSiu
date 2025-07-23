from pyslang import Visitor, SyntaxNode

# 定义自定义访问者
class MyVisitor(Visitor):
    def visitIntegerLiteral(self, node):
        print(f"Found integer: {node.value}")
        return super().visitIntegerLiteral(node)  # 继续遍历子节点

# 创建访问者实例
visitor = MyVisitor()

# 在节点上调用 visit()
#your_syntax_node.visit(visitor)  # your_syntax_node 是 SyntaxNode 实例
