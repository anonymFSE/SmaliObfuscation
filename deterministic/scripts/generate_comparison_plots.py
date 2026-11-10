import argparse          
import requests          
import pandas as pd      
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, LineChart, Reference, PieChart
from openpyxl.chart.series import DataPoint
ORIG_FILE = "original_virustotal_results.xlsx"
REBUILT_FILE = "transformed_virustotal_results.xlsx"
VT_API = "https://www.virustotal.com/api/v3"
def fill(hex_color):
    return PatternFill(
        "solid",
        fgColor=hex_color
    )
def thin():
    s = Side(
        style="thin",
        color="CCCCCC"
    )
    return Border(
        left=s,
        right=s,
        top=s,
        bottom=s
    )
def header_cell(
    ws,
    row,
    col,
    value,
    bg="1E3A5F",
    fg="FFFFFF",
    size=9,
    wrap=False
):
    c = ws.cell(
        row,
        col,
        value
    )
    c.font = Font(
        name="Arial",
        bold=True,
        size=size,
        color=fg
    )
    c.fill = fill(bg)
    c.alignment = Alignment(
        horizontal="center",
        vertical="center",
        wrap_text=wrap
    )
    c.border = thin()
    return c
def data_cell(
    ws,
    row,
    col,
    value,
    bg="FFFFFF",
    bold=False,
    color="000000",
    halign="center"
):
    c = ws.cell(
        row,
        col,
        value
    )
    c.font = Font(
        name="Arial",
        size=8,
        bold=bold,
        color=color
    )
    c.fill = fill(bg)
    c.alignment = Alignment(
        horizontal=halign,
        vertical="center"
    )
    c.border = thin()
    return c
def vt_get(sha256, api_key):
    headers = {
        "x-apikey": api_key
    }
    try:
        r = requests.get(
            f"{VT_API}/files/{sha256}",
            headers=headers,
            timeout=30
        )
        if r.status_code == 200:
            stats = r.json()["data"]["attributes"]["last_analysis_stats"]
            return {
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "undetected": stats.get("undetected", 0),
                "harmless": stats.get("harmless", 0),
                "status": "ANALYZED",
            }
        return {
            "malicious": None,
            "suspicious": None,
            "undetected": None,
            "harmless": None,
            "status": f"ERROR_{r.status_code}"
        }
    except Exception as e:
        return {
            "malicious": None,
            "suspicious": None,
            "undetected": None,
            "harmless": None,
            "status": f"ERROR: {e}"
        }
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api_key",
        required=True
    )
    parser.add_argument(
        "--orig",
        default=ORIG_FILE
    )
    parser.add_argument(
        "--rebuilt",
        default=REBUILT_FILE
    )
    parser.add_argument(
        "--output",
        default=None
    )
    parser.add_argument(
        "--family",
        default="SpyNote-RAT"
    )
    args = parser.parse_args()
    output_file = (
        args.output
        or f"comparison_results_{args.family}.xlsx"
    )
    titolo = (
        f"ORIGINAL vs REBUILT COMPARISON — "
        f"Reflection-based Call — {args.family}"
    )
    orig_df = pd.read_excel(
        args.orig
    )
    reb_df = pd.read_excel(
        args.rebuilt
    )
    tot_originali = len(orig_df)
    tot_rebuilt = len(reb_df)
    tot_non_rebuilt = (
        tot_originali - tot_rebuilt
    )
    tot_timeout_orig = 0
    if "Status" in orig_df.columns:
        tot_timeout_orig = (
            orig_df["Status"]
            .astype(str)
            .str.contains(
                "TIMEOUT|ERROR",
                na=False
            )
            .sum()
        )
    tot_timeout_reb = 0
    if "Status" in reb_df.columns:
        tot_timeout_reb = (
            reb_df["Status"]
            .astype(str)
            .str.contains(
                "TIMEOUT|ERROR",
                na=False
            )
            .sum()
        )
    orig_df["SHA256"] = (
        orig_df["SHA256"]
        .astype(str)
        .str.strip()
        .str.lower()
    )
    reb_df["SHA256"] = (
        reb_df["SHA256"]
        .astype(str)
        .str.strip()
        .str.lower()
    )
    reb_df["APK Name"] = (
        reb_df["APK Name"]
        .astype(str)
        .str.strip()
        .str.lower()
    )
    reb_df["HASH_ORIG"] = (
        reb_df["APK Name"]
        .str.replace(
            ".apk",
            "",
            regex=False
        )
        .str.strip()
    )
    if "Status" in orig_df.columns:
        orig_timeout = orig_df[
            orig_df["Status"]
            .astype(str)
            .str.contains(
                "TIMEOUT|ERROR",
                na=False
            )
        ]
        if not orig_timeout.empty:
            print(
                f"\nRieseguo VT for "
                f"{len(orig_timeout)} originals in timeout..."
            )
            for _, row in orig_timeout.iterrows():
                sha = str(
                    row["SHA256"]
                ).strip()
                print(
                    f"  [ORIG {sha[:20]}...] ",
                    end="",
                    flush=True
                )
                retry = vt_get(
                    sha,
                    args.api_key
                )
                print(
                    f"Status: {retry['status']}  |  "
                    f"Malicious: {retry['malicious']}"
                )
                if retry["status"] == "ANALYZED":
                    mask = (
                        orig_df["SHA256"] == sha
                    )
                    orig_df.loc[
                        mask,
                        "Status"
                    ] = "ANALYZED"
                    orig_df.loc[
                        mask,
                        "Malicious"
                    ] = retry["malicious"]
                    orig_df.loc[
                        mask,
                        "Undetected"
                    ] = retry["undetected"]
                    orig_df.loc[
                        mask,
                        "Suspicious"
                    ] = retry["suspicious"]
    if "Status" in reb_df.columns:
        reb_timeout = reb_df[
            reb_df["Status"]
            .astype(str)
            .str.contains(
                "TIMEOUT|ERROR",
                na=False
            )
        ]
        if not reb_timeout.empty:
            print(
                f"\nRieseguo VT for "
                f"{len(reb_timeout)} rebuilt in timeout..."
            )
            for _, row in reb_timeout.iterrows():
                sha_reb = str(
                    row["SHA256"]
                ).strip()
                sha_orig = str(
                    row["HASH_ORIG"]
                ).strip()
                print(
                    f"  [REB {sha_orig[:20]}...] "
                    f"rebuilt={sha_reb[:16]}... ",
                    end="",
                    flush=True
                )
                retry = vt_get(
                    sha_reb,
                    args.api_key
                )
                print(
                    f"Status: {retry['status']}  |  "
                    f"Malicious: {retry['malicious']}"
                )
                mask = (
                    reb_df["HASH_ORIG"] == sha_orig
                )
                if mask.any() and retry["status"] == "ANALYZED":
                    reb_df.loc[
                        mask,
                        "Status"
                    ] = "ANALYZED"
                    reb_df.loc[
                        mask,
                        "Malicious"
                    ] = retry["malicious"]
                    reb_df.loc[
                        mask,
                        "Undetected"
                    ] = retry["undetected"]
                elif mask.any():
                    reb_df.loc[
                        mask,
                        "Status"
                    ] = retry["status"]
    orig_cols = [
        "SHA256",
        "Malicious",
        "Undetected",
        "Suspicious"
    ]
    if "Status" in orig_df.columns:
        orig_cols.append("Status")
    merged = pd.merge(
        orig_df[orig_cols],
        reb_df[
            [
                "SHA256",
                "HASH_ORIG",
                "Malicious",
                "Undetected",
                "Status"
            ]
        ],
        left_on="SHA256",
        right_on="HASH_ORIG",
        how="left",
        suffixes=(
            "_orig",
            "_reb"
        )
    )
    rows = []
    for i, r in merged.iterrows():
        sha_orig = str(
            r["SHA256_orig"]
        ).strip()
        sha_reb = str(
            r.get(
                "SHA256_reb",
                ""
            )
        ).strip()
        mal_orig = (
            int(r["Malicious_orig"])
            if pd.notna(r["Malicious_orig"])
            else 0
        )
        und_orig = (
            int(r["Undetected_orig"])
            if pd.notna(r["Undetected_orig"])
            else 0
        )
        stato_col = (
            "Status_reb"
            if "Status_reb" in merged.columns
            else "Status"
        )
        stato_reb = (
            str(
                r.get(
                    stato_col,
                    "MISSING"
                )
            ).strip()
            if sha_reb not in ("", "nan", "0")
            else "MISSING"
        )
        if stato_reb in ("MISSING", "nan"):
            rows.append({
                "sha_orig": sha_orig,
                "sha_reb": "—",
                "status": "MISSING",
                "mal_orig": mal_orig,
                "mal_reb": None,
                "delta": None,
                "pct": None,
                "und_orig": und_orig,
                "und_reb": None
            })
        elif (
            "TIMEOUT" in stato_reb
            or
            "ERROR" in stato_reb
        ):
            rows.append({
                "sha_orig": sha_orig,
                "sha_reb": sha_reb,
                "status": stato_reb,
                "mal_orig": mal_orig,
                "mal_reb": None,
                "delta": None,
                "pct": None,
                "und_orig": und_orig,
                "und_reb": None
            })
        else:
            mal_reb = (
                int(r["Malicious_reb"])
                if pd.notna(r["Malicious_reb"])
                else 0
            )
            und_reb = (
                int(r["Undetected_reb"])
                if pd.notna(r["Undetected_reb"])
                else 0
            )
            delta = (
                mal_reb - mal_orig
            )
            pct = (
                round(
                    (mal_orig - mal_reb)
                    / mal_orig
                    * 100,
                    1
                )
                if mal_orig > 0
                else 0.0
            )
            rows.append({
                "sha_orig": sha_orig,
                "sha_reb": sha_reb,
                "status": "ANALYZED",
                "mal_orig": mal_orig,
                "mal_reb": mal_reb,
                "delta": delta,
                "pct": pct,
                "und_orig": und_orig,
                "und_reb": und_reb
            })
    analyzed = [
        r for r in rows
        if r["status"] == "ANALYZED"
    ]
    excluded = [
        r for r in rows
        if r["status"] != "ANALYZED"
    ]
    rows_f1 = [
        r for r in rows
        if r["status"] != "MISSING"
    ]
    n = len(analyzed)
    media_orig = (
        sum(r["mal_orig"] for r in analyzed) / n
        if n
        else 0
    )
    media_reb = (
        sum(r["mal_reb"] for r in analyzed) / n
        if n
        else 0
    )
    media_delta = (
        sum(r["delta"] for r in analyzed) / n
        if n
        else 0
    )
    media_pct = (
        sum(r["pct"] for r in analyzed) / n
        if n
        else 0
    )
    media_und_o = (
        sum(r["und_orig"] for r in analyzed) / n
        if n
        else 0
    )
    media_und_r = (
        sum(r["und_reb"] for r in analyzed) / n
        if n
        else 0
    )
    n_analizzati = len(analyzed)
    n_missing = sum(
        1
        for r in rows
        if r["status"] == "MISSING"
    )
    n_timeout = sum(
        1
        for r in rows
        if (
            "TIMEOUT" in r["status"]
            or
            "ERROR" in r["status"]
        )
    )
    evasione_totale = sum(
        1
        for r in analyzed
        if r["mal_reb"] == 0
    )
    evasione_50 = sum(
        1
        for r in analyzed
        if (
            r["pct"] is not None
            and
            r["pct"] >= 50
        )
    )
    dim_tutti = sum(
        1
        for r in analyzed
        if (
            r["delta"] is not None
            and
            r["delta"] < 0
        )
    )
    print(
        f"\nStatistics for {n} samples analyzed:"
    )
    print(
        f"  Total original APKs:    "
        f"{tot_originali}"
    )
    print(
        f"  APK rebuilt:             "
        f"{tot_rebuilt}"
    )
    print(
        f"  Malicious mean ORIG:    "
        f"{media_orig:.2f}"
    )
    print(
        f"  Malicious mean REBUILT: "
        f"{media_reb:.2f}"
    )
    print(
        f"  Reduction mean:         "
        f"{media_delta:.2f} "
        f"({media_pct:.1f}%)"
    )
    wb = Workbook()
    HDR  = "1E3A5F"
    ALT1 = "F0F6FF"
    ALT2 = "FFFFFF"
    GRY  = "E9ECEF"
    YLW  = "FFF3CD"
    ws1 = wb.active
    ws1.title = "Complete Comparison"
    ws1.merge_cells("A1:J1")
    c = ws1["A1"]
    c.value = titolo
    c.font = Font(
        name="Arial",
        bold=True,
        size=12,
        color="FFFFFF"
    )
    c.fill = fill(HDR)
    c.alignment = Alignment(
        horizontal="center",
        vertical="center"
    )
    ws1.row_dimensions[1].height = 26
    ws1.merge_cells("A2:J2")
    c = ws1["A2"]
    c.value = (
        f"Samples analyzed: {n}  |  "
        f"Malicious: {media_orig:.1f} → {media_reb:.1f}  |  "
        f"Reduction: −{abs(media_delta):.1f} AV "
        f"({media_pct:.1f}%)"
    )
    c.font = Font(
        name="Arial",
        italic=True,
        size=9,
        color="444444"
    )
    c.fill = fill("F0F4FA")
    c.alignment = Alignment(
        horizontal="center"
    )
    ws1.row_dimensions[2].height = 15
    hdrs1 = [
        "#",
        "Original SHA256",
        "SHA256 Rebuilt",
        "Pipeline Status",
        "Malicious Orig",
        "Malicious Rebuilt",
        "Undetected Orig",
        "Undetected Rebuilt",
        "Δ Malicious",
        "Reduction %"
    ]
    ws1.row_dimensions[3].height = 30
    for col, h in enumerate(
        hdrs1,
        1
    ):
        header_cell(
            ws1,
            3,
            col,
            h,
            wrap=True
        )
    for i, row in enumerate(rows_f1):
        r = i + 4
        sp = row["status"]
        bg = (
            YLW
            if (
                "TIMEOUT" in sp
                or
                "ERROR" in sp
            )
            else (
                ALT1
                if i % 2 == 0
                else ALT2
            )
        )
        data_cell(
            ws1,
            r,
            1,
            i + 1,
            bg=bg
        )
        data_cell(
            ws1,
            r,
            2,
            row["sha_orig"],
            bg=bg,
            halign="left"
        )
        data_cell(
            ws1,
            r,
            3,
            row["sha_reb"],
            bg=bg,
            halign="left"
        )
        data_cell(
            ws1,
            r,
            4,
            sp,
            bg=bg
        )
        data_cell(
            ws1,
            r,
            5,
            row["mal_orig"],
            bg=bg
        )
        data_cell(
            ws1,
            r,
            6,
            (
                row["mal_reb"]
                if row["mal_reb"] is not None
                else "—"
            ),
            bg=bg
        )
        data_cell(
            ws1,
            r,
            7,
            row["und_orig"],
            bg=bg
        )
        data_cell(
            ws1,
            r,
            8,
            (
                row["und_reb"]
                if row["und_reb"] is not None
                else "—"
            ),
            bg=bg
        )
        delta = row["delta"]
        if delta is not None:
            col_d = (
                "155724"
                if delta < 0
                else (
                    "7B0000"
                    if delta > 0
                    else "555555"
                )
            )
            data_cell(
                ws1,
                r,
                9,
                delta,
                bg=bg,
                bold=True,
                color=col_d
            )
        else:
            data_cell(
                ws1,
                r,
                9,
                "—",
                bg=bg
            )
        pct = row["pct"]
        if pct is not None:
            col_p = (
                "155724"
                if pct >= 50
                else (
                    "856404"
                    if pct >= 25
                    else "7B0000"
                )
            )
            data_cell(
                ws1,
                r,
                10,
                f"{pct}%",
                bg=bg,
                bold=True,
                color=col_p
            )
        else:
            data_cell(
                ws1,
                r,
                10,
                "—",
                bg=bg
            )
        ws1.row_dimensions[r].height = 13
    for i, w in enumerate(
        [
            4,
            65,
            65,
            14,
            14,
            16,
            14,
            16,
            12,
            12
        ],
        1
    ):
        ws1.column_dimensions[
            get_column_letter(i)
        ].width = w
    ws1.freeze_panes = "A4"
    ws2 = wb.create_sheet(
        "Statistics"
    )
    ws2.merge_cells("A1:B1")
    header_cell(
        ws2,
        1,
        1,
        "SUMMARY STATISTICS",
        size=11
    )
    ws2.row_dimensions[1].height = 24
    stats = [
        (
            "Total original APKs",
            tot_originali
        ),
        (
            "Successfully rebuilt APKs",
            tot_rebuilt
        ),
        (
            "APKs that could not be rebuilt",
            tot_non_rebuilt
        ),
        (
            "APKs analyzed on VT "
            "(coppie complete)",
            n
        ),
        (
            "APK excluded dal calculation "
            "(TIMEOUT/MISSING)",
            len(excluded)
        ),
        ("", ""),
        (
            "Mean Malicious — original",
            f"{media_orig:.2f}"
        ),
        (
            "Mean Malicious — rebuilt",
            f"{media_reb:.2f}"
        ),
        (
            "Mean absolute delta",
            f"−{abs(media_delta):.2f} AV"
        ),
        (
            "Mean detection-rate reduction",
            f"{media_pct:.1f}%"
        ),
        ("", ""),
        (
            "Mean Undetected — original",
            f"{media_und_o:.2f}"
        ),
        (
            "Mean Undetected — rebuilt",
            f"{media_und_r:.2f}"
        ),
        (
            "Mean Undetected increase",
            f"+{media_und_r-media_und_o:.2f}"
        ),
        ("", ""),
        (
            "APKs with reduced Malicious count",
            f"{dim_tutti}/{n}"
        ),
        (
            "APKs with ≥50% evasion",
            f"{evasione_50}/{n}"
        ),
        (
            "APKs with complete evasion (0 AV)",
            f"{evasione_totale}/{n}"
        ),
    ]
    for i, (label, val) in enumerate(stats):
        r = i + 2
        bg = (
            "F7F7F7"
            if not label
            else (
                ALT1
                if i % 2 == 0
                else ALT2
            )
        )
        c1 = ws2.cell(
            r,
            1,
            label
        )
        c1.font = Font(
            name="Arial",
            size=10,
            bold=bool(label)
        )
        c1.fill = fill(bg)
        c1.border = thin()
        c1.alignment = Alignment(
            horizontal="left",
            vertical="center"
        )
        c2 = ws2.cell(
            r,
            2,
            str(val)
            if val != ""
            else ""
        )
        c2.font = Font(
            name="Arial",
            size=10
        )
        c2.fill = fill(bg)
        c2.border = thin()
        c2.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )
        ws2.row_dimensions[r].height = 18
    ws2.column_dimensions["A"].width = 42
    ws2.column_dimensions["B"].width = 22
    ws3 = wb.create_sheet(
        "Excluded from Calculation"
    )
    ws3.merge_cells("A1:D1")
    header_cell(
        ws3,
        1,
        1,
        "SAMPLES EXCLUDED FROM PERCENTAGE CALCULATION",
        size=10
    )
    ws3.row_dimensions[1].height = 22
    for col, h in enumerate(
        [
            "Original SHA256",
            "SHA256 Rebuilt",
            "Reason",
            "Note"
        ],
        1
    ):
        header_cell(
            ws3,
            2,
            col,
            h
        )
    for i, row in enumerate(excluded):
        r = i + 3
        bg = (
            YLW
            if (
                "TIMEOUT" in row["status"]
                or
                "ERROR" in row["status"]
            )
            else GRY
        )
        reason = row["status"]
        nota = (
            "Rescan on VT"
            if (
                "TIMEOUT" in reason
                or
                "ERROR" in reason
            )
            else "APK not rebuilt"
        )
        for col, val in enumerate(
            [
                row["sha_orig"],
                row["sha_reb"],
                reason,
                nota
            ],
            1
        ):
            c = ws3.cell(
                r,
                col,
                val
            )
            c.font = Font(
                name="Arial",
                size=9
            )
            c.fill = fill(bg)
            c.border = thin()
            c.alignment = Alignment(
                horizontal="left",
                vertical="center"
            )
        ws3.row_dimensions[r].height = 15
    for i, w in enumerate(
        [
            65,
            65,
            20,
            35
        ],
        1
    ):
        ws3.column_dimensions[
            get_column_letter(i)
        ].width = w
    ws4 = wb.create_sheet(
        "Charts"
    )
    ws4.merge_cells("A1:N1")
    c = ws4["A1"]
    c.value = (
        f"GRAFICI — {args.family} "
        f"— Reflection-based Call"
    )
    c.font = Font(
        name="Arial",
        bold=True,
        size=12,
        color="FFFFFF"
    )
    c.fill = fill(HDR)
    c.alignment = Alignment(
        horizontal="center",
        vertical="center"
    )
    ws4.row_dimensions[1].height = 24
    DR = 80
    ws4.cell(
        DR,
        1,
        "APK"
    )
    ws4.cell(
        DR,
        2,
        "Mean Malicious"
    )
    ws4.cell(
        DR + 1,
        1,
        "Original"
    )
    ws4.cell(
        DR + 1,
        2,
        round(media_orig, 2)
    )
    ws4.cell(
        DR + 2,
        1,
        "obfuscated"
    )
    ws4.cell(
        DR + 2,
        2,
        round(media_reb, 2)
    )
    ws4.cell(
        DR + 5,
        1,
        "Status"
    )
    ws4.cell(
        DR + 5,
        2,
        "Samples"
    )
    ws4.cell(
        DR + 6,
        1,
        "analyzed"
    )
    ws4.cell(
        DR + 6,
        2,
        n_analizzati
    )
    ws4.cell(
        DR + 7,
        1,
        "Missing"
    )
    ws4.cell(
        DR + 7,
        2,
        n_missing
    )
    ws4.cell(
        DR + 8,
        1,
        "Timeout/Error"
    )
    ws4.cell(
        DR + 8,
        2,
        n_timeout
    )
    ws4.cell(
        DR + 12,
        1,
        "Sample"
    )
    ws4.cell(
        DR + 12,
        2,
        "Malicious Orig"
    )
    ws4.cell(
        DR + 12,
        3,
        "Malicious Rebuilt"
    )
    for i, row in enumerate(analyzed):
        ws4.cell(
            DR + 13 + i,
            1,
            i + 1
        )
        ws4.cell(
            DR + 13 + i,
            2,
            row["mal_orig"]
        )
        ws4.cell(
            DR + 13 + i,
            3,
            row["mal_reb"]
        )
    chart1 = BarChart()
    chart1.type = "col"
    chart1.title = (
        "Mean Comparison: "
        "Malicious Original vs obfuscated"
    )
    chart1.y_axis.title = (
        "Mean AV engines"
    )
    chart1.style = 10
    chart1.width = 18
    chart1.height = 12
    chart1.grouping = "clustered"
    ref_vals = Reference(
        ws4,
        min_col=2,
        min_row=DR,
        max_row=DR + 2
    )
    ref_cats = Reference(
        ws4,
        min_col=1,
        min_row=DR + 1,
        max_row=DR + 2
    )
    chart1.add_data(
        ref_vals,
        titles_from_data=True
    )
    chart1.set_categories(
        ref_cats
    )
    chart1.series[0].graphicalProperties.solidFill = "C0392B"
    from openpyxl.chart.series import DataPoint as DP
    pt = DP(idx=1)
    pt.graphicalProperties.solidFill = "27AE60"
    chart1.series[0].dPt.append(pt)
    ws4.add_chart(
        chart1,
        "A3"
    )
    chart2 = PieChart()
    chart2.title = "Pipeline Status"
    chart2.style = 10
    chart2.width = 14
    chart2.height = 12
    ref_pie_v = Reference(
        ws4,
        min_col=2,
        min_row=DR + 5,
        max_row=DR + 8
    )
    ref_pie_c = Reference(
        ws4,
        min_col=1,
        min_row=DR + 6,
        max_row=DR + 8
    )
    chart2.add_data(
        ref_pie_v,
        titles_from_data=True
    )
    chart2.set_categories(
        ref_pie_c
    )
    for idx, color in enumerate(
        [
            "27AE60",
            "95A5A6",
            "E67E22"
        ]
    ):
        pt = DataPoint(
            idx=idx
        )
        pt.graphicalProperties.solidFill = color
        chart2.series[0].dPt.append(pt)
    ws4.add_chart(
        chart2,
        "J3"
    )
    chart3 = LineChart()
    chart3.title = (
        "Andamento Malicious for Sample: "
        "Original vs obfuscated"
    )
    chart3.y_axis.title = (
        "N° motori AV"
    )
    chart3.x_axis.title = (
        "Sample"
    )
    chart3.style = 10
    chart3.width = 30
    chart3.height = 14
    ref_line_v = Reference(
        ws4,
        min_col=2,
        max_col=3,
        min_row=DR + 12,
        max_row=DR + 12 + n
    )
    ref_line_c = Reference(
        ws4,
        min_col=1,
        min_row=DR + 13,
        max_row=DR + 12 + n
    )
    chart3.add_data(
        ref_line_v,
        titles_from_data=True
    )
    chart3.set_categories(
        ref_line_c
    )
    chart3.series[0].graphicalProperties.line.solidFill = "C0392B"
    chart3.series[0].graphicalProperties.line.width = 20000
    chart3.series[1].graphicalProperties.line.solidFill = "27AE60"
    chart3.series[1].graphicalProperties.line.width = 20000
    ws4.add_chart(
        chart3,
        "A23"
    )
    for i, w in enumerate(
        [14] * 14,
        1
    ):
        ws4.column_dimensions[
            get_column_letter(i)
        ].width = w
    wb.save(
        output_file
    )
    print(
        f"\n[DONE] Saved: "
        f"{output_file}"
    )
    print(
        f"  Sheet 1: Complete Comparison "
        f"({len(rows_f1)} rows, MISSING excluded)"
    )
    print(
        "  Sheet 2: Summary statistics"
    )
    print(
        f"  Sheet 3: Excluded from calculation "
        f"({len(excluded)} lines)"
    )
    print(
        "  Sheet 4: 3 charts"
    )
if __name__ == "__main__":
    main()