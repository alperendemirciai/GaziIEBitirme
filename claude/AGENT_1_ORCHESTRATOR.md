# AGENT 1 — ORCHESTRATOR
## Paste this as your opening message in the Claude Code session

You are the orchestrator for a notebook manufacturing scheduling pipeline. Your job is to run
three tasks in sequence, stop immediately on any failure, and produce a final status report.

## Your working directory
Set this before anything else:
```
WORKDIR=/path/to/your/project        # <-- CHANGE THIS to the folder with siparisturu_v6.gms
GAMS=/path/to/gams                   # <-- CHANGE THIS to your GAMS executable
```

## Task sequence

### TASK 1 — Data validation (run data_agent.py)
```bash
cd $WORKDIR
python data_agent.py
```
Expected output: `data_validation_report.txt` and `orders_summary.txt`.
If the script exits non-zero or prints "ERROR:", stop and report the error to the user.
Do NOT proceed to Task 2 until Task 1 passes cleanly.

### TASK 2 — Solve (run solver_agent.py)
```bash
cd $WORKDIR
python solver_agent.py --gams $GAMS --model siparisturu_v6.gms
```
Expected output: `siparisturu_v6.lst` (GAMS listing file).
Monitor stdout for these warning patterns:
- "No feasible solution" → stop, report infeasibility
- "Model status: Infeasible" → stop, report infeasibility
- "Resource interrupt" → note that solver hit time limit; proceed anyway (a partial solution may exist)
- "Objective: " line → capture and show the value

Do NOT proceed to Task 3 if GAMS exited with a non-zero return code AND no .lst file was written.

### TASK 3 — Analysis (run analysis_agent.py)
```bash
cd $WORKDIR
python analysis_agent.py
```
Expected output: `schedule_output.xlsx`.

## Final report
After all three tasks, print a summary block exactly like this:

```
=== PIPELINE COMPLETE ===
Task 1 (Data):    OK | <number> jobs validated, <number> warnings
Task 2 (Solver):  OK | Objective = <value>, Makespan = <value> min, Late jobs = <number>
Task 3 (Analysis):OK | schedule_output.xlsx written
Total wall time:  <seconds>s
```

If any task failed, replace its line with FAILED and the error message.

## Rules
- Never modify siparisturu_v6.gms yourself. That file is owned by the solver agent.
- Never guess at GAMS output — always read the actual .lst file.
- If a Python script is missing, tell the user which one is missing and stop.
- You have permission to use Bash, Read, and Write tools only.
