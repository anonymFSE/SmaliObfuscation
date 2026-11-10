#!/usr/bin/env python3
import os
import re
import shutil
import argparse
from pathlib import Path
TARGET_APIS = {
    "Landroid/telephony/TelephonyManager;": [
        "getDeviceId", "getSubscriberId", "getLine1Number",
        "getSimSerialNumber", "getNetworkOperator",
        "getNetworkCountryIso", "getCellLocation",
        "getAllCellInfo", "getImei", "getMeid",
    ],
    "Landroid/telephony/SmsManager;": [
        "sendTextMessage",
        "sendMultipartTextMessage",
        "sendDataMessage",
    ],
    "Landroid/content/ContentResolver;": [
        "query", "insert", "update", "delete",
    ],
    "Landroid/location/LocationManager;": [
        "getLastKnownLocation",
        "requestLocationUpdates",
        "getProviders",
    ],
    "Landroid/hardware/Camera;": [
        "open",
        "takePicture",
    ],
    "Landroid/mean/AudioRecord;": [
        "startRecording",
        "read",
    ],
    "Landroid/content/ClipboardManager;": [
        "getPrimaryClip",
        "setPrimaryClip",
        "getText",
    ],
    "Landroid/content/pm/PackageManager;": [
        "getInstalledPackages",
        "getInstalledApplications",
    ],
    "Ljava/lang/Runtime;": [
        "exec",
    ],
    "Landroid/net/ConnectivityManager;": [
        "getActiveNetworkInfo",
        "getNetworkInfo",
    ],
    "Landroid/net/wifi/WifiManager;": [
        "getConnectionInfo",
        "getScanResults",
        "startScan",
    ],
    "Landroid/accounts/AccountManager;": [
        "getAccounts",
        "getAccountsByType",
    ],
    "Landroid/app/admin/DevicePolicyManager;": [
        "lockNow",
        "wipeData",
        "resetPassword",
        "setPasswordQuality",
    ],
    "Landroid/accessibilityservice/AccessibilityService;": [
        "performGlobalAction",
    ],
    "Landroid/provider/Settings$Secure;": [
        "getString",
    ],
    "Landroid/provider/Settings$System;": [
        "getString",
        "putString",
    ],
}
INVOKE_PATTERN = re.compile(
    r'^\s*(invoke-virtual|invoke-static|invoke-interface)\s+\{([^}]*)\}\s*,\s*'
    r'(L[^;]+;)->([^(]+)\(([^)]*)\)(.+)$'
)
def class_name_from_descriptor(descriptor):
    return descriptor.lstrip('L').rstrip(';').replace('/', '.')
def count_param_words(param_str, is_static):
    count = 0 if is_static else 1
    i = 0
    while i < len(param_str):
        c = param_str[i]
        if c == 'L':
            end = param_str.index(';', i)
            count += 1
            i = end + 1
        elif c == '[':
            i += 1
        elif c in ('J', 'D'):
            count += 2
            i += 1
        else:
            count += 1
            i += 1
    return count
def parse_registers(reg_str):
    return [
        r.strip()
        for r in reg_str.split(',')
        if r.strip()
    ]
def find_free_registers(used_regs, n, locals_count):
    used_set = set(used_regs)
    free = []
    for i in range(locals_count):
        name = f"v{i}"
        if name not in used_set:
            free.append(name)
            if len(free) == n:
                return free
    return None
def get_locals_from_method(method_lines):
    for line in method_lines:
        m = re.match(r'\s*\.locals\s+(\d+)', line)
        if m:
            return int(m.group(1))
    return None
def build_reflection_block(
    invoke_type,
    regs,
    class_desc,
    method_name,
    params,
    ret_type,
    free_regs,
    move_result_line
):
    cls_reg  = free_regs[0]
    meth_reg = free_regs[1]
    args_reg = free_regs[2]
    tmp_reg  = free_regs[3]
    class_name = class_name_from_descriptor(class_desc)
    is_static = (invoke_type == "invoke-static")
    reg_list = parse_registers(regs)
    if is_static:
        param_regs = reg_list
        instance_reg = None
    else:
        instance_reg = reg_list[0] if reg_list else None
        param_regs = reg_list[1:]
    param_types = []
    i = 0
    while i < len(params):
        c = params[i]
        if c == 'L':
            end = params.index(';', i)
            param_types.append(params[i:end + 1])
            i = end + 1
        elif c == '[':
            j = i + 1
            while j < len(params) and params[j] == '[':
                j += 1
            if j < len(params) and params[j] == 'L':
                end = params.index(';', j)
                param_types.append(params[i:end + 1])
                i = end + 1
            else:
                param_types.append(params[i:j + 1])
                i = j + 1
        else:
            param_types.append(c)
            i += 1
    lines = []
    lines.append(
        f"    # [REFLECTION] {class_desc}->{method_name}({params}){ret_type}"
    )
    lines.append(
        f"    const-string {cls_reg}, \"{class_name}\""
    )
    lines.append(
        f"    invoke-static {{{cls_reg}}}, "
        f"Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;"
    )
    lines.append(
        f"    move-result-object {cls_reg}"
    )
    n_params = len(param_types)
    lines.append(
        f"    const/4 {tmp_reg}, 0x{n_params:x}"
    )
    lines.append(
        f"    new-array {args_reg}, {tmp_reg}, [Ljava/lang/Class;"
    )
    for idx, ptype in enumerate(param_types):
        lines.append(
            f"    const/4 {tmp_reg}, 0x{idx:x}"
        )
        if ptype in ('I', 'S', 'B', 'Z', 'C'):
            primitive_map = {
                'I': 'Ljava/lang/Integer;',
                'S': 'Ljava/lang/Short;',
                'B': 'Ljava/lang/Byte;',
                'Z': 'Ljava/lang/Boolean;',
                'C': 'Ljava/lang/Character;'
            }
            lines.append(
                f"    sget-object {meth_reg}, "
                f"{primitive_map.get(ptype, 'Ljava/lang/Object;')}->TYPE:Ljava/lang/Class;"
            )
        elif ptype in ('J', 'D'):
            pm = {
                'J': 'Ljava/lang/Long;',
                'D': 'Ljava/lang/Double;'
            }
            lines.append(
                f"    sget-object {meth_reg}, "
                f"{pm[ptype]}->TYPE:Ljava/lang/Class;"
            )
        elif ptype == 'F':
            lines.append(
                f"    sget-object {meth_reg}, "
                f"Ljava/lang/Float;->TYPE:Ljava/lang/Class;"
            )
        elif ptype == 'V':
            pass
        else:
            clean = ptype.lstrip('[')
            if clean.startswith('L'):
                cname = class_name_from_descriptor(clean)
            else:
                cname = clean
            lines.append(
                f"    const-string {meth_reg}, \"{cname}\""
            )
            lines.append(
                f"    invoke-static {{{meth_reg}}}, "
                f"Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;"
            )
            lines.append(
                f"    move-result-object {meth_reg}"
            )
        lines.append(
            f"    aput-object {meth_reg}, {args_reg}, {tmp_reg}"
        )
    lines.append(
        f"    const-string {meth_reg}, \"{method_name}\""
    )
    lines.append(
        f"    invoke-virtual {{{cls_reg}, {meth_reg}, {args_reg}}}, "
        f"Ljava/lang/Class;->getMethod("
        f"Ljava/lang/String;[Ljava/lang/Class;)"
        f"Ljava/lang/reflect/Method;"
    )
    lines.append(
        f"    move-result-object {meth_reg}"
    )
    n_args = len(param_regs)
    lines.append(
        f"    const/4 {tmp_reg}, 0x{n_args:x}"
    )
    lines.append(
        f"    new-array {args_reg}, {tmp_reg}, [Ljava/lang/Object;"
    )
    for idx, reg in enumerate(param_regs):
        lines.append(
            f"    const/4 {tmp_reg}, 0x{idx:x}"
        )
        lines.append(
            f"    aput-object {reg}, {args_reg}, {tmp_reg}"
        )
    if is_static or instance_reg is None:
        lines.append(
            f"    const/4 {tmp_reg}, 0x0"
        )
        lines.append(
            f"    invoke-virtual {{{meth_reg}, {tmp_reg}, {args_reg}}}, "
            f"Ljava/lang/reflect/Method;->invoke("
            f"Ljava/lang/Object;[Ljava/lang/Object;)"
            f"Ljava/lang/Object;"
        )
    else:
        lines.append(
            f"    invoke-virtual {{{meth_reg}, {instance_reg}, {args_reg}}}, "
            f"Ljava/lang/reflect/Method;->invoke("
            f"Ljava/lang/Object;[Ljava/lang/Object;)"
            f"Ljava/lang/Object;"
        )
    if move_result_line:
        stripped = move_result_line.strip()
        lines.append(
            f"    move-result-object {cls_reg}"
        )
        if ret_type.startswith('L') or ret_type.startswith('['):
            lines.append(
                f"    check-cast {cls_reg}, {ret_type}"
            )
        if 'move-result-object' in stripped:
            result_reg = stripped.split()[-1]
            if result_reg != cls_reg:
                lines.append(
                    f"    move-object {result_reg}, {cls_reg}"
                )
        elif 'move-result' in stripped:
            result_reg = stripped.split()[-1]
            lines.append(
                f"    # NOTE: primitive move-result remapped to "
                f"{result_reg} (potrebbe richiedere unboxing manuale)"
            )
            lines.append(
                f"    move-object {result_reg}, {cls_reg}"
            )
    lines.append(
        f"    # [/REFLECTION]"
    )
    return lines
def build_target_set():
    targets = set()
    for cls, methods in TARGET_APIS.items():
        for m in methods:
            targets.add((cls, m))
    return targets
def process_smali_file(path, targets, stats):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    lines = content.splitlines(keepends=True)
    output = []
    i = 0
    substitutions = 0
    locals_count = 4
    in_method = False
    while i < len(lines):
        line = lines[i]
        if re.match(r'\s*\.method\b', line):
            in_method = True
            output.append(line)
            i += 1
            continue
        if re.match(r'\s*\.end method\b', line):
            in_method = False
            output.append(line)
            i += 1
            continue
        if in_method:
            m_locals = re.match(
                r'\s*\.locals\s+(\d+)',
                line
            )
            if m_locals:
                locals_count = int(m_locals.group(1))
        m = INVOKE_PATTERN.match(line)
        if m and in_method:
            invoke_type = m.group(1)
            regs_str    = m.group(2)
            class_desc  = m.group(3)
            method_name = m.group(4)
            params      = m.group(5)
            ret_type    = m.group(6)
            if (class_desc, method_name) in targets:
                next_line = (
                    lines[i + 1]
                    if i + 1 < len(lines)
                    else None
                )
                has_move = (
                    next_line
                    and re.match(
                        r'\s*move-result',
                        next_line.strip()
                    )
                )
                used_regs = parse_registers(regs_str)
                free = find_free_registers(
                    used_regs,
                    4,
                    max(locals_count, 8)
                )
                if free is None:
                    output.append(
                        f"    # [REFLECTION-SKIP: no free regs] "
                        f"{line.rstrip()}\n"
                    )
                    output.append(line)
                    i += 1
                    continue
                max_reg_needed = (
                    max(
                        int(r[1:])
                        for r in free
                        if r.startswith('v')
                    ) + 1
                )
                if max_reg_needed > locals_count:
                    for out_idx in range(
                        len(output) - 1,
                        -1,
                        -1
                    ):
                        if re.match(
                            r'\s*\.locals\s+\d+',
                            output[out_idx]
                        ):
                            output[out_idx] = re.sub(
                                r'\.locals\s+\d+',
                                f'.locals {max_reg_needed}',
                                output[out_idx]
                            )
                            locals_count = max_reg_needed
                            break
                move_line = (
                    next_line
                    if has_move
                    else None
                )
                block = build_reflection_block(
                    invoke_type,
                    regs_str,
                    class_desc,
                    method_name,
                    params,
                    ret_type,
                    free,
                    move_line
                )
                for bl in block:
                    output.append(bl + '\n')
                substitutions += 1
                stats['total'] += 1
                i += 1
                if has_move:
                    i += 1
                continue
        output.append(line)
        i += 1
    if substitutions > 0:
        return ''.join(output), substitutions
    return None, 0
def main():
    parser = argparse.ArgumentParser(
        description="Reflection-based call obfuscation for Android APK Smali code"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Folder containing decompiled APKs"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output folder for modified APKs"
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="Modify APKs in place without creating a copy"
    )
    args = parser.parse_args()
    input_dir  = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    targets = build_target_set()
    apk_dirs = sorted([
        d
        for d in input_dir.iterdir()
        if d.is_dir()
    ])
    if not apk_dirs:
        print(
            f"[ERR] No folder found in {input_dir}"
        )
        return
    print(
        f"\nAPK from processare: {len(apk_dirs)}"
    )
    print(
        f"API target:        "
        f"{sum(len(v) for v in TARGET_APIS.values())} "
        f"methods in {len(TARGET_APIS)} classes\n"
    )
    stats = {'total': 0}
    ok = 0
    err = 0
    skipped = 0
    for idx, apk_dir in enumerate(apk_dirs, 1):
        name = apk_dir.name
        print(
            f"[{idx:03d}/{len(apk_dirs)}] "
            f"{name[:55]} ...",
            end=" ",
            flush=True
        )
        try:
            if args.inplace:
                dest_dir = apk_dir
            else:
                dest_dir = output_dir / name
                if dest_dir.exists():
                    print("SKIP (already present)")
                    skipped += 1
                    continue
                shutil.copytree(
                    str(apk_dir),
                    str(dest_dir)
                )
            smali_files = list(
                dest_dir.rglob("*.smali")
            )
            apk_subs = 0
            for smali_path in smali_files:
                try:
                    new_content, n = process_smali_file(
                        smali_path,
                        targets,
                        stats
                    )
                    if new_content:
                        with open(
                            smali_path,
                            'w',
                            encoding='utf-8'
                        ) as f:
                            f.write(new_content)
                        apk_subs += n
                except Exception:
                    pass
            print(
                f"OK [{apk_subs} sostituzioni]"
            )
            ok += 1
        except Exception as e:
            print(
                f"ERROR: {e}"
            )
            err += 1
    print(f"\n{'='*55}")
    print(
        f"[DONE] OK: {ok} | "
        f"Errors: {err} | "
        f"Skip: {skipped}"
    )
    print(
        f"       Sostituzioni reflection totali: "
        f"{stats['total']}"
    )
    print(f"{'='*55}")
if __name__ == "__main__":
    main()