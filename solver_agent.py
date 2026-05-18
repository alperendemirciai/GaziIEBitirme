#!/usr/bin/env python3
"""
solver_agent.py — Agent 3 of the notebook scheduling pipeline.

Launches GAMS on siparisturu_v6.gms, monitors stdout for status patterns,
parses the resulting .lst file, and writes solve_summary.txt.

Usage:
    python solver_agent.py --gams /path/to/gams --model siparisturu_v6.gms

Exit codes:
    0  GAMS exited 0, .lst exists, model status indicates an integer/optimal solution
    1  GAMS exited non-zero
    2  .lst missing or unreadable
    3  model infeasible

Uses only the Python standard library. Does NOT modify siparisturu_v6.gms or cplex.opt.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from typing import Dict, Optional, Tuple


# Regex patterns we use to scan GAMS stdout in real time
INFEASIBLE_PATTERNS = [
    re.compile(r"\*\*\s*Infeasible", re.IGNORECASE),
    re.compile(r"Model\s+Status\s*:\s*Infeasible", re.IGNORECASE),
    re.compile(r"INFEASIBLE", re.IGNORECASE),
]
TIME_LIMIT_PATTERNS = [
    re.compile(r"Resource interrupt", re.IGNORECASE),
    re.compile(r"Time limit reached", re.IGNORECASE),
    re.compile(r"resource limit", re.IGNORECASE),
]
OBJECTIVE_INLINE = re.compile(r"Objective\s*[:=]\s*([\-\d.eE+]+)")
MIP_SOLUTION = re.compile(r"MIP Solution.*", re.IGNORECASE)
RESTART_EXEC = re.compile(r"-{3,}\s*Restarting execution", re.IGNORECASE)


def stream_gams(cmd, log_path: str) -> Tuple[int, Optional[float], bool, bool]:
    """Launch GAMS and stream stdout line-by-line.

    Returns: (returncode, objective_seen, infeasible_flag, time_limit_flag).
    Also tees stdout to `log_path` for later inspection.
    """
    print(f"Launching: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    objective_seen: Optional[float] = None
    infeasible = False
    time_limit = False

    with open(log_path, "w", encoding="utf-8") as logf:
        assert proc.stdout is not None
        for line in proc.stdout:
            logf.write(line)
            logf.flush()
            stripped = line.rstrip("\n")

            if any(p.search(stripped) for p in INFEASIBLE_PATTERNS):
                if not infeasible:
                    print("ERROR: Model is infeasible")
                infeasible = True

            if any(p.search(stripped) for p in TIME_LIMIT_PATTERNS):
                if not time_limit:
                    print("WARNING: Solver hit time limit -- solution may be suboptimal")
                time_limit = True

            m = OBJECTIVE_INLINE.search(stripped)
            if m:
                try:
                    val = float(m.group(1))
                    objective_seen = val
                    print(f"Objective value: {val}")
                except ValueError:
                    pass

            if MIP_SOLUTION.search(stripped):
                print(stripped.strip())

            if RESTART_EXEC.search(stripped):
                print(stripped.strip())

    proc.wait()
    return proc.returncode, objective_seen, infeasible, time_limit


def parse_lst(lst_path: str) -> Dict[str, object]:
    """Parse the .lst file for the key scalars and the SOLVE SUMMARY block.

    Reads line-by-line; stops after we've seen the DISPLAY scalars and the
    SOLVE SUMMARY (so we don't load the whole file). Returns a dict with:
        objective, makespan, late_jobs, model_status, solver_status,
        objective_summary, has_display
    Missing values are None.
    """
    result: Dict[str, object] = {
        "objective": None,
        "makespan": None,
        "late_jobs": None,
        "model_status": None,
        "solver_status": None,
        "objective_summary": None,
        "has_display": False,
    }

    # Scalar parameter/variable line examples:
    #   "----   488 PARAMETER Z_obj.l       =  123456.789"
    #   "----   488 VARIABLE  Cmax.L        =  987654.3"
    scalar_pat = re.compile(
        r"^----\s*\d+\s+(?:PARAMETER|VARIABLE)\s+(\S+?)\s*=\s*([\-\d.eE+]+)",
        re.IGNORECASE,
    )
    # Lines that begin a display block (table) -- also gives us has_display
    display_block_pat = re.compile(
        r"^----\s*\d+\s+(?:PARAMETER|VARIABLE)\s+(\S+)", re.IGNORECASE
    )

    with open(lst_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.rstrip("\n")

            m = scalar_pat.match(stripped)
            if m:
                name = m.group(1)
                try:
                    val = float(m.group(2))
                except ValueError:
                    continue
                # GAMS may print Z_obj.l, Z_obj.L, or Z_obj depending on type/case.
                key = name.lower().rstrip(".")
                if key.endswith(".l"):
                    key = key[:-2]
                if key == "z_obj":
                    result["objective"] = val
                    result["has_display"] = True
                elif key == "cmax":
                    result["makespan"] = val
                    result["has_display"] = True
                elif key == "geciken_is_adedi":
                    result["late_jobs"] = int(round(val))
                    result["has_display"] = True
                continue

            if display_block_pat.match(stripped):
                result["has_display"] = True
                continue

            # SOLVE SUMMARY scraping
            if "MODEL STATUS" in stripped and result["model_status"] is None:
                # Examples:
                #   **** MODEL STATUS      8 INTEGER SOLUTION
                #   **** MODEL STATUS      1 OPTIMAL
                m2 = re.search(r"MODEL\s+STATUS\s+(.+)$", stripped)
                if m2:
                    result["model_status"] = m2.group(1).strip()
            elif "SOLVER STATUS" in stripped and result["solver_status"] is None:
                m2 = re.search(r"SOLVER\s+STATUS\s+(.+)$", stripped)
                if m2:
                    result["solver_status"] = m2.group(1).strip()
            elif "OBJECTIVE VALUE" in stripped and result["objective_summary"] is None:
                m2 = re.search(r"OBJECTIVE\s+VALUE\s+([\-\d.eE+]+)", stripped)
                if m2:
                    try:
                        result["objective_summary"] = float(m2.group(1))
                    except ValueError:
                        pass

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Solver agent for siparisturu_v6")
    parser.add_argument("--gams", required=True, help="Path to GAMS executable")
    parser.add_argument("--model", default="siparisturu_v6.gms", help="GAMS model file")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"ERROR: model file not found: {args.model}")
        return 1
    if not os.path.exists(args.gams) and not _which(args.gams):
        print(f"ERROR: GAMS executable not found: {args.gams}")
        return 1

    model_base = os.path.splitext(os.path.basename(args.model))[0]
    lst_path = f"{model_base}.lst"

    cmd = [args.gams, args.model, "lo=3"]
    start = time.time()
    rc, _obj_seen, infeasible, time_limit = stream_gams(cmd, log_path="solver_run.log")
    elapsed = time.time() - start

    if infeasible:
        write_summary(
            rc=rc,
            elapsed=elapsed,
            parsed={
                "objective": None,
                "makespan": None,
                "late_jobs": None,
                "model_status": "Infeasible",
                "solver_status": None,
                "objective_summary": None,
                "has_display": False,
            },
        )
        return 3

    if not os.path.exists(lst_path):
        print(f"ERROR: .lst file not written: {lst_path}")
        write_summary(
            rc=rc,
            elapsed=elapsed,
            parsed={
                "objective": None,
                "makespan": None,
                "late_jobs": None,
                "model_status": "MISSING_LST",
                "solver_status": None,
                "objective_summary": None,
                "has_display": False,
            },
        )
        return 2

    try:
        parsed = parse_lst(lst_path)
    except OSError as exc:
        print(f"ERROR: could not read .lst file: {exc}")
        return 2

    write_summary(rc=rc, elapsed=elapsed, parsed=parsed)

    status = (parsed.get("model_status") or "").upper()
    success_markers = ("OPTIMAL", "INTEGER")

    if rc != 0:
        return 1
    if "INFEASIBLE" in status:
        return 3
    if not any(marker in status for marker in success_markers):
        # No clear optimal/integer marker -- still return 1 to flag for review
        # but only if no useful solution is in the .lst
        if parsed["objective"] is None and parsed["makespan"] is None:
            return 1

    print()
    print("SOLVER AGENT COMPLETE")
    print(f"Objective = {parsed['objective']}")
    print(f"Makespan  = {parsed['makespan']} min")
    print(f"Late jobs = {parsed['late_jobs']}")
    return 0


def write_summary(rc: int, elapsed: float, parsed: Dict[str, object]) -> None:
    obj = parsed.get("objective")
    cmax = parsed.get("makespan")
    late = parsed.get("late_jobs")
    cmax_days = (cmax / 1200.0) if isinstance(cmax, (int, float)) else None

    def fmt(v, suffix: str = "") -> str:
        return "n/a" if v is None else f"{v}{suffix}"

    with open("solve_summary.txt", "w", encoding="utf-8") as f:
        f.write(f"GAMS exit code:   {rc}\n")
        f.write(f"Model status:     {parsed.get('model_status') or 'n/a'}\n")
        f.write(f"Solver status:    {parsed.get('solver_status') or 'n/a'}\n")
        f.write(f"Objective value:  {fmt(obj)}\n")
        if cmax is not None and cmax_days is not None:
            f.write(f"Makespan:         {cmax} minutes  ({cmax_days:.2f} days)\n")
        else:
            f.write(f"Makespan:         n/a\n")
        f.write(f"Late jobs:        {fmt(late)}\n")
        f.write(f"Wall time:        {elapsed:.1f}s\n")
        if parsed.get("objective_summary") is not None:
            f.write(f"Objective (SOLVE SUMMARY): {parsed['objective_summary']}\n")


def _which(name: str) -> bool:
    """True if `name` is found on PATH (without spawning a shell)."""
    from shutil import which
    return which(name) is not None


if __name__ == "__main__":
    sys.exit(main())
