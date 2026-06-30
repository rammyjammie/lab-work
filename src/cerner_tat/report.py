"""Write the summary tables to a formatted .xlsx workbook (local file, offline)."""

from __future__ import annotations

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .aggregate import Summaries

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_TITLE_FONT = Font(bold=True, size=12)


def _write_sheet(writer: pd.ExcelWriter, name: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        df = pd.DataFrame({"(no data)": []})
    df.to_excel(writer, sheet_name=name, index=False)
    ws = writer.sheets[name]

    # style header row
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # auto-ish column widths
    for col_idx, col in enumerate(df.columns, start=1):
        max_len = max(
            [len(str(col))]
            + [len(str(v)) for v in df.iloc[:, col_idx - 1].tolist()]
        )
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)

    ws.freeze_panes = "A2"


def write_workbook(summaries: Summaries, output_path: str) -> str:
    """Write all sheets to output_path. Returns the path."""
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _write_sheet(writer, "Summary", summaries.summary)
        _write_sheet(writer, "Counts by Type", summaries.counts_by_type)
        _write_sheet(writer, "TAT by Type", summaries.tat_by_type)
        _write_sheet(writer, "TAT by Type & Shift", summaries.tat_by_type_shift)
        _write_sheet(writer, "Detail", summaries.detail)
    return output_path
