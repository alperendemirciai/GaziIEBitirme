# Notebook Scheduling Pipeline — Claude Code Quick Start

## File structure expected in your project folder
```
your_project/
├── siparisturu_v6.gms      ← your existing GAMS model (do not rename)
├── cplex.opt               ← auto-created by GAMS on first run
├── data_agent.py           ← created by Agent 2
├── solver_agent.py         ← created by Agent 3
├── analysis_agent.py       ← created by Agent 4
└── outputs/
    ├── data_validation_report.txt
    ├── orders_summary.txt
    ├── solve_summary.txt
    └── schedule_output.xlsx
```

## How to use these prompts

### Option A — Three separate Claude Code sessions (recommended)
Run each agent in its own `claude` session in order:

```bash
# Session 1: build and run the data agent
claude < AGENT_2_DATA_AGENT.md

# Session 2: build and run the solver agent
claude < AGENT_3_SOLVER_AGENT.md

# Session 3: build and run the analysis agent
claude < AGENT_4_ANALYSIS_AGENT.md
```

### Option B — Single orchestrated session
Run the orchestrator, which calls the three scripts automatically:
```bash
claude < AGENT_1_ORCHESTRATOR.md
```
The orchestrator assumes the three Python scripts already exist (created by Options A above).
Run Option A first, then Option B for orchestrated re-runs.

## Two things you MUST change in AGENT_1_ORCHESTRATOR.md before running:
```
WORKDIR=/path/to/your/project
GAMS=/path/to/gams
```
Find your GAMS executable path with: `which gams` (Linux/Mac) or `where gams` (Windows)

## Dependencies
Only `openpyxl` needs to be installed. Everything else uses the Python standard library.
```bash
pip install openpyxl
```

## What each agent actually does

| Agent | Input | Output | Time |
|---|---|---|---|
| Data Agent | siparisturu_v6.gms | data_validation_report.txt, orders_summary.txt | ~5 seconds |
| Solver Agent | siparisturu_v6.gms | siparisturu_v6.lst, solve_summary.txt | 1–2 hours (CPLEX) |
| Analysis Agent | siparisturu_v6.lst + .gms | schedule_output.xlsx | ~30 seconds |

## The Excel output (schedule_output.xlsx) has 3 sheets:
- **Job Schedule**: all 198 jobs with route, completion time, tardiness, ON TIME/LATE status
- **Machine Load**: utilization % for all 13 machines
- **Summary**: KPI block — objective value, makespan, on-time rate, worst late job

## Critical: delivery dates in the model
The .gms file has delivery dates hardcoded as `jdate(YYYY,MM,DD)`.
The due date computation is: `d(i) = (delivery_date - today) * 1200 minutes`.
If you run the model weeks from now, some delivery dates may have already passed,
making d(i) negative — the data agent will catch and report this as a critical error.
Update the `$eval TESLIM_I*` lines in the .gms file if dates become stale.
