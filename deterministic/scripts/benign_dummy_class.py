import os
import re
import csv
import shutil
import argparse
from pathlib import Path
STUB_CLASS = """.class public Lcom/injected/StubClass;
.super Ljava/lang/Object;
.source "StubClass.java"
# Dummy class added for obfuscation — it is never called
# Class constructor.
.method public constructor <init>()V
    .registers 1
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method
# Static method that is never called.
# Contains harmless instructions to make the class resemble a normal application class.
.method public static doNothing()V
    .registers 2
    const-string v0, "stub"
    const-string v1, "This method is never called"
    return-void
.end method
"""
STUB_PACKAGE = os.path.join("smali", "com", "injected")
STUB_FILENAME = "StubClass.smali"
def fix_apktool_yml(yml_path):
    with open(yml_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    fixed = re.sub(r": '(\d+)'", r": \1", content)
    if fixed != content:
        with open(yml_path, "w", encoding="utf-8") as f:
            f.write(fixed)
        return True
    return False
def conta_smali(apk_dir):
    return sum(1 for _ in Path(apk_dir).rglob("*.smali"))
def main():
    parser = argparse.ArgumentParser(
        description="Inject StubClass.smali into each decompiled APK"
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
        "--csv",
        default="report_injection.csv",
        help="Report CSV filename"
    )
    args = parser.parse_args()
    input_dir  = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    apk_dirs = sorted([
        d for d in input_dir.iterdir()
        if d.is_dir()
        and (d / "AndroidManifest.xml").exists()
        and (d / "apktool.yml").exists()
        and (d / "smali").exists()
    ])
    if not apk_dirs:
        print(f"[ERR] No APK decompileto valid found in: {input_dir}")
        return
    print(f"\n[INFO] Valid APKs found: {len(apk_dirs)}")
    print(f"[INFO] Output:             {output_dir}\n")
    results = []
    ok = 0       
    skip = 0     
    err = 0      
    for i, apk_dir in enumerate(apk_dirs, 1):
        name     = apk_dir.name
        out_path = output_dir / name
        print(
            f"[{i}/{len(apk_dirs)}] {name[:55]} ...",
            end=" ",
            flush=True
        )
        stub_dest = out_path / STUB_PACKAGE / STUB_FILENAME
        if stub_dest.exists():
            print("SKIP (already injected)")
            results.append({
                "name":        name,
                "status":       "SKIPPED",
                "smali_before": "",
                "smali_after":  "",
                "stub_path":   str(stub_dest),
                "note":        "Already present"
            })
            skip += 1
            continue
        try:
            if out_path.exists():
                shutil.rmtree(out_path)
            shutil.copytree(str(apk_dir), str(out_path))
            yml_path = out_path / "apktool.yml"
            fix_apktool_yml(str(yml_path))
            smali_before = conta_smali(out_path)
            stub_dir = out_path / STUB_PACKAGE
            stub_dir.mkdir(parents=True, exist_ok=True)
            stub_file = stub_dir / STUB_FILENAME
            with open(stub_file, "w", encoding="utf-8") as f:
                f.write(STUB_CLASS)
            smali_after = conta_smali(out_path)
            print(f"OK  ({smali_before} -> {smali_after} smali)")
            results.append({
                "name":        name,
                "status":       "OK",
                "smali_before": smali_before,
                "smali_after":  smali_after,
                "stub_path":   str(stub_file),
                "note":        ""
            })
            ok += 1
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "name":        name,
                "status":       "ERROR",
                "smali_before": "",
                "smali_after":  "",
                "stub_path":   "",
                "note":        str(e)[:200]
            })
            err += 1
    csv_path = output_dir / args.csv
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "name",
                "status",
                "smali_before",
                "smali_after",
                "stub_path",
                "note"
            ]
        )
        writer.writeheader()
        writer.writerows(results)
    print(f"\n{'='*55}")
    print(f"[DONE]  OK: {ok}  |  Skipped: {skip}  |  Errors: {err}")
    print(f"CSV:    {csv_path}")
    print(f"{'='*55}")
if __name__ == "__main__":
    main()