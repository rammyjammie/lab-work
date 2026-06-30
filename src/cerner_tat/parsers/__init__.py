"""Report parsers. Pick the right one by file extension via `get_parser`."""

from __future__ import annotations

import os
from typing import List

from ..config import Config
from ..models import TestRecord
from .html_parser import parse_html
from .pdf_parser import parse_pdf


def parse_file(path: str, config: Config) -> List[TestRecord]:
    """Parse a report file into TestRecords based on its extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".html", ".htm", ".xhtml"):
        return parse_html(path, config)
    if ext == ".pdf":
        return parse_pdf(path, config)
    raise ValueError(
        f"Unsupported file type {ext!r} for {path!r}. "
        "Supported: .html, .htm, .pdf"
    )


__all__ = ["parse_file", "parse_html", "parse_pdf"]
