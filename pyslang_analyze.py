import re

class_lines = """[文件内容已提供]"""
with open('class_sum_pyslanglib', 'r', encoding='utf-8') as f:
    class_lines = f.read()
# -*- coding: utf-8 -*-

# 提取类定义的正则表达式
class_pattern = re.compile(r'class (\w+)(?:\(([^)]+)\))?:')

class_hierarchy = {}
all_classes = set()

for line in class_lines.split('\n'):
    if line.strip() and line.startswith('class '):
        match = class_pattern.match(line)
        if match:
            class_name = match.group(1)
            parents = match.group(2)
            all_classes.add(class_name)

            if parents:
                parent_list = [p.strip() for p in parents.split(',')]
                class_hierarchy[class_name] = parent_list
            else:
                class_hierarchy[class_name] = []

###################
# 找出根类（没有父类或父类不在已知类中的类）
root_classes = []
for cls in class_hierarchy:
    parents = class_hierarchy[cls]
    if not parents or all(p not in all_classes for p in parents):
        root_classes.append(cls)

# 构建子类关系
child_map = {cls: [] for cls in all_classes}
for cls, parents in class_hierarchy.items():
    for parent in parents:
        if parent in all_classes:
            child_map[parent].append(cls)

# 生成层次结构报告
report = []
report.append("=== 类继承关系分析 ===")
report.append(f"\n总类数: {len(all_classes)}")
report.append(f"\n根类 ({len(root_classes)}个):")
report.extend(f"- {cls}" for cls in sorted(root_classes))

report.append("\n\n=== 详细继承关系 ===")
for cls in sorted(all_classes):
    parents = class_hierarchy[cls]
    children = child_map[cls]

    report.append(f"\n类: {cls}")
    if parents:
        report.append(f"  继承自: {', '.join(parents)}")
    if children:
        report.append(f"  子类: {', '.join(children)}")
    else:
        report.append("  没有子类")

report = "\n".join(report)
print(report)

