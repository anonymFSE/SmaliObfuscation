#!/usr/bin/env python3
import os
import re
import argparse
from pathlib import Path
DECODER_SMALI = """\
.class public Lcom/str/Dec;
.super Ljava/lang/Object;
.method public static constructor <clinit>()V
    .locals 0
    return-void
.end method
# Convert the hexadecimal string into the original characters.
# Example: "00680069" → "hi"
.method public static d(Ljava/lang/String;)Ljava/lang/String;
    .locals 8
    # Compute the length of the input string
    invoke-virtual {p0}, Ljava/lang/String;->length()I
    move-result v0
    # Each character is represented by 4 hexadecimal digits
    const/4 v1, 0x4
    div-int v2, v0, v1
    # Create the array that will contain the rebuilt characters
    new-array v3, v2, [C
    # Start from the first position of the string
    const/4 v4, 0x0
    :loop_str
    if-ge v4, v2, :end_str
    # Compute the position of the four hexadecimal characters to read
    mul-int v5, v4, v1
    add-int/lit8 v6, v5, 0x4
    # Estrae un gruppo di 4 cifre hex
    invoke-virtual {p0, v5, v6}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v6
    # Convert the four hexadecimal digits to the corresponding numeric value
    const/16 v7, 0x10
    invoke-static {v6, v7}, Ljava/lang/Integer;->parseInt(Ljava/lang/String;I)I
    move-result v6
    # Convert the numeric value into the original character
    int-to-char v6, v6
    aput-char v6, v3, v4
    # Move to the next character
    add-int/lit8 v4, v4, 0x1
    goto :loop_str
    :end_str
    # Rebuild the complete string and return it
    new-instance v5, Ljava/lang/String;
    invoke-direct {v5, v3}, Ljava/lang/String;-><init>([C)V
    return-object v5
.end method
"""
def encode_string(s: str) -> str:
    return ''.join(f'{ord(c):04x}' for c in s)
def unescape_smali_string(raw: str) -> str:
    try:
        return raw.encode('raw_unicode_escape').decode('unicode_escape')
    except Exception:
        return raw
_SKIP_PATTERNS = [
    re.compile(r'^L[\w/$]+;$'),          
    re.compile(r'^\[+[BCDFIJSVZ]$'),     
    re.compile(r'^[BCDFIJSVZ]$'),        
    re.compile(r'^<\w+>$'),              
    re.compile(r'^(true|false|null)$'),  
]
def should_obfuscate(s: str) -> bool:
    if len(s) < 4:
        return False
    if not any(c.isprintable() for c in s):
        return False
    for pat in _SKIP_PATTERNS:
        if pat.match(s):
            return False
    return True
def inject_decoder_class(apk_root: Path) -> bool:
    smali_root = None
    for candidate in ("smali", "smali_classes2", "smali_classes3"):
        p = apk_root / candidate
        if p.exists():
            smali_root = p
            break
    if smali_root is None:
        return False
    target_dir = smali_root / "com" / "str"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "Dec.smali"
    if not target_file.exists():
        target_file.write_text(DECODER_SMALI, encoding="utf-8")
    return True
_CONST_STR_RE = re.compile(
    r'^(\s*const-string(?:/jumbo)?\s+(v\d+|p\d+),\s*)"((?:[^"\\]|\\.)*)"',
)
def process_smali_file(path: Path) -> int:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0
    lines = content.splitlines(keepends=True)
    new_lines = []
    count = 0
    for line in lines:
        m = _CONST_STR_RE.match(line)
        if m:
            prefix = m.group(1)
            reg = m.group(2)
            raw_string = m.group(3)
            decoded = unescape_smali_string(raw_string)
            reg_num = int(reg[1:]) if reg[1:].isdigit() else 999
            if should_obfuscate(decoded) and reg_num <= 15:
                encoded = encode_string(decoded)
                indent = re.match(r'^(\s*)', line).group(1)
                new_lines.append(f'{prefix}"{encoded}"\n')
                new_lines.append(
                    f'{indent}invoke-static {{{reg}}}, '
                    f'Lcom/str/Dec;->d(Ljava/lang/String;)Ljava/lang/String;\n'
                )
                new_lines.append(
                    f'{indent}move-result-object {reg}\n'
                )
                count += 1
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    if count > 0:
        path.write_text(''.join(new_lines), encoding="utf-8")
    return count
def main():
    parser = argparse.ArgumentParser(
        description="String obfuscation on .smali files"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Folder containing decompiled APKs"
    )
    args = parser.parse_args()
    base = Path(args.input).resolve()
    if not base.exists():
        print(f"[ERR] Folder not found: {base}")
        return
    total_apk = 0
    total_files = 0
    total_strings = 0
    skipped_files = 0
    errors = 0
    apk_dirs = sorted(
        d for d in base.iterdir()
        if d.is_dir()
    )
    for apk_dir in apk_dirs:
        has_smali = any(
            (apk_dir / s).exists()
            for s in (
                "smali",
                "smali_classes2",
                "smali_classes3"
            )
        )
        if not has_smali:
            continue
        total_apk += 1
        if not inject_decoder_class(apk_dir):
            print(
                f"[WARN] {apk_dir.name[:60]}: "
                "unable to insert Dec.smali"
            )
            continue
        apk_count = 0
        for smali_file in apk_dir.rglob("*.smali"):
            if (
                smali_file.name == "Dec.smali"
                and smali_file.parent.name == "str"
            ):
                continue
            total_files += 1
            try:
                n = process_smali_file(smali_file)
                if n > 0:
                    apk_count += n
                else:
                    skipped_files += 1
            except Exception as e:
                errors += 1
                print(f"[ERR] {smali_file}: {e}")
        total_strings += apk_count
        print(
            f"[OK] {apk_dir.name[:60]} "
            f"({apk_count} obfuscated strings)"
        )
    print("\n[DONE]")
    print(f"  Processed APKs        : {total_apk}")
    print(f"  Processed .smali files : {total_files}")
    print(f"  Obfuscated strings    : {total_strings}")
    print(f"  Files without strings   : {skipped_files}")
    print(f"  Errors                : {errors}")
if __name__ == "__main__":
    main()