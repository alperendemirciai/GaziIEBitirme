# AGENT 4 — ANALYSIS AGENT
## Paste this as your opening message in a separate Claude Code session,
## OR save as analysis_agent.py and let the Orchestrator run it.

You are the analysis agent for a notebook production scheduling model.
Your job is to parse the GAMS solution from `siparisturu_v6.lst` and produce
a human-readable Excel schedule report.

## What the .lst file contains (solution section)

After the solver finishes, the GAMS DISPLAY section at the end of the .lst file
contains these parameter tables — each in the format:

```
----   NNN PARAMETER parameter_name

   i1   val1,   i2   val2, ...
```

The parameters you need to extract are:

| Parameter | What it means |
|---|---|
| `rota_atama(i)` | Route number assigned to each job (1–7) |
| `tamamlanma(i)` | Completion time of each job in minutes |
| `teslim_gun(i)` | Completion time in working days |
| `gecikme(i)` | Tardiness in minutes (0 if on time) |
| `gecikme_gun(i)` | Tardiness in working days |
| `makine_yuk(j)` | Total load on each machine in minutes |
| `makine_yuk_gun(j)` | Total load on each machine in days |
| `geciken_is_adedi` | Scalar: count of late jobs |
| `Z_obj.l` | Scalar: objective value |
| `Cmax.l` | Scalar: makespan in minutes |
| `d(i)` | Due date for each job in minutes (also displayed) |

## Job metadata (hardcoded — use this to enrich the output)

Each job ID maps to a name in the format:
`CUSTOMER-BindingType-Pages-Format-RulingType`

Extract CUSTOMER, BindingType, and RulingType from the job name string in the .lst file.
The job names appear in the .lst file header section like:
```
I01  "ŞOK-Plastik Spiral-72YP-A4-Çizgili"
```

Route number → route description mapping:
- 1 = Wire Stitch (Bielom2 → Shrink1 → MSK)
- 2 = Plastic Spiral via Plasticol
- 3 = Plastic Spiral via Kore
- 4 = Double Metal via Autobind
- 5 = Double Metal via CWH
- 6 = Manual Spiral
- 7 = Thread Stitch

## Script to write: analysis_agent.py

Write a Python script that:

### 1. Parses siparisturu_v6.lst

Use line-by-line reading. The DISPLAY block looks like this in the .lst file:
```
----    488 PARAMETER rota_atama  route assigned to each job

        I01          2,          I02          3,          I03          2,
        I04          3, ...
```

Write a general-purpose parser function:
```python
def parse_parameter(lst_lines, param_name):
    """Returns dict {element_name: float_value}"""
```

Key parsing notes:
- Lines with parameter values use comma-separated `KEY  VALUE` pairs, sometimes
  wrapping across multiple lines until the next `----` block.
- Values of 0 are often omitted (GAMS sparse display) — treat missing as 0.
- For scalar parameters (geciken_is_adedi, Z_obj.l, Cmax.l), the line looks like:
  `----   NNN PARAMETER Z_obj.l              =  123456.789`

### 2. Builds a job table

Create a list of dicts, one per job, with these columns:
```
job_id          e.g. "I01"
job_name        e.g. "ŞOK-Plastik Spiral-72YP-A4-Çizgili"
customer        e.g. "ŞOK"
binding_type    e.g. "Plastik Spiral"
ruling          e.g. "Çizgili"
route_num       e.g. 2
route_desc      e.g. "Plastic Spiral via Plasticol"
qty             from the .gms file (parse qty block just like the data agent does)
due_minutes     d(i) value
due_days        due_minutes / 1200
completion_min  tamamlanma(i)
completion_days teslim_gun(i)
tardiness_min   gecikme(i)
tardiness_days  gecikme_gun(i)
status          "ON TIME" if tardiness_min == 0 else "LATE"
```

Sort the table by tardiness_days descending (worst late jobs first),
then by due_days ascending within on-time jobs.

### 3. Writes schedule_output.xlsx with 3 sheets

#### Sheet 1: "Job Schedule"
All columns listed above, one row per job (198 rows).
Apply conditional formatting:
- Red background on the `status` cell if "LATE"
- Green background if "ON TIME"
- Bold the rows where tardiness_days > 1

#### Sheet 2: "Machine Load"
| Machine | Load (min) | Load (days) | Capacity (min/day) | Utilization % |
For utilization: load_min / (capacity * total_days_of_schedule), where
total_days_of_schedule = Cmax / 1200.
Sort by utilization descending.

Include these capacity values (minutes/day):
- Bielom1: 4800, Bielom2: 4800
- Shrink1: 2400, Shrink2: 2400, MSK: 2400
- All others: 1200

#### Sheet 3: "Summary"
A KPI block with the following rows:
```
Total jobs scheduled:       198
Jobs on time:               <count>
Jobs late:                  <geciken_is_adedi>
On-time rate:               <pct>%
Objective value (Z):        <Z_obj.l>
Makespan:                   <Cmax.l> min  /  <Cmax.l/1200> days
Most loaded machine:        <machine name> at <utilization>%
Most late job:              <job_id> - <job_name>, <tardiness_days> days late
```

Use openpyxl for all Excel writing. Do not use pandas.

### 4. Print on success:
```
ANALYSIS AGENT COMPLETE
Output: schedule_output.xlsx
Jobs on time: <N> / 198
Most late job: <job_id>, <tardiness_days> days
Makespan: <days> working days
```

### 5. Exit codes
- Exit 0 on success
- Exit 1 if siparisturu_v6.lst not found
- Exit 2 if .lst file exists but contains no DISPLAY section (solve may have crashed)
- Exit 3 if openpyxl not installed (print install command: `pip install openpyxl`)

## Rules
- Parse the .lst file — do not hardcode any solution values.
- The qty values must be re-parsed from siparisturu_v6.gms (you need them for the job table).
- Treat any job with `tamamlanma(i) = 0` as unscheduled (flag as "UNSCHEDULED" in status).
- Use only Python standard library + openpyxl.
- Print "ERROR: <message>" for any failure.
