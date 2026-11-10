#!/usr/bin/env python3
import os                  
import time                
import hashlib             
import argparse            
import requests            
from pathlib import Path   
API_KEY = ""
BASE_URL = "https://www.virustotal.com/api/v3"
HEADERS = {"x-apikey": API_KEY}
WAIT_BETWEEN_REQUESTS = 16
HEADERS_XLSX = [
    "SHA256",
    "APK Name",
    "Malicious",
    "Suspicious",
    "Undetected",
    "Harmless",
    "Timeout",
    "Status"
]
def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
def upload_file(apk_path):
    url = f"{BASE_URL}/files"
    with open(apk_path, "rb") as f:
        files = {
            "file": (
                apk_path.name,
                f,
                "application/octet-stream"
            )
        }
        response = requests.post(
            url,
            headers=HEADERS,
            files=files
        )
    if response.status_code == 200:
        return response.json()["data"]["id"]
    else:
        return None, response.text
def get_analysis_result(analysis_id, max_wait=300):
    url = f"{BASE_URL}/analyses/{analysis_id}"
    elapsed = 0
    while elapsed < max_wait:
        response = requests.get(
            url,
            headers=HEADERS
        )
        if response.status_code != 200:
            return None
        data = response.json()["data"]
        status = data["attributes"]["status"]
        if status == "completed":
            stats = data["attributes"]["stats"]
            return {
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "undetected": stats.get("undetected", 0),
                "harmless": stats.get("harmless", 0),
                "timeout": stats.get("timeout", 0),
            }
        print(
            f"       analysis in progress ({status})..."
            f" waiting {WAIT_BETWEEN_REQUESTS}s"
        )
        time.sleep(WAIT_BETWEEN_REQUESTS)
        elapsed += WAIT_BETWEEN_REQUESTS
    return None
def get_file_report(sha256):
    url = f"{BASE_URL}/files/{sha256}"
    response = requests.get(
        url,
        headers=HEADERS
    )
    if response.status_code == 200:
        stats = response.json()["data"]["attributes"]["last_analysis_stats"]
        return {
            "malicious": stats.get("malicious", 0),
            "suspicious": stats.get("suspicious", 0),
            "undetected": stats.get("undetected", 0),
            "harmless": stats.get("harmless", 0),
            "timeout": stats.get("timeout", 0),
        }
    return None
def load_existing_results(output_path):
    existing = {}
    if not os.path.exists(output_path):
        return existing
    try:
        import openpyxl
        wb = openpyxl.load_workbook(output_path)
        ws = wb.active
        rows = list(
            ws.iter_rows(
                min_row=2,
                values_only=True
            )
        )
        for r in rows:
            if not r or not r[0]:
                continue
            sha256, name, malicious, suspicious, undetected, \
                harmless, timeout, status = (
                    list(r) + [None] * 8
                )[:8]
            existing[str(name)] = {
                "sha256": sha256,
                "name": name,
                "malicious": malicious,
                "suspicious": suspicious,
                "undetected": undetected,
                "harmless": harmless,
                "timeout": timeout,
                "status": status
            }
    except Exception as e:
        print(
            f"[WARN] Unable to read existing file "
            f"({e}), restarting from zero."
        )
    return existing
def write_excel(results_dict, output_path):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "VirusTotal Analysis"
    header_fill = PatternFill(
        start_color="1F3864",
        end_color="1F3864",
        fill_type="solid"
    )
    header_font = Font(
        color="FFFFFF",
        bold=True
    )
    for col, h in enumerate(HEADERS_XLSX, 1):
        cell = ws.cell(
            row=1,
            column=col,
            value=h
        )
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    for row, r in enumerate(results_dict.values(), 2):
        ws.cell(row=row, column=1, value=r["sha256"])
        ws.cell(row=row, column=2, value=r["name"])
        ws.cell(row=row, column=3, value=r.get("malicious", ""))
        ws.cell(row=row, column=4, value=r.get("suspicious", ""))
        ws.cell(row=row, column=5, value=r.get("undetected", ""))
        ws.cell(row=row, column=6, value=r.get("harmless", ""))
        ws.cell(row=row, column=7, value=r.get("timeout", ""))
        ws.cell(row=row, column=8, value=r.get("status", ""))
    ws.column_dimensions["A"].width = 70
    ws.column_dimensions["B"].width = 25
    for col in ["C", "D", "E", "F", "G", "H"]:
        ws.column_dimensions[col].width = 14
    wb.save(output_path)
def main():
    parser = argparse.ArgumentParser(
        description="Upload APKs to VirusTotal and download results (with resume)"
    )
    parser.add_argument(
        "--apk",
        required=True,
        help="Folder containing APKs"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output Excel file (.xlsx)"
    )
    args = parser.parse_args()
    apk_dir = Path(args.apk).resolve()
    apks = sorted([
        p for p in apk_dir.glob("*.apk")
        if p.is_file()
    ])
    if not apks:
        print(f"[ERR] No APK found in {apk_dir}")
        return
    results = load_existing_results(args.output)
    already_completed = set(results.keys())
    if already_completed:
        print(
            f"[RESUME] Found {len(already_completed)} APK already processed "
            f"in {args.output}, li salto."
        )
    da_fare = [
        p for p in apks
        if p.stem not in already_completed
    ]
    print(
        f"\nAPK totali: {len(apks)}"
        f"  |  Already completed: {len(already_completed)}"
        f"  |  from fare: {len(da_fare)}"
    )
    print(
        f"Tempo stimato: "
        f"~{len(da_fare) * WAIT_BETWEEN_REQUESTS // 60} minuti\n"
    )
    if not da_fare:
        print("[INFO] All APKs have already been processed.")
        return
    for i, apk_path in enumerate(da_fare, 1):
        name = apk_path.stem
        try:
            sha256 = sha256_of_file(apk_path)
            print(
                f"[{i:03d}/{len(da_fare)}] "
                f"{name[:50]} ..."
            )
            print(
                "       Checking hash on VT...",
                end=" ",
                flush=True
            )
            report = get_file_report(sha256)
            time.sleep(WAIT_BETWEEN_REQUESTS)
            if report:
                print(
                    f"already present -> "
                    f"Malicious: {report['malicious']}"
                )
                results[name] = {
                    "sha256": sha256,
                    "name": name,
                    "status": "ALREADY_PRESENT",
                    **report
                }
            else:
                print("not present, uploading...")
                analysis_id = upload_file(apk_path)
                time.sleep(WAIT_BETWEEN_REQUESTS)
                if not analysis_id or isinstance(analysis_id, tuple):
                    print("       [ERR] Upload failed")
                    results[name] = {
                        "sha256": sha256,
                        "name": name,
                        "status": "ERROR_UPLOAD",
                        "malicious": "",
                        "suspicious": "",
                        "undetected": "",
                        "harmless": ""
                    }
                else:
                    print(
                        "       Waiting for analysis...",
                        end=" ",
                        flush=True
                    )
                    report = get_analysis_result(analysis_id)
                    if report:
                        print(
                            f"completed -> "
                            f"Malicious: {report['malicious']}"
                        )
                        results[name] = {
                            "sha256": sha256,
                            "name": name,
                            "status": "ANALYZED",
                            **report
                        }
                    else:
                        print("timeout")
                        results[name] = {
                            "sha256": sha256,
                            "name": name,
                            "status": "TIMEOUT",
                            "malicious": "",
                            "suspicious": "",
                            "undetected": "",
                            "harmless": ""
                        }
            write_excel(
                results,
                args.output
            )
        except KeyboardInterrupt:
            print(
                "\n[INTERROTTO] "
                "Salvo i results fin qui e esco..."
            )
            write_excel(
                results,
                args.output
            )
            return
        except Exception as e:
            print(
                f"\n[ERR] error for {name}: {e}"
            )
            print(
                "       Salvo i results fin qui e mi fermo. "
                "Rilancia lo stesso comando for riprendere."
            )
            write_excel(
                results,
                args.output
            )
            raise
    print(
        f"\n[DONE] results salvati in: "
        f"{args.output}"
    )
    print(
        f"       total: {len(results)}"
    )
    print(
        f"       Analyzed: "
        f"{sum(1 for r in results.values() if r['status'] in ('ANALYZED','ALREADY_PRESENT'))}"
    )
    print(
        f"       Errors:     "
        f"{sum(1 for r in results.values() if r['status'] not in ('ANALYZED','ALREADY_PRESENT'))}"
    )
if __name__ == "__main__":
    main()