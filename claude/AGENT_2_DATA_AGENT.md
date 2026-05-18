# AGENT 2 — DATA AGENT
## Paste this as your opening message in a separate Claude Code session,
## OR save as data_agent.py and let the Orchestrator run it.
## This agent reads no Excel file — all data is already hardcoded in the .gms file.
## Its job is to validate that file's data section before the solve runs.

You are the data validation agent for a notebook production scheduling model.
Your only job is to read `siparisturu_v6.gms`, validate its data, and write two output files.
You must not modify the .gms file under any circumstances.

## What the model contains (you must verify all of this)

### Jobs (i): I01–I198, 198 total
Each job has:
- A name string like "CUSTOMER-BindingType-Pages-Format-RulingType"
- A quantity `qty(i)` in units (already in the .gms file)
- A delivery date computed as `(delivery_date - today) * 1200` minutes
- A product type membership (one of the sets below)

### Product type sets (verify every job appears in exactly one):
| Set name in GMS | Binding type | Compatible routes |
|---|---|---|
| i_TelDikis | Wire stitch | r1 only |
| i_PlastikStd | Plastic spiral standard | r2 or r3 |
| i_PlastikKucuk | Plastic spiral small format | r2 or r3 |
| i_DblMetalKucuk | Double metal spiral small | r4 or r5 |
| i_DblMetalBuyuk | Double metal spiral large | r4 or r5 |
| i_ManuelSpiral | Manual spiral | r6 only |
| i_IplikDikis | Thread stitch | r7 only |

### Paper ruling sets (verify every job appears in exactly one):
- `i_cizgili` = lined (Çizgili)
- `i_kareli` = squared (Kareli)
- `i_duz` = plain (Düz)

### Routes (r): r1–r7
| Route | Bottleneck machine | Cycle time (sec/unit) |
|---|---|---|
| r1 | Bielom2 | 2 |
| r2 | Plasticol | 15 |
| r3 | Kore | 16.5 |
| r4 | Autobind | 9 (small) or 17 (large) |
| r5 | CWH | 15 (small) or 23 (large) |
| r6 | ManSpiral | 17 |
| r7 | Juki | 15 |

Non-bottleneck machines on every route take 25% of the bottleneck cycle time.

### Machine sequences per route:
- r1: Bielom2 → Shrink1 → MSK
- r2: Bielom1 → PolarBicak → Kugler → Plasticol → Shrink2 → MSK
- r3: Bielom1 → PolarBicak → Kore → Shrink2 → MSK
- r4: Bielom1 → PolarBicak → Kugler → Autobind → Shrink2 → MSK
- r5: Bielom1 → PolarBicak → CWH → Shrink2 → MSK
- r6: Bielom1 → PolarBicak → Kugler → ManSpiral → Shrink2 → MSK
- r7: Bielom1 → PolarBicak → Juki → Shrink2 → MSK

### Machine capacities (minutes/day):
- Bielom1: 4800  (two shifts)
- Bielom2: 4800  (two shifts)
- Shrink1: 2400
- Shrink2: 2400
- MSK:     2400
- All others (PolarBicak, Kugler, Plasticol, Kore, Autobind, CWH, ManSpiral, Juki): 1200

### Setup times:
40-minute setup on Bielom1 or Bielom2 when consecutive jobs differ in ruling type
(lined↔squared, lined↔plain, squared↔plain). Zero setup when same ruling.

### Due dates:
`d(i) = days_until_delivery * 1200` minutes.
Current delivery date groups in the model:
- Many jobs: 2027-07-10
- ADEL jobs (I64–I108): 2027-05-15
- IN UFFICIO jobs (I109–I138): 2027-05-18
- SUN jobs (I140–I151): 2027-05-25
- Tehelan jobs (I152–I187): 2027-05-18
- Ri Plast jobs (I188–I198): 2027-05-11

### Objective weights (do not change these):
- alpha = 0.10 (makespan)
- beta = 0.60 (total tardiness)
- gamma_p = 0.30 (count of late jobs)
- BigM = 9999999

## Validation checks to perform

Write a Python script `data_agent.py` that does the following:

1. Parse the .gms file with string operations (do not use a GAMS API).
   Read the `qty(i)` parameter block and extract all 198 job quantities.

2. Check: every job I01–I198 has qty > 0. Flag any zero-quantity jobs as warnings
   (they are excluded from K1 by the `$(qty(i) gt 0)` condition).

3. Check: the delivery date for each job produces d(i) > 0 minutes
   (i.e., the delivery is in the future relative to today's date).
   Today's date is whatever `datetime.date.today()` returns at runtime.
   Flag any job with d(i) <= 0 as a CRITICAL ERROR (past-due job will cause
   the model to treat any completion time as late, inflating the objective badly).

4. Check: no job appears in more than one product type set.
   Parse the set definitions in the .gms file and verify mutual exclusivity.

5. Check: no job appears in more than one ruling type set (i_cizgili, i_kareli, i_duz).

6. Compute a quick capacity feasibility estimate:
   For each machine j, sum up the minimum possible processing time across all jobs
   that could use it (using the bottleneck cycle times above and the actual qty values).
   Compare against cap_j. If total_load > cap_j * 1.5, print a WARNING that
   the machine may be overloaded (this does not stop the pipeline).

7. Write `data_validation_report.txt`:
   - One line per check: PASS / WARNING / ERROR
   - List any flagged jobs under each check
   - Final line: "OVERALL: PASS" or "OVERALL: ERROR (N critical errors found)"

8. Write `orders_summary.txt`:
   - Total jobs: 198
   - Jobs by binding type (counts)
   - Jobs by ruling type (counts)
   - Jobs by delivery date group (counts)
   - Top 5 jobs by qty (job ID, name, qty)
   - Earliest delivery date and which jobs have it

9. Exit code 0 if no critical errors, exit code 1 if any critical errors.

## Rules
- Parse the .gms file directly — do not hardcode the qty values.
- Do NOT modify the .gms file.
- Use only Python standard library + datetime.
- Print "ERROR: <message>" to stdout for any critical failure.
- Print "WARNING: <message>" to stdout for non-critical issues.
- Print "DATA AGENT COMPLETE" as the last line on success.
