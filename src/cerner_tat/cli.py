"""Command-line entry point: `python -m cerner_tat.cli report.html -o out/`."""

from __future__ import annotations

import argparse
import sys
from typing import List

from .config import load_config
from .pipeline import process_file


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cerner_tat",
        description="Turn Cerner HTML/PDF lab reports into a TAT spreadsheet (fully local).",
    )
    parser.add_argument("inputs", nargs="+", help="Report files (.html/.htm/.pdf/.txt)")
    parser.add_argument(
        "-o", "--output-dir", default="output", help="Folder for the .xlsx files"
    )
    parser.add_argument(
        "-c", "--config", default=None, help="Path to a config.yaml (optional)"
    )
    parser.add_argument(
        "-m",
        "--master",
        default=None,
        help="Append each report's Daily Summary row to this running master .xlsx",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)

    exit_code = 0
    for path in args.inputs:
        result = process_file(path, args.output_dir, config, master_path=args.master)
        if result.error:
            print(f"[FAIL] {path}: {result.error}", file=sys.stderr)
            exit_code = 1
        else:
            print(
                f"[ OK ] {path}: {result.record_count} tests -> {result.output_path}"
            )
    if args.master:
        print(f"       Daily Summary rows appended to {args.master}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
