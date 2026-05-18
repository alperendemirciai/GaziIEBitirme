# Tutorial — How to Run the Pipeline

**Audience:** someone who knows GAMS but is not a Python programmer.
**Goal:** by the end of this tutorial you will have produced
`schedule_output.xlsx`, a 3-sheet Excel file with the optimised schedule for
all 198 notebook orders.

Estimated time: **15 minutes of setup + 1 to 2 hours for the GAMS solve**.

> Throughout this tutorial, lines that start with `$` are commands you type
> in the terminal. Type only what comes *after* the `$`.

---

## Part 0 — What you need before you start

You need **three** things on the computer:

1. **Python 3** (any version 3.7 or newer).
   Check by opening a terminal and typing:
   ```
   $ python3 --version
   ```
   You should see something like `Python 3.11.5`. If you get
   "command not found", install Python from <https://www.python.org/downloads/>.

2. **GAMS with CPLEX**. You must already have GAMS installed (because you
   wrote the model in GAMS). Just confirm you know where it is:
   - **Windows:** the GAMS executable is usually
     `C:\GAMS\44\gams.exe` (the version number may differ).
   - **macOS:** usually `/Applications/GAMS44.4/gams` or
     `/Library/Frameworks/GAMS.framework/Resources/gams`.
   - **Linux:** type `which gams` and copy whatever path it shows.

   You only need the **path to the gams executable**. Write it down.

3. **The project folder** that has all these files in it. The folder must
   contain `siparisturu_v6.gms` and the four Python scripts:
   `data_agent.py`, `solver_agent.py`, `analysis_agent.py`,
   `orchestrator.py`.

---

## Part 1 — One-time setup

### Step 1.1 — Open a terminal in the project folder

- **Windows:** in File Explorer, navigate to the folder, then in the address
  bar type `cmd` and press Enter. A black window opens.
- **macOS:** right-click the folder → Services → "New Terminal at Folder".
- **Linux:** right-click in the folder → "Open in Terminal".

To check you are in the right place, type:

```
$ ls
```
(or `dir` on Windows). You should see `siparisturu_v6.gms` and the four
`.py` files in the listing.

### Step 1.2 — Install the one Python library we need

The analysis agent uses a library called **openpyxl** to write Excel files.
Install it once with:

```
$ pip install openpyxl
```

If `pip` is not found, try `pip3 install openpyxl` or
`python3 -m pip install openpyxl`.

You should see `Successfully installed openpyxl-...` near the end.

---

## Part 2 — Fix the two data bugs in `siparisturu_v6.gms`

The data agent found two real bugs in the GAMS data file. Until they're
fixed, the pipeline will halt at Task 1. The fix is **a single line edit**.

### Step 2.1 — Open `siparisturu_v6.gms` in any text editor

Notepad, VS Code, GAMSStudio, TextEdit — anything works. Search (Ctrl+F)
for `i_cizgili`.

You will see a block that looks like this (around line 359):

```gams
Set
  i_cizgili(i) "Cizgili kagitli isler" /
             I01, I03, I05, I10, I12, I14, I16, I18
             I20, I22, I24, I26, I33, I35, I36, I39
             I40, I42, I43, I45, I50, I52, I54, I56
             I58, I60, I64, I66, I68, I70, I72, I74
             I76, I78, I80, I82, I84, I86, I88, I90
             I92, I94, I196, I198, I100, I102, I111,    ← THE BUGGY LINE
             I115, I118, I121, I124, I127, I130 /
```

### Step 2.2 — Change one line

Replace this line:

```gams
             I92, I94, I196, I198, I100, I102, I111,
```

with this line (change `I196` → `I96` and `I198` → `I98`):

```gams
             I92, I94, I96, I98, I100, I102, I111,
```

### Step 2.3 — Save the file

That's it. This single change fixes both bugs at once:
- `I96` and `I98` (which end in `Çizgili`) are now correctly in `i_cizgili`.
- `I196` and `I198` (which end in `Düz`) are no longer wrongly in
  `i_cizgili` — they stay correctly in `i_duz` only.

---

## Part 3 — Run the pipeline

You have two choices: **run all three agents at once with the orchestrator**
(easier), or **run each agent one by one** (lets you see each step
separately).

### Option A — Run everything with the orchestrator (recommended)

Type this in the terminal, **replacing `PATH_TO_GAMS` with your actual GAMS
path**:

```
$ python3 orchestrator.py --gams PATH_TO_GAMS
```

Examples for each operating system:

```
# Windows
$ python orchestrator.py --gams "C:\GAMS\44\gams.exe"

# macOS
$ python3 orchestrator.py --gams "/Applications/GAMS44.4/gams"

# Linux
$ python3 orchestrator.py --gams /opt/gams/gams
```

The orchestrator will:
1. Run **Agent 2** (data validation) → ~5 seconds
2. Run **Agent 3** (GAMS solve) → **1 to 2 hours, be patient**
3. Run **Agent 4** (Excel report) → ~5 seconds

While Agent 3 is running, you will see CPLEX progress lines stream past.
This is normal. The GAMS solver tries to find better and better solutions
until it either proves the gap is below 5 %, or the time limit is hit.
The most recent objective value is printed each time CPLEX finds an
improvement.

When it's done, you will see a block like:

```
=== PIPELINE COMPLETE ===
Task 1 (Data):    OK | 198 jobs validated, 1 warning(s)
Task 2 (Solver):  OK | Objective = 123456.789, Makespan = 45000.0 min, Late jobs = 7
Task 3 (Analysis):OK | schedule_output.xlsx written
Total wall time:  4231.6s
```

➡ The final report is `schedule_output.xlsx`. **Open it in Excel.**

### Option B — Run each agent separately

If you prefer to see each step on its own (for example, to inspect the
validation report before running the long solve), run the four scripts in
order:

```
$ python3 data_agent.py
```
Look at `data_validation_report.txt` and `orders_summary.txt`. The last
line of the report should say `OVERALL: PASS`. If it says `OVERALL: ERROR`,
re-check Part 2.

```
$ python3 solver_agent.py --gams PATH_TO_GAMS --model siparisturu_v6.gms
```
This is the long step. Output goes to `solver_run.log` and
`solve_summary.txt`. The GAMS listing is `siparisturu_v6.lst`.

```
$ python3 analysis_agent.py
```
This reads `siparisturu_v6.lst` and writes `schedule_output.xlsx`. Fast.

---

## Part 4 — Reading the outputs

### `data_validation_report.txt`
Plain-text report of each check (PASS / WARNING / ERROR) plus an
`OVERALL:` verdict on the last line.

### `orders_summary.txt`
Descriptive statistics about the 198 jobs: counts per customer, binding
type, delivery date, top 5 jobs by quantity, and the earliest delivery
date.

### `solve_summary.txt`
Six lines summarising the GAMS solve:
- GAMS exit code
- Model status (e.g. `8 INTEGER SOLUTION` or `1 OPTIMAL`)
- Solver status (e.g. `1 NORMAL COMPLETION`)
- Objective value
- Makespan in minutes and days
- Number of late jobs

### `siparisturu_v6.lst`
The full GAMS listing file. Huge (often 100k+ lines). You don't normally
need to open it — Agent 4 has already extracted what you need into the
Excel file. Keep it as evidence of the solve.

### `solver_run.log`
A tee of everything GAMS printed to stdout during the run. Useful for
debugging if Agent 3 reports a problem.

### `schedule_output.xlsx` ⭐ THE MAIN DELIVERABLE
Open it in Excel. Three sheets:
- **Job Schedule** — every job with its route, completion time, and
  on-time/late status.
- **Machine Load** — utilization per machine.
- **Summary** — KPI block.

---

## Part 5 — Troubleshooting

> If your error is not listed here, scroll down to Part 6 and copy-paste
> one of the AI prompt templates.

### "python3: command not found" (or "'python' is not recognized")
Python is not installed, or not on your PATH. Install it from
<https://www.python.org/downloads/> and **tick the "Add Python to PATH" box
during installation on Windows**.

### "ERROR: openpyxl not installed -- run: pip install openpyxl"
You skipped Step 1.2. Run `pip install openpyxl` and try again.

### "ERROR: model file not found: siparisturu_v6.gms"
Your terminal is in the wrong folder. `cd` into the folder that contains
the `.gms` file, then run the command again.

### "ERROR: GAMS executable not found"
The `--gams` path you gave the orchestrator is wrong. Double-check the
path. On Windows the path probably needs **double quotes** around it
because it contains spaces (e.g. `--gams "C:\Program Files\GAMS\gams.exe"`).

### "OVERALL: ERROR (2 critical errors found)"
You skipped Part 2. Go back and apply the one-line fix to
`siparisturu_v6.gms`.

### Solver runs but Task 3 says ".lst contains no DISPLAY section"
Something went wrong during the solve before GAMS reached the `Display`
statement. Open `solver_run.log` and search for "Infeasible" or "Error".

### "WARNING: Solver hit time limit -- solution may be suboptimal"
This is not an error. CPLEX hit the 3600-second per-iteration or
7200-second wall limit before proving optimality. The pipeline still
produces a valid (but possibly non-optimal) schedule. Look at the model
status line in `solve_summary.txt`: `INTEGER SOLUTION` means a feasible
schedule exists; `OPTIMAL` means it's also proven best.

### "Model status: Infeasible"
The GAMS model has no feasible solution given the current data — for
example, all delivery dates are too tight. This is rarely a code bug;
it's a data issue. Re-check the delivery dates in `siparisturu_v6.gms` —
if any are in the past relative to today, Agent 2 would have flagged
them, but you may also need to push them later.

### Re-running after a partial failure
You can re-run just the analysis step (fast, ~5 seconds) without re-doing
the GAMS solve by passing `--skip-solver` to the orchestrator:

```
$ python3 orchestrator.py --gams PATH_TO_GAMS --skip-solver
```

This is useful while iterating on report formatting.

---

## Part 6 — When in doubt, ask an AI

If something doesn't work and the troubleshooting list above doesn't
cover it, copy one of these prompts into ChatGPT, Claude, or any AI
chat tool. **Replace `<PASTE ERROR HERE>` with the exact error message
you see.**

### Prompt template A — "I get an error and don't understand it"

```
I am running a Python pipeline that wraps a GAMS optimisation model.
I am NOT a programmer. The project is for a graduation thesis in
Industrial Engineering. There are 4 files: orchestrator.py,
data_agent.py, solver_agent.py, analysis_agent.py.

I ran this command:

  <PASTE THE COMMAND YOU RAN HERE>

and I got this output:

  <PASTE THE FULL ERROR / OUTPUT HERE>

Please:
1. Explain in plain language what went wrong.
2. Tell me exactly what to type to fix it.
3. Do not assume I know Python — give the literal command, not pseudocode.
```

### Prompt template B — "The pipeline ran but the result looks wrong"

```
I ran a notebook-production GAMS scheduling pipeline. The Excel output
"schedule_output.xlsx" has surprising numbers. Here are the contents of
solve_summary.txt:

  <PASTE solve_summary.txt CONTENTS HERE>

And here are the contents of data_validation_report.txt:

  <PASTE data_validation_report.txt CONTENTS HERE>

What does each line mean, and do these numbers indicate the solve worked
correctly?
```

### Prompt template C — "I need to change something in the model"

```
I have a GAMS file siparisturu_v6.gms with a notebook-production
scheduling model: 198 jobs (I01..I198), 13 machines, 7 routes, objective
0.10*Cmax + 0.60*sum(Ti) + 0.30*sum(delta). I want to change
<describe what you want to change, e.g. "the delivery date for jobs
I140..I151 from 2027-05-25 to 2027-06-15">.

How do I make this change in the .gms file without breaking the model?
Tell me which lines to edit.
```

---

## Part 7 — A quick mental model of how the pipeline thinks

If you are curious about why each agent exists:

- **Data Agent (Agent 2)** acts like a careful reviewer. It reads the
  .gms file *as text* and checks that the data section is consistent
  before you invest two hours of CPU on a bad solve.
- **Solver Agent (Agent 3)** acts like a babysitter for GAMS. It launches
  GAMS as a subprocess, streams every line of output to the screen and to
  a log file, and watches for the words "Infeasible" or "Time limit
  reached" so it can tell you what happened without you having to read
  the 100k-line `.lst` yourself.
- **Analysis Agent (Agent 4)** acts like a translator. It reads the
  numerical solution out of the `.lst` file's `DISPLAY` block and turns
  it into an Excel spreadsheet that you can actually show to people.
- **Orchestrator (Agent 1)** acts like a project manager. It runs the
  three agents in order, stops if any of them fail, and prints a final
  summary.

All four scripts use only standard library Python — plus `openpyxl` to
write the Excel file. None of them modifies the .gms file.

Good luck with the defence!
