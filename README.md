# Cerner TAT Scraper

A **fully local, offline** tool for the lab. It reads Cerner TAT reports —
as an **HTML file, a PDF, or text pasted straight out of the Cerner viewer** —
classifies each test by type (CBC, Chemistry, Cardiac, Coagulation,
Urinalysis), figures out which **shift** it belongs to (day 07:00–19:00 / night
19:00–07:00), and writes a formatted **Excel spreadsheet** with the counts and
average turn‑around‑times (TAT).

> **Pasting text is the most reliable input.** Cerner TAT PDFs are often
> *screenshots/scanned images* with no selectable text, so a PDF parser can't
> read them. Copying the report text and pasting it into the **Paste text** tab
> (or saving it as a `.txt` file) sidesteps that entirely. See
> [Pasting report text](#pasting-report-text).

> **Privacy / security:** This tool makes **zero network calls**. Everything runs
> on your machine. No patient data ever leaves the computer. See
> [Security notes](#security-notes).

---

## What it produces

For each report you feed in, you get an `.xlsx` workbook with these sheets:

| Sheet | Contents |
|-------|----------|
| **Daily Summary** | One wide row for the day: counts by type, patient count, and grouped average TAT by shift. Designed to stack into a running tracker — see [Daily Summary](#daily-summary-the-wide-tracking-row). |
| **Summary** | Total tests, totals by type, totals by shift, at a glance |
| **Counts by Type** | Test counts per category, split by Day / Night |
| **TAT by Type** | Average of each TAT metric per category |
| **TAT by Type & Shift** | Average of each TAT metric per category, per shift |
| **Detail** | Every parsed row (patient, test, timestamps, TAT, category, shift) |

The five TAT metrics tracked are exactly the columns from your reports:

- order → collected
- collected → lab
- collected → complete
- lab → complete
- order → complete

If your report already has these as columns, they're used directly. If it only
has timestamps (ordered / collected / received / completed), the tool computes
them.

> **Note:** Cerner displays timestamps truncated to the minute but computes TAT
> on the underlying seconds, so a value recomputed from the displayed times can
> differ from Cerner's by ~1 minute. The tool therefore always prefers the
> report's own TAT numbers and only computes them when they're absent.

---

## Quick start

### 1. Install Python 3.10+

- **Windows / macOS:** download from [python.org](https://www.python.org/downloads/).
  The official installer includes `tkinter` (used for the GUI). On Windows,
  check *"Add Python to PATH"* during install.
- **Linux:** install Python plus tkinter, e.g. on Debian/Ubuntu:
  `sudo apt install python3 python3-tk python3-pip`

### 2. Install the dependencies (one time, offline-capable)

```bash
pip install -r requirements.txt
```

### 3. Run the GUI

```bash
python run_gui.py
```

Pick one or more report files, choose an output folder, click **Process**.

Prefer the command line? See [Command line](#command-line-optional).

### Pasting report text

Because Cerner TAT PDFs are frequently images, the easiest path is usually:

1. In Cerner, select the report text and copy it.
2. Open the GUI (`python run_gui.py`) and switch to the **Paste text** tab.
3. Paste, give it an output name, and click **Process**.

The tool reads the text positionally — each test is a block of: test name,
(optional) priority code, the four timestamps, then the five TAT values. This
layout is defined under `text_layout` in `config/config.yaml`, so if your
report's column order differs you can adjust it there without touching code. You
can also save the copied text as a `.txt` file and process it like any other
input.

### Pasting a whole day at once (grouped by patient)

If you paste an entire report where tests are grouped under patient headers like:

```
6000788 SURNAME,FIRSTNAME EMERGENCY
PT
ST
06/17/2026 07:54
... (timestamps + TAT values)
CBC w/ Diff
ST
...
6000799 OTHERSURNAME,OTHERFIRST EMERGENCY
Troponin I
...
```

…the tool **automatically detects and discards those patient/encounter header
lines** — the name, MRN, and location are *never* written to the spreadsheet.
Each patient is instead counted and shown only as an anonymized **`Patient 1`,
`Patient 2`…** label, so you still get a patient count and can see which tests
belonged to the same (unnamed) patient. This lets you copy-paste the full day
in one go. See `samples/example_pasted_report_by_patient.txt` for the format.

Which lines count as a patient header is controlled by
`text_layout.patient_header_pattern` in the config (default: an MRN number
followed by a `LAST,FIRST` name). Set it to empty to turn the feature off.

If a report has **no MRN + name header**, a bare divider line can still separate
patients: any line matching `text_layout.patient_delimiters` (default:
`PATIENT`) starts a new patient and is discarded. So a paste like
`PATIENT` / test block / `PATIENT` / test block is split into two patients.

### De-identification

By default (`privacy.deidentify: true` in the config), **no patient name, MRN,
or accession number is ever written to the output** — for any input type. Only
the anonymized `Patient N` label and a patient count appear. Set
`privacy.deidentify: false` only if you deliberately want identifiers in the
spreadsheet (not recommended for shared files).

---

## Daily Summary: the wide tracking row

The **Daily Summary** sheet is **one row per date**, laid out as columns so days
stack into a running, day-over-day tracker (the same wide shape your lab
already uses). If a single paste/report spans several days, it's split into one
row per calendar date automatically (a one-day paste is just one row):

```
Date | CBC | Chemistry | Cardiac | Coagulation | Urinalysis | Total | Patients | <grouped TAT by shift…>
```

**Why it's trimmed.** Two of the five TAT metrics are exact sums of the others,
so they carry no extra information in an average:

- `Collected→Complete = Collected→Lab + Lab→Complete`
- `Order→Complete   = Order→Collected + Collected→Lab + Lab→Complete`

So by default each group shows the **three independent phases** (`Order→Coll`,
`Coll→Lab`, `Lab→Comp`) plus the **`Order→Comp` total** as the headline — four
columns instead of five, and every number means something. TAT is grouped
**Blood vs Urine** and split **Day vs Night** (the "overall" column is dropped
because it's just Day+Night combined).

All of this is controlled under `daily_summary` in `config/config.yaml` — change
the metrics, the groups (e.g. one per test type), or the shifts without touching
code.

### Outlier cap (e.g. urine cultures)

Some tests — urine cultures especially — take thousands of minutes and would
wreck an average. Any single TAT value above `analysis.tat_cap_minutes`
(default **500**) is **left out of the averaged metrics** on every summary sheet.
The raw values are still shown on the **Detail** sheet, and the **Summary** sheet
reports how many values were excluded, so nothing is hidden. Set the cap to
empty to disable it.

### Running master workbook

Point the tool at a master file and each report's Daily Summary row is
**appended** to it, building the time series automatically:

```bash
python -m cerner_tat.cli report.txt -o output --master output/master.xlsx
```

In the GUI, set the optional **Master file** field. The master is created on
first use and grown one row per date thereafter (a multi-day report appends
several rows at once); new columns are added on the end if the layout ever
changes, so old rows keep working.

## Tuning it to YOUR reports

Cerner output varies by site, so the parser is driven entirely by
[`config/config.yaml`](config/config.yaml) — you usually never touch the code.

1. Drop a **de‑identified** sample report into [`samples/`](samples/).
2. Open `config/config.yaml`.
3. Under `columns:`, make sure each field lists the exact header text that
   appears in your report (matching is case-insensitive and ignores spacing /
   punctuation). Add aliases as needed.
4. Under `classification:`, adjust the keyword/regex lists so your local test
   names map to the right category.
5. Re-run. Check the **Detail** sheet — every row should have a `category` and a
   `shift`. Anything landing in `Other` is a test name your rules didn't match
   yet; add a pattern for it.

If your layout is unusual (merged header cells, multi-row headers, free-text
PDF instead of tables), share the de-identified sample and the parser can be
adapted to it.

---

## Command line (optional)

```bash
# one file
python -m cerner_tat.cli path/to/report.html -o output_folder

# a whole folder of reports
python -m cerner_tat.cli reports/*.pdf reports/*.html -o output_folder

# append each report's Daily Summary row to a running master workbook
python -m cerner_tat.cli reports/*.txt -o output_folder --master output_folder/master.xlsx
```

---

## Security notes

See **[SECURITY.md](SECURITY.md)** for the full security model, threat model, and
the split between what the tool enforces and what your institution must provide.
In short:

- **Offline is enforced, not just promised.** Importing the package installs a
  network kill-switch that blocks all outbound connections and DNS — so patient
  data cannot leave the machine, even from a dependency. Verify with
  `python -m pytest tests/test_security.py -k network -v`.
- **De-identification on by default.** No name, MRN, or accession is written to
  output; patients show only as `Patient N`. Patient header lines are discarded.
- **Fail-closed PHI guard.** Before writing, every sheet is scanned; if anything
  looks like a name/MRN while de-id is on, the tool refuses to write the file.
- **Data minimization.** `privacy.include_detail_sheet` and
  `privacy.include_timestamps` let you trim the output further.
- **No telemetry, no hidden copies.** Only the `.xlsx` files you ask for are
  written, to the folder you choose.
- Still keep input/output folders inside your lab's secured, access-controlled,
  encrypted storage, the same as any other PHI — that part is on the institution.

---

## Project layout

```
config/config.yaml        # column aliases, shift times, classification rules — edit this
samples/                  # drop de-identified sample reports here
src/cerner_tat/           # the package
  parsers/                # HTML + PDF table extraction, and pasted-text parsing
  classify.py             # test-type + shift assignment
  aggregate.py            # counts + average TAT
  report.py               # Excel writer
  pipeline.py             # ties it together
  gui.py / cli.py         # the two ways to run it
tests/                    # unit tests with synthetic data
run_gui.py                # double-clickable launcher for the GUI
```

## Running the tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```
