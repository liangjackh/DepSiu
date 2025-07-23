import pyslang

tree = pyslang.SyntaxTree.fromFile('slang_test.sv')
count=0
for mod in tree.root.members:
    print(f"ele: {count}" )
    print(mod.header.name.value)
    print("--------------------")
    for mem in mod.members:
        mem.visit()
        #print(f"{mem.kind}, {}")
        print(f"{mem.kind}")
    #print(mod.members[1].header.dataType)
    count = count + 1
    print("-------------")
mod = tree.root.members[0]
#print(mod.header.name.value)
#print(mod.members[0].kind)
#print(mod.members[1].header.dataType)