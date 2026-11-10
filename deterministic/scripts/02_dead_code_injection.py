#!/usr/bin/env python3
import os
import re
import argparse
from pathlib import Path

def is_method_start(line):

    s = line.strip()
    
    return (
        s.startswith(".method")
        and "abstract" not in s
        and "native"   not in s
    )


def is_method_end(line):

    return line.strip().startswith(".end method")

def inject_block(reg_a, reg_b):
    
    tag = f"{reg_a}x{reg_b}"

    va, vb = f"v{reg_a}", f"v{reg_b}"
  
    
    def const_instr(reg_num, val):
        if reg_num <= 15:
            return f"    const/4 v{reg_num}, {val}\n"
        else:
            return f"    const/16 v{reg_num}, {val}\n"

    
    return [

        
        
        f"    invoke-static {{}}, Ljava/lang/System;->nanoTime()J\n",
        f"    move-result-wide {va}\n",

        
        
        f"    invoke-static {{}}, Ljava/lang/Math;->random()D\n",
        f"    move-result-wide {va}\n",

        
        const_instr(reg_a, "0x0"),
        const_instr(reg_b, "0x1"),

        
        
        f"    xor-int/2addr {va}, {vb}\n",

        
        
        f"    if-eqz {va}, :dead_{tag}\n",

        
        f"    goto :end_{tag}\n",

        
        f"    :dead_{tag}\n",

        
        const_instr(reg_a, "0x0"),

        
        f"    :end_{tag}\n",
    ]



def process_file(path):

    
    with open(path, "r", errors="ignore") as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    injected = 0

    
    while i < len(lines):
        line = lines[i]

        
        if is_method_start(line):
       
            method_lines = [line]
            i += 1

            while i < len(lines) and not is_method_end(lines[i]):
                method_lines.append(lines[i])
                i += 1

            
            if i < len(lines):
                method_lines.append(lines[i])

            i += 1
        
            reg_idx   = None
            reg_count = None
            mode      = None

            for k, ml in enumerate(method_lines):

                
                m = re.match(r'\s*\.locals\s+(\d+)', ml)
                if m:
                    reg_count = int(m.group(1))
                    reg_idx   = k
                    mode      = "locals"
                    break

                
                m = re.match(r'\s*\.registers\s+(\d+)', ml)
                if m:
                    reg_count = int(m.group(1))
                    reg_idx   = k
                    mode      = "registers"
                    break
       
            
            if reg_count is not None and reg_count >= 2:

                
                
                reg_a = min(reg_count - 2, 14)
                reg_b = min(reg_count - 1, 15)

                
                
                result = (
                    method_lines[:reg_idx + 1]
                    + inject_block(reg_a, reg_b)
                    + method_lines[reg_idx + 1:]
                )

                new_lines.extend(result)
                injected += 1

            else:
                
                
                new_lines.extend(method_lines)

        else:
            
            new_lines.append(line)
            i += 1

    
    if injected > 0:
        with open(path, "w") as f:
            f.writelines(new_lines)

    return injected


def main():

    
    parser = argparse.ArgumentParser(
        description="Dead code injection on .smali files"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Folder containing decompiled Smali files (from 01_decompile_apk.py)"
    )

    args = parser.parse_args()

    
    base = Path(args.input).resolve()

    
    if not base.exists():
        print(f"[ERR] Folder not found: {base}")
        return

    
    
    
    total_files    = 0   
    total_injected = 0   
    total_skipped  = 0   
    errors         = 0   


    
    for root, _, files in os.walk(base):

        for fname in files:

            
            if not fname.endswith(".smali"):
                continue

            path = os.path.join(root, fname)
            total_files += 1

            try:
                
                
                n = process_file(path)

                if n > 0:
                    total_injected += n
                    print(f"[OK]   {path}  ({n} methods)")
                else:
                    
                    total_skipped += 1

            except Exception as e:
                
                errors += 1
                print(f"[ERR]  {path}: {e}")

 
    print(f"\n[DONE] File .smali    : {total_files}")
    print(f"       Injected methods : {total_injected}")
    print(f"       Skipped files   : {total_skipped}  (methods with < 2 local registers)")
    print(f"       Errors         : {errors}")



if __name__ == "__main__":
    main()
