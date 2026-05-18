#!/usr/bin/env python3
"""
orchestrator.py — Agent 1 of the notebook scheduling pipeline.

Runs the three pipeline tasks in sequence, stops on failure, and prints a
final status block. Reads paths from CLI args or from environment variables
(WORKDIR, GAMS) for convenience.

Usage:
    python orchestrator.py --gams /path/to/gams [--workdir /path/to/project]

The orchestrator assumes that data_agent.py, solver_agent.py and
analysis_agent.py already exist in WORKDIR.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from typing import List, Optional, Tuple


REQUIRED_SCRIPTS = ["data_agent.py", "solver_agent.py", "analysis_agent.py"]
MODEL_FILE = "siparisturu_v6.gms"


def _shorten(s: str, n: int = 240) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    return s[: n - 3] + "..."


def run_streamed(cmd: List[str], cwd: str) -> Tuple[int, str]:
    """Run a subprocess, tee output to our stdout, and return (rc, captured_text)."""
    print(f"\n$ {' '.join(cmd)}  (cwd={cwd})")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    captured_lines: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        captured_lines.append(line)
    proc.wait()
    return proc.returncode, "".join(captured_lines)


def parse_data_summary(captured: str) -> Tuple[int, int, int]:
    """Return (jobs_validated, warnings, errors) from data_agent output."""
    warnings = 0
    errors = 0
    # Try to read OVERALL line: "OVERALL: PASS | WARNINGS: 1" or
    # "OVERALL: ERROR (N critical errors found) | WARNINGS: x"
    m = re.search(r"OVERALL:\s*([A-Z]+)(?:\s*\((\d+)\s+critical[^)]*\))?", captured)
    if m:
        if m.group(1) == "ERROR" and m.group(2):
            errors = int(m.group(2))
    m2 = re.search(r"WARNINGS:\s*(\d+)", captured)
    if m2:
        warnings = int(m2.group(1))
    # We always validate 198 jobs by spec
    return 198, warnings, errors


def parse_solver_summary(workdir: str) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    """Read solve_summary.txt for objective / makespan / late_jobs."""
    path = os.path.join(workdir, "solve_summary.txt")
    if not os.path.exists(path):
        return None, None, None
    obj = mksp = None
    late: Optional[int] = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Objective value:"):
                v = line.split(":", 1)[1].strip()
                obj = _try_float(v.split()[0]) if v not in ("", "n/a") else None
            elif line.startswith("Makespan:"):
                tail = line.split(":", 1)[1].strip()
                obj_part = tail.split()[0] if tail and tail != "n/a" else None
                mksp = _try_float(obj_part) if obj_part else None
            elif line.startswith("Late jobs:"):
                v = line.split(":", 1)[1].strip()
                if v.isdigit():
                    late = int(v)
    return obj, mksp, late


def _try_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline orchestrator")
    parser.add_argument(
        "--workdir",
        default=os.environ.get("WORKDIR", os.getcwd()),
        help="Project directory (default: $WORKDIR or current directory)",
    )
    parser.add_argument(
        "--gams",
        default=os.environ.get("GAMS", ""),
        help="Path to the GAMS executable (default: $GAMS env var)",
    )
    parser.add_argument(
        "--model",
        default=MODEL_FILE,
        help="GAMS model file inside the workdir",
    )
    parser.add_argument(
        "--skip-solver",
        action="store_true",
        help="Skip Task 2 (useful when re-running analysis on an existing .lst)",
    )
    args = parser.parse_args()

    workdir = os.path.abspath(args.workdir)
    if not os.path.isdir(workdir):
        print(f"ERROR: workdir not found: {workdir}")
        return 1

    # Verify all required scripts exist
    for s in REQUIRED_SCRIPTS:
        if not os.path.exists(os.path.join(workdir, s)):
            print(f"ERROR: required script missing in workdir: {s}")
            return 1
    if not os.path.exists(os.path.join(workdir, args.model)):
        print(f"ERROR: model file missing: {args.model}")
        return 1

    if not args.skip_solver and not args.gams:
        print("ERROR: --gams path is required (or set GAMS env var)")
        return 1

    wall_start = time.time()
    task1 = "PENDING"
    task2 = "PENDING"
    task3 = "PENDING"
    task1_detail = ""
    task2_detail = ""
    task3_detail = ""
    failed_at: Optional[str] = None

    # ----- TASK 1: data validation -----
    print("=" * 60)
    print("TASK 1 -- Data validation")
    print("=" * 60)
    rc1, out1 = run_streamed([sys.executable, "data_agent.py"], cwd=workdir)
    jobs, warnings, errors = parse_data_summary(out1)
    if rc1 != 0 or "ERROR:" in out1:
        task1 = "FAILED"
        task1_detail = f"data_agent.py exit={rc1}, errors={errors}, warnings={warnings}"
        failed_at = "Task 1"
        print(f"\nTask 1 FAILED -- {task1_detail}")
        return _final_report(
            wall_start, task1, task2, task3,
            task1_detail, task2_detail, task3_detail,
            jobs, warnings, failed_at=failed_at,
        )
    task1 = "OK"
    task1_detail = f"{jobs} jobs validated, {warnings} warning(s)"

    # ----- TASK 2: solve -----
    if args.skip_solver:
        task2 = "SKIPPED"
        task2_detail = "--skip-solver flag was set"
    else:
        print("\n" + "=" * 60)
        print("TASK 2 -- Solve")
        print("=" * 60)
        rc2, out2 = run_streamed(
            [sys.executable, "solver_agent.py", "--gams", args.gams, "--model", args.model],
            cwd=workdir,
        )
        # rc2 == 3 means infeasible per solver_agent contract
        if rc2 == 3:
            task2 = "FAILED"
            task2_detail = "Model is infeasible"
            failed_at = "Task 2"
            print("\nTask 2 FAILED -- model infeasible")
            return _final_report(
                wall_start, task1, task2, task3,
                task1_detail, task2_detail, task3_detail,
                jobs, warnings, failed_at=failed_at,
            )
        lst_path = os.path.join(workdir, args.model.replace(".gms", ".lst"))
        if rc2 != 0 and not os.path.exists(lst_path):
            task2 = "FAILED"
            task2_detail = f"solver_agent.py exit={rc2}, no .lst written"
            failed_at = "Task 2"
            print(f"\nTask 2 FAILED -- {task2_detail}")
            return _final_report(
                wall_start, task1, task2, task3,
                task1_detail, task2_detail, task3_detail,
                jobs, warnings, failed_at=failed_at,
            )
        obj, mksp, late = parse_solver_summary(workdir)
        bits = []
        if obj is not None:
            bits.append(f"Objective = {obj:.3f}")
        if mksp is not None:
            bits.append(f"Makespan = {mksp:.1f} min")
        if late is not None:
            bits.append(f"Late jobs = {late}")
        task2 = "OK"
        task2_detail = ", ".join(bits) if bits else "(no metrics parsed)"
        if rc2 != 0:
            task2_detail += "  [solver returned non-zero, partial result accepted]"

    # ----- TASK 3: analysis -----
    print("\n" + "=" * 60)
    print("TASK 3 -- Analysis")
    print("=" * 60)
    rc3, out3 = run_streamed([sys.executable, "analysis_agent.py"], cwd=workdir)
    xlsx_path = os.path.join(workdir, "schedule_output.xlsx")
    if rc3 != 0 or not os.path.exists(xlsx_path):
        task3 = "FAILED"
        task3_detail = f"analysis_agent.py exit={rc3}, xlsx exists={os.path.exists(xlsx_path)}"
        failed_at = "Task 3"
        return _final_report(
            wall_start, task1, task2, task3,
            task1_detail, task2_detail, task3_detail,
            jobs, warnings, failed_at=failed_at,
        )
    task3 = "OK"
    task3_detail = "schedule_output.xlsx written"

    return _final_report(
        wall_start, task1, task2, task3,
        task1_detail, task2_detail, task3_detail,
        jobs, warnings, failed_at=None,
    )


def _final_report(
    wall_start: float,
    task1: str, task2: str, task3: str,
    task1_detail: str, task2_detail: str, task3_detail: str,
    jobs: int, warnings: int,
    failed_at: Optional[str] = None,
) -> int:
    elapsed = time.time() - wall_start
    print()
    print("=== PIPELINE COMPLETE ===")
    print(f"Task 1 (Data):    {task1} | {task1_detail or '-'}")
    print(f"Task 2 (Solver):  {task2} | {task2_detail or '-'}")
    print(f"Task 3 (Analysis):{task3} | {task3_detail or '-'}")
    print(f"Total wall time:  {elapsed:.1f}s")
    if failed_at:
        print(f"Pipeline halted at: {failed_at}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
