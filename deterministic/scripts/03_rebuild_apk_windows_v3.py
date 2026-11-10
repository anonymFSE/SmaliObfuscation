#!/usr/bin/env python3
import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
MARKER = "opaque_predicate_injected"
MAX_8BIT_REGISTER = 255
@dataclass
class MethodStats:
    injected: int = 0
    already_injected: int = 0        
    skipped_no_registers: int = 0
    skipped_not_enough_locals: int = 0        
    skipped_bad_registers: int = 0
    skipped_param_alias: int = 0
    skipped_too_many_registers: int = 0        
    skipped_malformed_signature: int = 0
    skipped_no_body: int = 0def is_method_start(line):
    s = line.strip()
    return (
        s.startswith(".method")
        and " abstract " not in f" {s} "
        and " native " not in f" {s} "
    )
def is_method_end(line):
    return line.strip().startswith(".end method")
def count_parameter_registers(method_line):
    match = re.search(r"\((.*?)\)", method_line)
    if not match:
        return None
    params = match.group(1)
    count = 0
    i = 0
    while i < len(params):
        ch = params[i]
        if ch == "[":
            while i < len(params) and params[i] == "[":
                i += 1
            if i >= len(params):
                return None
            if params[i] == "L":
                end = params.find(";", i)
                if end == -1:
                    return None
                i = end + 1
            else:
                i += 1
            count += 1
            continue
        if ch == "L":
            end = params.find(";", i)
            if end == -1:
                return None
            i = end + 1
            count += 1
            continue
        if ch in ("J", "D"):
            i += 1
            count += 2
            continue
        if ch in ("B", "C", "F", "I", "S", "Z"):
            i += 1
            count += 1
            continue
        return None
    is_static = re.search(
        r"(^|\s)static(\s|$)",
        method_line.strip()
    ) is not None
    if not is_static:
        count += 1
    return count
def find_register_directive(method_lines):
    for idx, line in enumerate(method_lines):
        match = re.match(
            r"^(\s*)\.(locals|registers)\s+(\d+)(.*)$",
            line
        )
        if match:
            return (
                idx,              
                match.group(1),   
                match.group(2),   
                int(match.group(3)),  
                match.group(4)    
            )
    return None
def find_insertion_index(method_lines, register_idx):
    idx = register_idx + 1
    in_annotation = False
    while idx < len(method_lines):
        stripped = method_lines[idx].strip()
        if not stripped or stripped.startswith("#"):
            idx += 1
            continue
        if stripped.startswith(".annotation"):
            in_annotation = True
            idx += 1
            continue
        if in_annotation:
            idx += 1
            if stripped.startswith(".end annotation"):
                in_annotation = False
            continue
        if stripped.startswith(".param"):
            idx += 1
            continue
        if stripped.startswith((
            ".end param",
            ".prologue",
            ".line",
            ".local",
            ".restart local",
            ".end local"
        )):
            idx += 1
            continue
        break
    return idx
def uses_numeric_parameter_alias(
    method_lines,
    body_start,
    first_param_register,
    param_registers
):
    if param_registers <= 0:
        return False
    last_param_register = (
        first_param_register + param_registers - 1
    )
    body = "".join(method_lines[body_start:])
    for match in re.finditer(r"\bv(\d+)\b", body):
        reg = int(match.group(1))
        if first_param_register <= reg <= last_param_register:
            return True
    return False
def const_instruction(reg, value):
    if -8 <= value <= 7 and reg <= 15:
        return f"    const/4 v{reg}, {value:#x}\n"
    return f"    const/16 v{reg}, {value:#x}\n"
def build_runtime_predicate(reg_base, label_id):
    reg_x = reg_base
    reg_tmp = reg_base + 1
    reg_div = reg_base + 2
    return [
        f"    # {MARKER}\n",
        "    invoke-static {}, Ljava/lang/Thread;->activeCount()I\n",
        f"    move-result v{reg_x}\n",
        f"    mul-int v{reg_tmp}, v{reg_x}, v{reg_x}\n",
        f"    add-int v{reg_tmp}, v{reg_tmp}, v{reg_x}\n",
        const_instruction(reg_div, 2),
        f"    rem-int v{reg_tmp}, v{reg_tmp}, v{reg_div}\n",
        f"    if-eqz v{reg_tmp}, :opq_keep_{label_id}\n",
        f"    goto :opq_dead_{label_id}\n",
        f"    :opq_dead_{label_id}\n",
        const_instruction(reg_x, 0),
        f"    add-int v{reg_x}, v{reg_x}, v{reg_tmp}\n",
        f"    goto :opq_end_{label_id}\n",
        f"    :opq_keep_{label_id}\n",
        "    nop\n",
        f"    :opq_end_{label_id}\n",
    ]
def build_constant_predicate(reg_base, label_id):
    reg_x = reg_base
    reg_tmp = reg_base + 1
    reg_div = reg_base + 2
    return [
        f"    # {MARKER}\n",
        const_instruction(reg_x, 7),
        f"    mul-int v{reg_tmp}, v{reg_x}, v{reg_x}\n",
        f"    add-int v{reg_tmp}, v{reg_tmp}, v{reg_x}\n",
        const_instruction(reg_div, 2),
        f"    rem-int v{reg_tmp}, v{reg_tmp}, v{reg_div}\n",
        f"    if-eqz v{reg_tmp}, :opq_keep_{label_id}\n",
        f"    goto :opq_dead_{label_id}\n",
        f"    :opq_dead_{label_id}\n",
        const_instruction(reg_x, 0),
        f"    add-int v{reg_x}, v{reg_x}, v{reg_tmp}\n",
        f"    goto :opq_end_{label_id}\n",
        f"    :opq_keep_{label_id}\n",
        "    nop\n",
        f"    :opq_end_{label_id}\n",
    ]
def process_method(
    method_lines,
    method_id,
    predicate_mode,
    stats
):
    if any(MARKER in line for line in method_lines):
        stats.already_injected += 1
        return method_lines
    param_registers = count_parameter_registers(
        method_lines[0]
    )
    if param_registers is None:
        stats.skipped_malformed_signature += 1
        return method_lines
    directive = find_register_directive(method_lines)
    if directive is None:
        stats.skipped_no_registers += 1
        return method_lines
    reg_idx, indent, directive_type, old_count, suffix = directive
    if directive_type == "locals":
        old_locals = old_count
    else:
        if old_count < param_registers:
            stats.skipped_bad_registers += 1
            return method_lines
        old_locals = old_count - param_registers
    if old_locals < 3:
        stats.skipped_not_enough_locals += 1
        return method_lines
    first_param_register = old_locals
    body_start = reg_idx + 1
    if uses_numeric_parameter_alias(
        method_lines,
        body_start,
        first_param_register,
        param_registers
    ):
        stats.skipped_param_alias += 1
        return method_lines
    reg_base = 0
    highest_new_register = reg_base + 2
    if highest_new_register > MAX_8BIT_REGISTER:
        stats.skipped_too_many_registers += 1
        return method_lines
    label_id = f"{method_id}_{reg_base}"
    if predicate_mode == "runtime":
        block = build_runtime_predicate(
            reg_base,
            label_id
        )
    else:
        block = build_constant_predicate(
            reg_base,
            label_id
        )
    insertion_idx = find_insertion_index(
        method_lines,
        reg_idx
    )
    if (
        insertion_idx >= len(method_lines) - 1
        or is_method_end(method_lines[insertion_idx])
    ):
        stats.skipped_no_body += 1
        return method_lines
    updated = list(method_lines)
    updated[insertion_idx:insertion_idx] = block
    stats.injected += 1
    return updated
def process_file(path, predicate_mode, dry_run=False):
    with open(path, "r", errors="ignore") as f:
        lines = f.readlines()
    stats = MethodStats()
    new_lines = []
    i = 0
    method_id = 0
    while i < len(lines):
        line = lines[i]
        if is_method_start(line):
            method_id += 1
            method_lines = [line]
            i += 1
            while (
                i < len(lines)
                and not is_method_end(lines[i])
            ):
                method_lines.append(lines[i])
                i += 1
            if i < len(lines):
                method_lines.append(lines[i])
                i += 1
            new_lines.extend(
                process_method(
                    method_lines,
                    method_id,
                    predicate_mode,
                    stats
                )
            )
        else:
            new_lines.append(line)
            i += 1
    if stats.injected > 0 and not dry_run:
        with open(path, "w") as f:
            f.writelines(new_lines)
    return stats
def merge_stats(total, current):
    for field in total.__dataclass_fields__:
        setattr(
            total,
            field,
            getattr(total, field)
            + getattr(current, field)
        )
def main():
    parser = argparse.ArgumentParser(
        description="Opaque predicate injection on .smali files"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Folder containing decompiled Smali files"
    )
    parser.add_argument(
        "--mode",
        choices=("runtime", "constant"),
        default="runtime",
        help="Opaque predicate type to inject (default: runtime)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be modified without writing files"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print every modified Smali file"
    )
    args = parser.parse_args()
    base = Path(args.input).resolve()
    if not base.exists():
        print(f"[ERR] Folder not found: {base}")
        return
    total_files = 0
    changed_files = 0
    errors = 0
    total = MethodStats()
    for root, _, files in os.walk(base):
        for fname in files:
            if not fname.endswith(".smali"):
                continue
            total_files += 1
            path = os.path.join(root, fname)
            try:
                stats = process_file(
                    path,
                    args.mode,
                    args.dry_run
                )
                merge_stats(total, stats)
                if stats.injected > 0:
                    changed_files += 1
                    if not args.quiet:
                        action = (
                            "DRY"
                            if args.dry_run
                            else "OK"
                        )
                        print(
                            f"[{action}] {path} "
                            f"({stats.injected} methods)"
                        )
            except Exception as exc:
                errors += 1
                print(
                    f"[ERR] {path}: {exc}"
                )
    print("\n[DONE]")
    print(
        f"File .smali analyzed       : "
        f"{total_files}"
    )
    print(
        f"Modified files              : "
        f"{changed_files}"
    )
    print(
        f"Methods with opaque predicates  : "
        f"{total.injected}"
    )
    print(
        f"Already modified methods        : "
        f"{total.already_injected}"
    )
    print(
        f"Skipped: no registers       : "
        f"{total.skipped_no_registers}"
    )
    print(
        f"Skipped: too few local registers     : "
        f"{total.skipped_not_enough_locals}"
    )
    print(
        f"Skipped: parameter register aliases  : "
        f"{total.skipped_param_alias}"
    )
    print(
        f"Skipped: too many registers  : "
        f"{total.skipped_too_many_registers}"
    )
    print(
        f"Skipped: malformed signature : "
        f"{total.skipped_malformed_signature}"
    )
    print(
        f"Skipped: no valid body   : "
        f"{total.skipped_no_body}"
    )
    print(
        f"Skipped: invalid registers: "
        f"{total.skipped_bad_registers}"
    )
    print(
        f"Errors                       : "
        f"{errors}"
    )
if __name__ == "__main__":
    main()