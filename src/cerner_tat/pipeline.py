"""End-to-end: file(s) in -> enriched records -> summaries -> .xlsx out."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from .aggregate import Summaries, build_summaries
from .classify import enrich
from .config import Config, load_config
from .models import TestRecord
from .parsers import parse_file, parse_text
from .report import write_workbook


@dataclass
class ProcessResult:
    input_path: str
    output_path: Optional[str]
    record_count: int
    summaries: Optional[Summaries] = None
    error: Optional[str] = None


def process_records(paths: List[str], config: Config) -> List[TestRecord]:
    """Parse + enrich every path, returning the combined record list."""
    records: List[TestRecord] = []
    for path in paths:
        records.extend(parse_file(path, config))
    return enrich(records, config)


def process_file(
    path: str,
    output_dir: str,
    config: Optional[Config] = None,
) -> ProcessResult:
    """Process one report file into one .xlsx workbook."""
    config = config or load_config()
    try:
        records = enrich(parse_file(path, config), config)
        summaries = build_summaries(records, config)

        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0]
        output_path = os.path.join(output_dir, f"{base}_TAT.xlsx")
        write_workbook(summaries, output_path)

        return ProcessResult(
            input_path=path,
            output_path=output_path,
            record_count=len(records),
            summaries=summaries,
        )
    except Exception as exc:  # surface a clean message to the GUI/CLI
        return ProcessResult(
            input_path=path,
            output_path=None,
            record_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )


def process_files(
    paths: List[str],
    output_dir: str,
    config: Optional[Config] = None,
) -> List[ProcessResult]:
    config = config or load_config()
    return [process_file(p, output_dir, config) for p in paths]


def process_text(
    text: str,
    output_dir: str,
    output_name: str = "pasted_report",
    config: Optional[Config] = None,
) -> ProcessResult:
    """Process pasted report text into one .xlsx workbook."""
    config = config or load_config()
    label = f"<pasted:{output_name}>"
    try:
        records = enrich(parse_text(text, config), config)
        if not records:
            return ProcessResult(
                input_path=label,
                output_path=None,
                record_count=0,
                error="No test records were recognized in the pasted text.",
            )
        summaries = build_summaries(records, config)

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{output_name}_TAT.xlsx")
        write_workbook(summaries, output_path)

        return ProcessResult(
            input_path=label,
            output_path=output_path,
            record_count=len(records),
            summaries=summaries,
        )
    except Exception as exc:
        return ProcessResult(
            input_path=label,
            output_path=None,
            record_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )
