#!/usr/bin/env python3

import os
import subprocess
import argparse
import sys
from pathlib import Path


APKTOOL_JAR = r"C:\apktool\apktool_3.0.2.jar"


def run(cmd):
    try:
        r = subprocess.run(
            cmd, shell=False,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, timeout=300 
        )
        return r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)


def main():
    parser = argparse.ArgumentParser(description="Decompile APKs to Smali")
    parser.add_argument("--input",  required=True, help="Folder containing APK files (including subfolders)")
    parser.add_argument("--output", required=True, help="Smali output folder")
    args = parser.parse_args()


    if not os.path.exists(APKTOOL_JAR):
        print(f"[ERR] apktool.jar not found at {APKTOOL_JAR}")
        sys.exit(1)

    input_dir  = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)


    apks = sorted(input_dir.rglob("*.apk"))
    if not apks:
        print(f"[ERR] No APK files found in: {input_dir}")
        sys.exit(1)

    print(f"[INFO] APK files found: {len(apks)}")
    print(f"[INFO] Output:      {output_dir}\n")

    ok = err = skip = 0


    for i, apk in enumerate(apks):
        out_dir = output_dir / apk.stem 


        if out_dir.exists() and any(out_dir.iterdir()):
            print(f"[{i+1}/{len(apks)}] SKIP  {apk.name}")
            skip += 1
            continue

        out_dir.mkdir(exist_ok=True)
        print(f"[{i+1}/{len(apks)}] DECOMPILE: {apk.name[:60]} ...", end=" ", flush=True)

        
        rc, out = run(["java", "-jar", APKTOOL_JAR, "d", str(apk), "-o", str(out_dir), "-f"])  
        if rc != 0:
            
            rc, out = run(["java", "-jar", APKTOOL_JAR, "d", str(apk), "-o", str(out_dir), "-f", "--no-res"])


        if rc == 0:
            smali_ok = any(out_dir.glob("smali*"))
            if smali_ok:
                print("OK")
            else:
                print("OK (warning: no Smali folder)")
            ok += 1
        else:
            print("ERROR")
            print(f"       {out.strip()[-200:]}")
            err += 1

    print(f"\n{'='*50}")
    print(f"DONE  OK: {ok}  |  Skipped: {skip}  |  Errors: {err}")


if __name__ == "__main__":
    main()
