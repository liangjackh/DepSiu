#!/usr/bin/env python3
"""
调试位置信息提取
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sv_parser import SystemVerilogParser


def debug_location_info():
    """调试位置信息"""
    
    simple_code = """module test(input a, input b);
    assert (a || b);
    assume (a != b);
endmodule"""
    
    parser = SystemVerilogParser() 
    modules = parser.parse_text(simple_code)
    
    if modules and hasattr(modules[0], 'assertions') and modules[0].assertions:
        assertion = modules[0].assertions[0]
        print(f"断言信息: {assertion}")
        
        # 尝试手动计算行号
        if '偏移' in assertion['location']:
            offset_str = assertion['location'].replace('偏移 ', '')
            try:
                offset = int(offset_str)
                # 手动计算行号
                lines = simple_code[:offset].count('\n')
                print(f"偏移 {offset} 对应第 {lines + 1} 行")
                
                # 计算列号
                last_newline = simple_code.rfind('\n', 0, offset)
                if last_newline == -1:
                    column = offset + 1
                else:
                    column = offset - last_newline
                print(f"列号: {column}")
                
            except:
                pass


if __name__ == "__main__":
    debug_location_info()