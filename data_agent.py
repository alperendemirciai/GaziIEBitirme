#!/usr/bin/env python3
"""
data_agent.py — Agent 2 of the notebook scheduling pipeline.

Parses siparisturu_v6.gms, validates its data section against the rules
documented in the agent prompts, and writes two reports:
    - data_validation_report.txt   (PASS / WARNING / ERROR per check)
    - orders_summary.txt           (descriptive statistics over the 198 jobs)

Exit codes:
    0  no critical errors
    1  one or more critical errors

Uses only the Python standard library. Does NOT modify siparisturu_v6.gms.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

GMS_FILE = "siparisturu_v6.gms"
REPORT_FILE = "data_validation_report.txt"
SUMMARY_FILE = "orders_summary.txt"

EXPECTED_JOB_COUNT = 198
EXPECTED_JOBS = [f"I{n:02d}" if n < 100 else f"I{n}" for n in range(1, EXPECTED_JOB_COUNT + 1)]

PRODUCT_SETS = [
    "i_TelDikis",
    "i_PlastikStd",
    "i_PlastikKucuk",
    "i_DblMetalKucuk",
    "i_DblMetalBuyuk",
    "i_ManuelSpiral",
    "i_IplikDikis",
]

RULING_SETS = ["i_cizgili", "i_kareli", "i_duz"]

PRODUCT_TO_ROUTES = {
    "i_TelDikis":      ["r1"],
    "i_PlastikStd":    ["r2", "r3"],
    "i_PlastikKucuk":  ["r2", "r3"],
    "i_DblMetalKucuk": ["r4", "r5"],
    "i_DblMetalBuyuk": ["r4", "r5"],
    "i_ManuelSpiral":  ["r6"],
    "i_IplikDikis":    ["r7"],
}

ROUTE_MACHINES = {
    "r1": ["Bielom2", "Shrink1", "MSK"],
    "r2": ["Bielom1", "PolarBicak", "Kugler", "Plasticol", "Shrink2", "MSK"],
    "r3": ["Bielom1", "PolarBicak", "Kore", "Shrink2", "MSK"],
    "r4": ["Bielom1", "PolarBicak", "Kugler", "Autobind", "Shrink2", "MSK"],
    "r5": ["Bielom1", "PolarBicak", "CWH", "Shrink2", "MSK"],
    "r6": ["Bielom1", "PolarBicak", "Kugler", "ManSpiral", "Shrink2", "MSK"],
    "r7": ["Bielom1", "PolarBicak", "Juki", "Shrink2", "MSK"],
}

ROUTE_BOTTLENECK = {
    "r1": "Bielom2",
    "r2": "Plasticol",
    "r3": "Kore",
    "r4": "Autobind",
    "r5": "CWH",
    "r6": "ManSpiral",
    "r7": "Juki",
}

PRODUCT_BOTTLENECK_SEC = {
    "i_TelDikis":      {"r1": 2.0},
    "i_PlastikStd":    {"r2": 15.0, "r3": 16.5},
    "i_PlastikKucuk":  {"r2": 10.0, "r3": 11.5},
    "i_DblMetalKucuk": {"r4": 9.0,  "r5": 15.0},
    "i_DblMetalBuyuk": {"r4": 17.0, "r5": 23.0},
    "i_ManuelSpiral":  {"r6": 17.0},
    "i_IplikDikis":    {"r7": 15.0},
}

MACHINE_CAPACITIES = {
    "Bielom1":    4800,
    "Bielom2":    4800,
    "Shrink1":    2400,
    "Shrink2":    2400,
    "MSK":        2400,
    "PolarBicak": 1200,
    "Kugler":     1200,
    "Plasticol":  1200,
    "Kore":       1200,
    "Autobind":   1200,
    "CWH":        1200,
    "ManSpiral":  1200,
    "Juki":       1200,
}


def read_gms(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_job_names(text: str) -> Dict[str, str]:
    """Parse the `Set i isler / ... /` block; returns {job_id: descriptive_name}."""
    m = re.search(r"Set\s+i\s+isler\s*/(.*?)/", text, re.DOTALL | re.IGNORECASE)
    if not m:
        raise RuntimeError("ERROR: Could not locate the `Set i isler /.../` block in the .gms file")
    block = m.group(1)
    names: Dict[str, str] = {}
    # Each line: I<num>  "Customer-Binding-...-Ruling"
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        match = re.match(r'(I\d+)\s+"([^"]*)"', line)
        if match:
            names[match.group(1)] = match.group(2)
    return names


def parse_qty(text: str) -> Dict[str, int]:
    """Parse the `Parameter qty(i) ... / ... /` block."""
    m = re.search(r"Parameter\s+qty\(i\)[^/]*/(.*?)/", text, re.DOTALL | re.IGNORECASE)
    if not m:
        raise RuntimeError("ERROR: Could not locate the `Parameter qty(i)` block in the .gms file")
    block = m.group(1)
    qty: Dict[str, int] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        match = re.match(r"(I\d+)\s+([\d.]+)", line)
        if match:
            qty[match.group(1)] = int(float(match.group(2)))
    return qty


def parse_named_job_set(text: str, set_name: str) -> List[str]:
    """Parse a named GAMS set like `i_TelDikis(i) "description" / I09, I10, ... /`.

    The description may contain `/` characters (e.g. "(r2:15 / r3:16.5)"), so we
    explicitly skip over an optional quoted description before locating the body.
    """
    pattern = rf'{re.escape(set_name)}\s*\(\s*i\s*\)\s*(?:"[^"]*")?\s*/\s*(.*?)\s*/'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    tokens = re.findall(r"I\d+", body)
    return tokens


def parse_teslim_dates(text: str) -> Dict[str, datetime.date]:
    """Parse `$eval TESLIM_I<n> jdate(YYYY,MM,DD)` lines."""
    teslim: Dict[str, datetime.date] = {}
    pattern = re.compile(
        r"\$eval\s+TESLIM_I(\d+)\s+jdate\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        n = int(match.group(1))
        y, mo, d = int(match.group(2)), int(match.group(3)), int(match.group(4))
        job_id = f"I{n:02d}" if n < 100 else f"I{n}"
        teslim[job_id] = datetime.date(y, mo, d)
    return teslim


def extract_customer_binding_ruling(job_name: str) -> Tuple[str, str, str]:
    """Job name format: CUSTOMER-BindingType-Pages-Format-RulingType.
    Returns (customer, binding_type, ruling_type)."""
    parts = job_name.split("-")
    if len(parts) >= 5:
        return parts[0].strip(), parts[1].strip(), parts[-1].strip()
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip(), (parts[-1].strip() if parts else "")
    return job_name, "", ""


def main() -> int:
    if not os.path.exists(GMS_FILE):
        print(f"ERROR: {GMS_FILE} not found in working directory.")
        return 1

    text = read_gms(GMS_FILE)
    today = datetime.date.today()

    # --- Parse all data blocks ---
    try:
        job_names = parse_job_names(text)
        qty = parse_qty(text)
        teslim = parse_teslim_dates(text)
        product_membership: Dict[str, List[str]] = {
            s: parse_named_job_set(text, s) for s in PRODUCT_SETS
        }
        ruling_membership: Dict[str, List[str]] = {
            s: parse_named_job_set(text, s) for s in RULING_SETS
        }
    except RuntimeError as exc:
        print(str(exc))
        return 1

    # --- Validation checks ---
    report_lines: List[str] = []
    critical_errors = 0
    warnings = 0

    def add(status: str, label: str, detail: str = "") -> None:
        nonlocal critical_errors, warnings
        line = f"[{status}] {label}"
        if detail:
            line += f"  --  {detail}"
        report_lines.append(line)
        if status == "ERROR":
            critical_errors += 1
            print(f"ERROR: {label}: {detail}")
        elif status == "WARNING":
            warnings += 1
            print(f"WARNING: {label}: {detail}")

    # Check 0: file recognises all 198 jobs
    missing_jobs = [j for j in EXPECTED_JOBS if j not in job_names]
    extra_jobs = [j for j in job_names if j not in EXPECTED_JOBS]
    if not missing_jobs and not extra_jobs and len(job_names) == EXPECTED_JOB_COUNT:
        add("PASS", "All 198 jobs (I01–I198) are declared in Set i")
    else:
        msg = ""
        if missing_jobs:
            msg += f"missing={missing_jobs[:10]}{'...' if len(missing_jobs) > 10 else ''}"
        if extra_jobs:
            msg += f" extra={extra_jobs[:10]}{'...' if len(extra_jobs) > 10 else ''}"
        if len(job_names) != EXPECTED_JOB_COUNT:
            msg += f" (parsed {len(job_names)}, expected {EXPECTED_JOB_COUNT})"
        add("ERROR", "Set i declaration", msg or "unknown mismatch")

    # Check 1: every job has qty > 0
    zero_qty_jobs = [j for j in EXPECTED_JOBS if qty.get(j, 0) == 0]
    if not zero_qty_jobs:
        add("PASS", "Every job has qty > 0")
    else:
        add(
            "WARNING",
            "Jobs with qty == 0 (excluded from K1)",
            ", ".join(zero_qty_jobs),
        )

    missing_qty = [j for j in EXPECTED_JOBS if j not in qty]
    if missing_qty:
        add(
            "ERROR",
            "Jobs missing qty entry",
            ", ".join(missing_qty[:10]),
        )

    # Check 2: delivery date in the future (d(i) > 0)
    past_due_jobs: List[Tuple[str, datetime.date, int]] = []
    missing_dates = [j for j in EXPECTED_JOBS if j not in teslim]
    if missing_dates:
        add(
            "ERROR",
            "Jobs missing TESLIM_I delivery date",
            ", ".join(missing_dates[:10]),
        )
    for j in EXPECTED_JOBS:
        if j not in teslim:
            continue
        days_left = (teslim[j] - today).days
        if days_left <= 0:
            past_due_jobs.append((j, teslim[j], days_left))
    if not past_due_jobs:
        add("PASS", f"All delivery dates are in the future relative to today ({today.isoformat()})")
    else:
        detail = "; ".join(
            f"{j} due={dt.isoformat()} (d(i)={days * 1200} min)" for j, dt, days in past_due_jobs[:10]
        )
        add(
            "ERROR",
            f"Jobs with d(i) <= 0 — past-due delivery dates ({len(past_due_jobs)} total)",
            detail,
        )

    # Check 3: each job in exactly one product type set
    product_owner: Dict[str, List[str]] = defaultdict(list)
    for set_name, members in product_membership.items():
        for j in members:
            product_owner[j].append(set_name)

    multi_product = {j: sets for j, sets in product_owner.items() if len(sets) > 1}
    no_product = [j for j in EXPECTED_JOBS if j not in product_owner]

    if not multi_product:
        add("PASS", "No job appears in more than one product type set")
    else:
        detail = "; ".join(f"{j}: {sorted(sets)}" for j, sets in list(multi_product.items())[:10])
        add("ERROR", "Jobs in multiple product sets", detail)

    if not no_product:
        add("PASS", "Every job appears in at least one product type set")
    else:
        add("ERROR", f"Jobs with NO product type set ({len(no_product)})", ", ".join(no_product[:15]))

    # Check 4: each job in exactly one ruling set
    ruling_owner: Dict[str, List[str]] = defaultdict(list)
    for set_name, members in ruling_membership.items():
        for j in members:
            ruling_owner[j].append(set_name)

    multi_ruling = {j: sets for j, sets in ruling_owner.items() if len(sets) > 1}
    no_ruling = [j for j in EXPECTED_JOBS if j not in ruling_owner]

    if not multi_ruling:
        add("PASS", "No job appears in more than one ruling type set")
    else:
        detail = "; ".join(f"{j}: {sorted(sets)}" for j, sets in list(multi_ruling.items())[:10])
        add("ERROR", "Jobs in multiple ruling sets", detail)

    if not no_ruling:
        add("PASS", "Every job appears in at least one ruling type set")
    else:
        add("ERROR", f"Jobs with NO ruling set ({len(no_ruling)})", ", ".join(no_ruling[:15]))

    # Check 5: capacity feasibility estimate
    # For each machine, sum minimum possible processing minutes given route choices.
    # Bottleneck cycle times come from PRODUCT_BOTTLENECK_SEC; non-bottleneck = 25%.
    # We pick the route that gives minimum bottleneck load for the job (the model's freedom).
    machine_load_min: Dict[str, float] = defaultdict(float)
    for j in EXPECTED_JOBS:
        if qty.get(j, 0) == 0:
            continue
        if j not in product_owner or not product_owner[j]:
            continue
        product = product_owner[j][0]
        route_times = PRODUCT_BOTTLENECK_SEC.get(product, {})
        if not route_times:
            continue
        # Pick the route giving the smallest total min-machine-load (use min cycle as proxy)
        chosen_route = min(route_times, key=lambda r: route_times[r])
        sec_per_unit = route_times[chosen_route]
        bottleneck_min = sec_per_unit * qty[j] / 60.0
        # All machines on this route get either the bottleneck time or 25% of it
        for m in ROUTE_MACHINES[chosen_route]:
            if m == ROUTE_BOTTLENECK[chosen_route]:
                machine_load_min[m] += bottleneck_min
            else:
                machine_load_min[m] += 0.25 * bottleneck_min

    overloaded: List[Tuple[str, float, int]] = []
    for m, load in machine_load_min.items():
        cap = MACHINE_CAPACITIES.get(m, 1200)
        if load > cap * 1.5:
            overloaded.append((m, load, cap))
    if not overloaded:
        add(
            "PASS",
            "Machine capacity estimate within 1.5x daily capacity assumption",
        )
    else:
        detail = "; ".join(
            f"{m}: load={load:,.0f} min vs cap={cap} min/day (ratio={load / cap:.2f}x days)"
            for m, load, cap in overloaded
        )
        add(
            "WARNING",
            "Machines that may need many days to clear backlog (total load > 1.5 × daily capacity)",
            detail,
        )

    # --- Write data_validation_report.txt ---
    overall = "PASS" if critical_errors == 0 else f"ERROR ({critical_errors} critical errors found)"
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Data validation report -- generated {datetime.datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"Source file: {GMS_FILE}\n")
        f.write(f"Today's date: {today.isoformat()}\n")
        f.write(f"Expected jobs: {EXPECTED_JOB_COUNT}\n")
        f.write("=" * 72 + "\n")
        for line in report_lines:
            f.write(line + "\n")
        f.write("=" * 72 + "\n")
        f.write(f"OVERALL: {overall}\n")
        f.write(f"WARNINGS: {warnings}\n")

    # --- Build orders_summary.txt ---
    by_binding = Counter()
    by_ruling = Counter()
    by_delivery_date = Counter()
    customers = Counter()

    for j in EXPECTED_JOBS:
        name = job_names.get(j, "")
        customer, binding, ruling = extract_customer_binding_ruling(name)
        customers[customer] += 1
        by_binding[binding] += 1
        by_ruling[ruling] += 1
        if j in teslim:
            by_delivery_date[teslim[j].isoformat()] += 1

    # Top 5 by qty
    top5 = sorted(
        ((qty.get(j, 0), j, job_names.get(j, "")) for j in EXPECTED_JOBS),
        reverse=True,
    )[:5]

    # Earliest delivery date
    if teslim:
        earliest_date = min(teslim.values())
        earliest_jobs = [j for j, d in teslim.items() if d == earliest_date]
        earliest_jobs.sort(key=lambda s: int(s[1:]))
    else:
        earliest_date = None
        earliest_jobs = []

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(f"Orders summary -- generated {datetime.datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"Source file: {GMS_FILE}\n")
        f.write("=" * 72 + "\n")
        f.write(f"Total jobs: {EXPECTED_JOB_COUNT}\n\n")

        f.write("-- Jobs by binding type --\n")
        for k, v in by_binding.most_common():
            f.write(f"  {k or '(blank)':<32s} {v}\n")
        f.write("\n")

        f.write("-- Jobs by ruling type --\n")
        for k, v in by_ruling.most_common():
            f.write(f"  {k or '(blank)':<32s} {v}\n")
        f.write("\n")

        f.write("-- Jobs by delivery date group --\n")
        for k, v in sorted(by_delivery_date.items()):
            f.write(f"  {k}  {v}\n")
        f.write("\n")

        f.write("-- Jobs by customer --\n")
        for k, v in customers.most_common():
            f.write(f"  {k or '(blank)':<32s} {v}\n")
        f.write("\n")

        f.write("-- Top 5 jobs by quantity --\n")
        for q, j, name in top5:
            f.write(f"  {j:<6s} qty={q:>10d}  {name}\n")
        f.write("\n")

        if earliest_date is not None:
            f.write(f"-- Earliest delivery date: {earliest_date.isoformat()} --\n")
            f.write(f"   {len(earliest_jobs)} job(s): {', '.join(earliest_jobs)}\n")

    print(f"Wrote {REPORT_FILE} and {SUMMARY_FILE}")
    print(f"OVERALL: {overall} | WARNINGS: {warnings}")
    print("DATA AGENT COMPLETE")
    return 0 if critical_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
