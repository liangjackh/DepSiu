import pyslang

tree = pyslang.SyntaxTree.fromFile('slang_test.sv')
printer = pyslang.SyntaxPrinter()
print(f"[test] {printer.str()}")
print(f"[printer]{printer.printFile(tree)}")
count=0
print(f"root: {tree.root.kind}")
for mod in tree.root.members:
    print(f"ele: {count}" )
    print(f"header name value: {mod.header.name.value}")
    for mem in mod.members:
        #mem.visit()
        print(f"type: {type(mem)}")
        if isinstance(mem, pyslang.PortDeclarationSyntax):
            print(f"    declarators: {mem.declarators}")
            print(f"    port_decl_header: {mem.header}")
            #first_token = mem.header.getFirstToken()
            #print(f"raw_text: {first_token.rawText}")
            #print(f"trivia: {first_token.trivia}")
            #print(f"value: {first_token.value}")
            #print(f"valueText: {first_token.valueText}")
            #print(f"value: {first_token.value}")
            #last_token = mem.header.getLastToken()
            print("    =====================================")
        elif isinstance(mem, pyslang.DataDeclarationSyntax):
            print(f"    [data declar syntax]{mem.declarators}")
        elif isinstance(mem, pyslang.ProceduralBlockSyntax):
        #ProceduralBlockSyntax -> MemberSyntax -> SyntaxNode
        # keywork: Token,   statement: StatementSynatax    
            print(f"    {mem.kind}")
            print(f"    parent_kind:{mem.parent.kind}")
            print(f"    source_range_1: ({mem.sourceRange.start}, {mem.sourceRange.end})")
            print(f"    source_range_2: ({mem.sourceRange.start.offset}, {mem.sourceRange.end.offset})")
            print(f"    token: {str(mem.keyword)}")
            print(f"    [printer][token]{printer.print(mem.keyword)}")
            print(f"[printer]{printer.str()}")
            printer.print(mem.keyword)
            #print(f"    [printer]{printer.printFile(mem.parent)}")
            
        
        print(f"{mem.kind}")
    #print(mod.members[1].header.dataType)
    count = count + 1
    print("-------------")
mod = tree.root.members[0]
#print(mod.header.name.value)
#print(mod.members[0].kind)
#print(mod.members[1].header.dataType)