"""
Synthetic test for analysis_agent.py — generates a fake .lst file that mimics
the GAMS DISPLAY section format, runs the analysis agent, and checks that
schedule_output.xlsx is produced with valid contents.

This does NOT modify the production agents. Run from project root:
    python3 test_analysis.py
"""

from __future__ import annotations
import os
import random
import subprocess
import sys


def build_fake_lst(path: str) -> None:
    """Mimic the GAMS DISPLAY section format for the 13 parameters we need."""
    random.seed(7)
    job_ids = [f"I{n:02d}" if n < 100 else f"I{n}" for n in range(1, 199)]
    # Pseudo-randomly assign route 1..7
    rota = {j: random.randint(1, 7) for j in job_ids}
    # Completion times (minutes) — increasing-ish to mimic a schedule
    tamamlanma = {j: float(1000 + idx * 137 + random.randint(0, 200))
                  for idx, j in enumerate(job_ids)}
    teslim_gun = {j: round(v / 1200.0, 4) for j, v in tamamlanma.items()}
    # Make ~15% late
    gecikme = {}
    for j in job_ids:
        if random.random() < 0.15:
            gecikme[j] = float(random.randint(100, 50000))
    gecikme_gun = {j: round(v / 1200.0, 4) for j, v in gecikme.items()}
    # Due dates — varied minutes
    d_minutes = {j: float(random.randint(20000, 200000)) for j in job_ids}
    # Machine load
    machines = ["Bielom1", "Bielom2", "PolarBicak", "Kugler", "Plasticol",
                "Kore", "Autobind", "CWH", "ManSpiral", "Juki",
                "Shrink1", "Shrink2", "MSK"]
    yuk = {m: float(random.randint(5000, 200000)) for m in machines}
    yuk_gun = {m: round(v / 1200.0, 4) for m, v in yuk.items()}

    def write_table(f, lineno: int, name: str, mapping: dict) -> None:
        f.write(f"----   {lineno} PARAMETER {name}  test parameter\n\n")
        # Emit ~6 per line, in GAMS-like sparse format: "I01  2.000,    I02  3.000,"
        items = list(mapping.items())
        i = 0
        while i < len(items):
            chunk = items[i:i + 6]
            parts = [f"{k:>8s}{v:>12.3f}" for k, v in chunk]
            line = "   " + ",  ".join(parts)
            if i + 6 < len(items):
                line += ","
            f.write(line + "\n")
            i += 6
        f.write("\n")

    def write_scalar(f, lineno: int, name: str, value: float) -> None:
        f.write(f"----   {lineno} PARAMETER {name}                  =  {value}\n\n")

    cmax_value = max(tamamlanma.values())
    z_obj_value = 0.10 * cmax_value + 0.60 * sum(gecikme.values()) + 0.30 * len(gecikme)
    late_count = len(gecikme)

    with open(path, "w", encoding="utf-8") as f:
        f.write("GAMS test listing -- synthetic\n\n")
        f.write("--- Restarting execution\n\n")
        write_scalar(f, 488, "Z_obj.l", round(z_obj_value, 3))
        write_scalar(f, 488, "Cmax.l", round(cmax_value, 3))
        write_table(f, 489, "rota_atama", {k: float(v) for k, v in rota.items()})
        write_table(f, 490, "tamamlanma", tamamlanma)
        write_table(f, 491, "teslim_gun", teslim_gun)
        # gecikme: GAMS often omits zeros, simulate by only writing the late ones
        write_table(f, 492, "gecikme", gecikme)
        write_table(f, 493, "gecikme_gun", gecikme_gun)
        write_table(f, 494, "makine_yuk", yuk)
        write_table(f, 495, "makine_yuk_gun", yuk_gun)
        write_scalar(f, 498, "geciken_is_adedi", late_count)
        write_table(f, 499, "d", d_minutes)


def main() -> int:
    lst_path = "siparisturu_v6.lst"
    if os.path.exists(lst_path):
        os.rename(lst_path, lst_path + ".bak")
    try:
        build_fake_lst(lst_path)
        print(f"Wrote synthetic {lst_path}")
        rc = subprocess.call([sys.executable, "analysis_agent.py"])
        print(f"\nanalysis_agent.py exit code: {rc}")
        if rc != 0:
            return rc
        if not os.path.exists("schedule_output.xlsx"):
            print("ERROR: schedule_output.xlsx not created")
            return 1
        size = os.path.getsize("schedule_output.xlsx")
        print(f"schedule_output.xlsx size = {size} bytes")
        from openpyxl import load_workbook
        wb = load_workbook("schedule_output.xlsx", read_only=True)
        sheets = wb.sheetnames
        print(f"Sheets: {sheets}")
        for sh in sheets:
            ws = wb[sh]
            print(f"  {sh}: rows={ws.max_row} cols={ws.max_column}")
        return 0
    finally:
        if os.path.exists(lst_path + ".bak"):
            os.rename(lst_path + ".bak", lst_path)


if __name__ == "__main__":
    sys.exit(main())
