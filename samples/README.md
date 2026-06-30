# Sample reports

Drop **de-identified** Cerner report files here (`.html` or `.pdf`) to test and
tune the parser against your real layout.

**Do not commit real patient data.** Replace names, MRNs, and accession numbers
with dummy values before saving a file here. This folder is for format samples
only.

`example_report.html` is a synthetic, fictional report included so you can see
the expected shape and try the tool immediately:

```bash
python -m cerner_tat.cli samples/example_report.html -o output
```
