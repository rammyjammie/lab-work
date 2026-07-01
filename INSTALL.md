# Installing on a hospital computer

Hospital workstations are typically locked down: no admin rights, restricted or
no internet, managed software only, and IT approval required for new tools. This
guide covers the three realistic install paths. Pick the one that matches your
environment — **Option A if IT will help, Option B for an offline/air-gapped
machine, Option C if you want no Python install at all.**

Whichever route you take, hand your IT/Security team [SECURITY.md](SECURITY.md)
first — most hospitals require review before a new tool is approved.

---

## Before you start

You need to know two things about the target machine:

1. **Do you have admin rights?** (Usually no on a clinical workstation.)
2. **Does it have internet access?** Fully offline, proxied, or open?

The tool itself runs **fully offline** by design (it blocks all network access),
but *installing* the Python packages needs to get them onto the machine somehow —
that's what the options below solve.

---

## Option A — IT-managed standard install (recommended)

Best when your IT/software center can provide Python and allow a one-time
package install.

1. **Request Python 3.11 (64-bit)** through your software center / IT ticket, or
   have IT install it from <https://www.python.org/downloads/>. Ask them to check
   **"Add Python to PATH."** (The official installer includes the GUI toolkit.)
2. **Place the project folder** in an approved location (e.g. your user profile
   or a lab share) — for example `C:\LabTools\cerner-tat-scraper\`.
3. **Install dependencies once.** Open a terminal in that folder:
   ```
   pip install -r requirements.txt
   ```
   - If the machine uses a **proxy**, IT can point pip at it:
     `pip install --proxy http://PROXY:PORT -r requirements.txt`
   - No admin rights? Add `--user`: `pip install --user -r requirements.txt`
4. **Run it:**
   ```
   python run_gui.py
   ```
5. *(Optional)* Have IT create a Start-menu or desktop shortcut that runs
   `pythonw run_gui.py` in the project folder, so staff just click an icon.

---

## Option B — Offline install with a wheel bundle (air-gapped machine)

Best when the target machine has **no internet** (or you're not allowed to run
pip against the internet on it). You prepare a bundle on an internet-connected
machine, move it via approved media, and install from the bundle — no internet
needed on the target.

> The bundle is platform-specific. Prepare it on a machine with the **same OS and
> the same Python version (3.11, 64-bit)** as the target.

**On an internet-connected machine (same OS + Python version):**
```
python scripts/make_offline_bundle.py
```
This downloads every dependency into a `vendor/` folder. Copy the **whole project
folder (including `vendor/`)** to approved transfer media.

**On the target hospital machine (no internet needed):**
```
pip install --no-index --find-links vendor -r requirements.txt
python run_gui.py
```
`--no-index` guarantees pip never touches the internet; it installs only from the
local `vendor/` folder.

(If Python itself isn't on the target, have IT install it first — Option A step 1
— or use Option C.)

---

## Option C — Standalone executable (no Python install)

Best when you can't install Python on the clinical workstation at all. You build
a single self-contained app on a **build machine that has the same OS** (e.g. a
Windows machine to make a Windows `.exe`), then copy the result over.

This needs a small amount of one-time setup so the app can find its config file
when frozen. **Ask and I'll add a ready-to-use PyInstaller build script and the
config-path handling** — it's a ~15-minute change. The end result is a folder (or
single `.exe`) staff double-click, with nothing else to install.

---

## After installing — verify the safeguards

Confirm the offline kill-switch is active on the target machine:
```
python -m pytest tests/test_security.py -k network -v
```
All network tests should pass (meaning outbound connections are blocked). If
`pytest` isn't installed on the target, this step can be done on the build/prep
machine instead.

---

## Where to put input and output

- Keep the project folder, the input reports, and the output spreadsheets on
  **encrypted, access-controlled storage** (your lab share or an encrypted local
  profile) — same as any PHI. See [SECURITY.md](SECURITY.md).
- Point the tool's **Output folder** (and optional **Master file**) at that
  secured location in the GUI.

---

## Quick troubleshooting

| Symptom | Fix |
|--------|-----|
| `python` not recognized | Python isn't on PATH — reinstall with "Add to PATH," or use the full path to `python.exe`. |
| `pip` blocked / times out | Use the offline bundle (Option B) or IT's proxy settings. |
| GUI won't open on Linux | Install the Tk package: `sudo apt install python3-tk`. (Windows/macOS include it.) |
| "Refusing to write output… identifiers detected" | The PHI guard did its job — a patient line wasn't recognized. Check the patient-header settings in `config/config.yaml`. |
