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

---

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
```

---

## Security notes

- **No network access.** The code imports only local libraries; it never opens a
  socket or calls a web service. You can run it on an air-gapped machine.
- **No telemetry.** Nothing is logged or sent anywhere.
- **Your data stays put.** Input files are read locally; output `.xlsx` files are
  written only to the folder you choose.
- Keep input/output folders inside your lab's secured, access-controlled storage,
  the same as any other PHI.

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
