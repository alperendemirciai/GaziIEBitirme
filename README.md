# Notebook Production Scheduling Pipeline

A four-agent automation pipeline for the GAMS model `siparisturu_v6.gms`.
It validates the input data, launches the solver, and turns the GAMS solution
into a human-readable Excel report.

> **If you have GAMS installed and just want to run it,** open
> [`TUTORIAL.md`](TUTORIAL.md). This file is the reference / "what is it?"
> document. The tutorial has the step-by-step copy-paste instructions.

---

## 1. What the pipeline does

The pipeline solves a **198-job notebook (defter) production scheduling
problem** with 13 machines, 7 production routes, sequence-dependent setups,
and tardiness-aware objective. The model itself lives in
`siparisturu_v6.gms`. This pipeline wraps four automation steps around it:

```
              ┌────────────────────────┐
              │  Agent 1: orchestrator │
              │  (orchestrator.py)     │
              └───────────┬────────────┘
                          │ runs in sequence, stops on first failure
       ┌──────────────────┼────────────────────┐
       ▼                  ▼                    ▼
┌──────────────┐  ┌──────────────┐    ┌──────────────────┐
│  Agent 2     │  │  Agent 3     │    │  Agent 4         │
│  Data Agent  │→ │  Solver      │ →  │  Analysis Agent  │
│              │  │  Agent       │    │                  │
│ Validates    │  │ Runs GAMS,   │    │ Parses .lst,     │
│ the .gms     │  │ monitors     │    │ writes Excel     │
│ data         │  │ stdout       │    │ schedule report  │
└──────────────┘  └──────────────┘    └──────────────────┘
   data_agent.py    solver_agent.py     analysis_agent.py
```

| Agent | Script | Reads | Writes |
|---|---|---|---|
| 1 | `orchestrator.py` | – | console summary block |
| 2 | `data_agent.py` | `siparisturu_v6.gms` | `data_validation_report.txt`, `orders_summary.txt` |
| 3 | `solver_agent.py` | `siparisturu_v6.gms` | `siparisturu_v6.lst`, `solve_summary.txt`, `solver_run.log` |
| 4 | `analysis_agent.py` | `siparisturu_v6.lst`, `siparisturu_v6.gms` | `schedule_output.xlsx` |

Total time on a typical run: **a few seconds for Agents 2 & 4**, **1–2 hours
for Agent 3** (CPLEX has a 3600-second per-iteration time limit and a 7200-
second wall limit set inside the `.gms` file).

---

## 2. Project structure (after running)

```
GaziIEBitirme/
├── README.md                        ← this file
├── TUTORIAL.md                      ← step-by-step how-to run
├── siparisturu_v6.gms               ← THE GAMS model (input)
│
├── data_agent.py                    ← Agent 2
├── solver_agent.py                  ← Agent 3
├── analysis_agent.py                ← Agent 4
├── orchestrator.py                  ← Agent 1
├── test_analysis.py                 ← optional helper (tests Agent 4 alone)
│
├── data_validation_report.txt       ← (produced by Agent 2)
├── orders_summary.txt               ← (produced by Agent 2)
├── siparisturu_v6.lst               ← (produced by GAMS, read by Agent 4)
├── solve_summary.txt                ← (produced by Agent 3)
├── solver_run.log                   ← (produced by Agent 3 — full GAMS stdout)
├── schedule_output.xlsx             ← (produced by Agent 4 — FINAL REPORT)
│
├── claude/                          ← agent prompt files (reference)
└── assets/                          ← original course material
```

---

## 3. The Excel report — `schedule_output.xlsx`

The final deliverable. It has **3 sheets**:

### Sheet 1: "Job Schedule"
One row per job (198 rows), sorted with worst-late jobs at the top.

Columns:
`job_id, job_name, customer, binding_type, ruling, route_num, route_desc,
qty, due_minutes, due_days, completion_min, completion_days,
tardiness_min, tardiness_days, status`

The `status` column is colour-coded:
- 🟢 **ON TIME** — `tardiness_min == 0`
- 🔴 **LATE** — `tardiness_min > 0`
- ⚪ **UNSCHEDULED** — `completion_min == 0`

Rows with **more than one day late** are also rendered in **bold**.

### Sheet 2: "Machine Load"
| Machine | Load (min) | Load (days) | Capacity (min/day) | Utilization % |

Sorted by utilization descending. Utilization is computed as
`load_minutes / (capacity * makespan_in_days) * 100`.

### Sheet 3: "Summary"
KPI block: total jobs, on-time vs late counts, on-time rate, the GAMS
objective value, makespan in minutes and days, the most-loaded machine,
and the worst late job.

---

## 4. ⚠ IMPORTANT — known data issues in `siparisturu_v6.gms`

The data agent (Agent 2) **found two real bugs in the GAMS data file** that
will cause the pipeline to halt at Task 1 until they are fixed. They look
like typing mistakes — fixing them takes 30 seconds.

### Bug 1 — Two jobs missing from any ruling-type set

Jobs `I96` and `I98` are *not* listed in `i_cizgili`, `i_kareli`, or
`i_duz`. Their names end with `Çizgili`, so they should be in `i_cizgili`.

### Bug 2 — Two jobs listed in two ruling sets at once

Jobs `I196` and `I198` appear in **both** `i_cizgili` **and** `i_duz`. Their
names end with `Düz`, so they should be in `i_duz` only.

### How to fix both at once

Open `siparisturu_v6.gms`, find the `i_cizgili(i)` block (around line 359),
and replace this line:

```gams
             I92, I94, I196, I198, I100, I102, I111,
```

with this corrected line:

```gams
             I92, I94, I96, I98, I100, I102, I111,
```

That single change removes `I196` and `I198` from `i_cizgili` (Bug 2) and
adds `I96` and `I98` (Bug 1). Re-run `python3 data_agent.py` and
`OVERALL: PASS` should appear.

> The pipeline does **not** modify the .gms file automatically — by design.
> The .gms file is owned by the solver agent, and silent edits would mask
> real data problems. Make the fix manually.

---

## 5. Other things the data agent checks

- All 198 jobs (`I01`–`I198`) are declared in `Set i`
- Every job has `qty > 0`
- Every delivery date is in the future (`d(i) > 0`)
- No job appears in more than one *product type* set
- Every job appears in at least one product type set
- A rough capacity feasibility estimate per machine (informational warning)

When the file passes all checks, the report ends with `OVERALL: PASS`.

---

## 6. Dependencies

- **Python 3.7 or newer**
- **`openpyxl`** (only needed by Agent 4) — install with `pip install openpyxl`
- **GAMS** with **CPLEX** (only needed by Agent 3) — installed separately

Everything else uses the Python standard library.

---

## 7. Files in `claude/`

These are the original prompt files that describe each agent's contract.
They are reference material — they document *why* each script does what it
does. You don't need to modify them.

| File | Describes |
|---|---|
| `AGENT_1_ORCHESTRATOR.md` | The pipeline runner contract |
| `AGENT_2_DATA_AGENT.md`   | What the data validator must check |
| `AGENT_3_SOLVER_AGENT.md` | The GAMS-monitoring contract |
| `AGENT_4_ANALYSIS_AGENT.md` | The Excel-report contract |
| `QUICKSTART_README.md`    | Original quick-start guide |

---

## 8. Where to start

➡ **Open [`TUTORIAL.md`](TUTORIAL.md) next.** It walks through running the
pipeline end-to-end on a machine with GAMS installed.
