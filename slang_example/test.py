import pyslang

tree = pyslang.SyntaxTree.fromFile('slang_test.sv')
count=0
for mod in tree.root.members:
    print(f"ele: {count}" )
    print(mod.header.name.value)
    print("--------------------")
    for mem in mod.members:
        #mem.visit()
        print(f"type: {type(mem)}")
        if isinstance(mem, pyslang.PortDeclarationSyntax):
            print(f"{mem.declarators}")
            print(f"port_decl_header: {mem.header}")
            first_token = mem.header.getFirstToken()
            print(f"raw_text: {first_token.rawText}")
            print(f"trivia: {first_token.trivia}")
            print(f"value: {first_token.value}")
            print(f"valueText: {first_token.valueText}")
            last_token = mem.header.getLastToken()
            print("=====================================")
        print(f"{mem.kind}")
    #print(mod.members[1].header.dataType)
    count = count + 1
    print("-------------")
mod = tree.root.members[0]
#print(mod.header.name.value)
#print(mod.members[0].kind)
#print(mod.members[1].header.dataType)