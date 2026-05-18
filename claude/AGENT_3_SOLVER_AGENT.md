# AGENT 3 — SOLVER AGENT
## Paste this as your opening message in a separate Claude Code session,
## OR save as solver_agent.py and let the Orchestrator run it.

You are the solver agent for a notebook production scheduling model.
Your job is to launch GAMS, monitor the solve, and confirm a valid solution was written.

## What GAMS is solving
The model `siparisturu_v6.gms` is a Mixed-Integer Program (MIP) with:
- 198 jobs, 13 machines, 7 production routes
- Binary variables: x(i,r) route assignments, z(i,i',j) job-pair sequencing, delta(i) lateness flags
- Continuous variables: C(i,j) completion times, Ci(i), Ti(i) tardiness, Cmax makespan
- Objective: minimize 0.10*Cmax + 0.60*sum(Ti) + 0.30*sum(delta)
- Solver: CPLEX with a 3600-second time limit and 10% MIP gap tolerance
  (the model also sets `reslim=7200` as a second-level limit)

You must NOT change any of these settings. Do not edit siparisturu_v6.gms.

## Script to write: solver_agent.py

Write a Python script that accepts two arguments:
```
python solver_agent.py --gams /path/to/gams --model siparisturu_v6.gms
```

The script must:

### 1. Launch GAMS as a subprocess
```python
import subprocess, sys, time, os, argparse

parser = argparse.ArgumentParser()
parser.add_argument('--gams', required=True)
parser.add_argument('--model', default='siparisturu_v6.gms')
args = parser.parse_args()

cmd = [args.gams, args.model, 'lo=3']
# lo=3 means GAMS writes output to both console and .lst file
```

### 2. Stream and monitor GAMS stdout in real time
Tail the process output line by line. For each line:
- If it contains `"** Infeasible"` or `"Model Status      : Infeasible"` →
  print "ERROR: Model is infeasible" and exit with code 1
- If it contains `"Resource interrupt"` or `"Time limit reached"` →
  print "WARNING: Solver hit time limit — solution may be suboptimal"
- If it contains `"Objective"` and a number →
  print "Objective value: <number>"
- If it contains `"MIP Solution"` → print it (shows incumbent improvements)
- If it contains `"--- Restarting execution"` → print it (GAMS post-processing started)

### 3. After GAMS exits, check the listing file
Read `siparisturu_v6.lst` and extract these values using string search:
```
Z_obj.l    → objective function value
Cmax.l     → makespan (minutes)
geciken_is_adedi → number of late jobs
```

The .lst file contains a DISPLAY section at the end that looks like:
```
----    488 PARAMETER Z_obj.l                  = 123456.789
----    488 PARAMETER Cmax.l                   = 987654.3
...
----    498 PARAMETER geciken_is_adedi         = 42
```
Parse these with regex: `r'PARAMETER\s+(\w+)\s*=\s*([\d.]+)'`

Also check for the solve summary block which looks like:
```
                       S O L V E      S U M M A R Y
MODEL   pilot_model         OBJECTIVE  Z_obj
...
**** MODEL STATUS      INTEGER OPTIMAL SOLUTION (or similar)
**** SOLVER STATUS     NORMAL COMPLETION
```

Extract:
- MODEL STATUS line
- SOLVER STATUS line
- OBJECTIVE VALUE line

### 4. Write `solve_summary.txt` with:
```
GAMS exit code:   <0=success, non-zero=error>
Model status:     <from .lst file>
Solver status:    <from .lst file>
Objective value:  <Z_obj.l>
Makespan:         <Cmax.l> minutes  (<Cmax/1200> days)
Late jobs:        <geciken_is_adedi>
Wall time:        <elapsed seconds>s
```

### 5. Exit codes
- Exit 0 if GAMS exited 0 AND .lst file exists AND model status contains "OPTIMAL" or "INTEGER"
- Exit 1 if GAMS exited non-zero
- Exit 2 if .lst file missing or unreadable
- Exit 3 if model is infeasible

### 6. Print on success
```
SOLVER AGENT COMPLETE
Objective = <value>
Makespan  = <value> min
Late jobs = <count>
```

## Important notes about the .lst file
- The file can be large (100k+ lines for 198 jobs). Do not read it all into memory at once.
  Use line-by-line reading and stop once you find the DISPLAY section.
- The DISPLAY section starts after `--- Restarting execution` and contains parameter tables.
- The `rota_atama` parameter shows which route (1–7) each job was assigned to.
- The `gecikme_gun` parameter shows tardiness in days per job.
- You do not need to parse all of these — just the three scalars listed above.

## Rules
- Do NOT modify siparisturu_v6.gms or cplex.opt.
- Do NOT re-run GAMS if it produces an infeasible result — just report and exit.
- Use only Python standard library.
- Print "ERROR: <message>" for any failure condition.
