# Security & Privacy

This document describes the security model of the Cerner TAT Scraper and the
split of responsibilities between the tool and your institution. Please review it
with your facility's **Privacy Officer / Security Officer / IT** before using the
tool with real reports.

> **Honest scope:** No software can, by itself, make handling patient data
> "totally safe" or "HIPAA compliant." Compliance is an *organizational* status
> that also depends on device security, access controls, physical security,
> policies, training, and risk assessments. This tool is built to enforce strong
> **technical** safeguards and to minimize what it ever touches — but the
> safeguards below are only part of the picture.

---

## What the tool does (technical safeguards)

### 1. Fully offline — enforced, not just promised
The tool needs no network, and it actively blocks network use. On import it
installs a process-wide **network kill-switch** (`src/cerner_tat/security.py`)
that raises an error on any attempt to open an outbound TCP/IP connection or
resolve a hostname. This means patient data cannot leave the machine — not by
the tool, and not by any library it loads.

*Verify it yourself:*
```bash
python -m pytest tests/test_security.py -k network -v
```

### 2. De-identification on by default
With `privacy.deidentify: true` (the default), **no patient name, MRN, or
accession number is ever written to the output** — for any input type. Patients
appear only as an anonymized `Patient N` label. When pasting a whole report,
patient/encounter header lines (e.g. `6000788 SURNAME,FIRST EMERGENCY`) are
detected and discarded before anything is stored.

### 3. Fail-closed PHI guard
Before any workbook is written, every sheet is scanned for text that looks like a
patient name or MRN. If de-identification is on and something matches, the tool
**refuses to write the file** and reports which column tripped the check (never
the value itself). This turns a silent de-identification mistake into a safe,
loud failure.

### 4. Data minimization options
`config/config.yaml` → `privacy:`
- `include_detail_sheet: false` — omit the per-test Detail sheet entirely.
- `include_timestamps: false` — drop exact order/collect/receive/complete times
  from the Detail sheet (a precise timestamp + test can be a quasi-identifier for
  a small patient population).

Counts and averaged TAT never contain PHI regardless of these settings.

### 5. No telemetry, no hidden persistence
The tool reads only the input you give it and writes only the `.xlsx` files (and
optional master workbook) to the folder you choose. It creates no caches,
temp copies, or logs of report content, and sends nothing anywhere.

---

## What your institution must provide (organizational safeguards)

The tool cannot do these — they are the deployer's responsibility:

- **Device & OS security:** run on a managed, patched, access-controlled
  workstation. Enable full-disk encryption (BitLocker / FileVault).
- **Access control:** restrict who can run the tool and who can open its output
  folders (least privilege). Use per-user accounts, not a shared login.
- **Physical security:** the workstation and any printed output must be
  physically secured.
- **Secure storage & handling of output:** keep input and output files on
  encrypted, access-controlled storage. Do **not** email outputs or upload them
  to unmanaged/consumer cloud services. Follow your retention/disposal policy.
- **Software review:** have IT/Security review and approve this tool and its
  dependencies before deployment (see *Supply chain* below).
- **Workforce training & policies:** minimum-necessary use, incident reporting,
  and your organization's PHI-handling procedures.
- **Risk assessment & BAAs:** any formal HIPAA risk analysis and business
  associate agreements are organizational processes, not features of this tool.

---

## Threat model

**Protects against**
- Accidental data egress (a dependency or mistake trying to "phone home") —
  blocked by the network kill-switch.
- De-identification mistakes reaching a file — caught by the fail-closed PHI
  guard.
- Over-collection of identifiers — de-identification + minimization options.

**Does *not* protect against (institution's domain)**
- A compromised or malicious operating system / user with local access.
- Someone deliberately turning safeguards off (`privacy.deidentify: false`, or
  the documented `CERNER_TAT_ALLOW_NETWORK=1` escape hatch) and mishandling data.
- Insecure storage, sharing, or disposal of the output files.
- Physical access to the machine or printouts.

The escape hatches exist for flexibility but **should never be enabled in a
hospital deployment**; treat their use as a policy decision.

---

## Supply chain (recommended for IT review)

Dependencies are all mainstream, offline-capable libraries (pandas, openpyxl,
beautifulsoup4, lxml, pdfplumber, PyYAML). For a hardened install, IT can pin
exact versions with hashes and install with verification:

```bash
pip install pip-tools
pip-compile --generate-hashes requirements.txt -o requirements.lock
pip install --require-hashes -r requirements.lock
```

This guarantees the exact reviewed packages are installed and nothing was
substituted.

---

## Reporting a concern

This is an internal lab tool. Route any security concern to your team's
maintainer and your facility's Security Officer.
