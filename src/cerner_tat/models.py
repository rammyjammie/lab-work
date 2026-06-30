"""The core data model: one TestRecord per test/order row in a report."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from .config import TAT_FIELDS, TIME_FIELDS


@dataclass
class TestRecord:
    """A single test/order extracted from a report.

    TAT values are stored in **minutes** (float). Any of them may be None if the
    report neither provides the column nor the timestamps needed to compute it.
    """

    # Stop pytest from trying to collect this as a test class (name starts "Test").
    __test__ = False

    test_name: str = ""
    patient_name: Optional[str] = None
    mrn: Optional[str] = None
    accession: Optional[str] = None

    order_time: Optional[datetime] = None
    collected_time: Optional[datetime] = None
    received_time: Optional[datetime] = None
    complete_time: Optional[datetime] = None

    tat_order_to_collected: Optional[float] = None
    tat_collected_to_lab: Optional[float] = None
    tat_collected_to_complete: Optional[float] = None
    tat_lab_to_complete: Optional[float] = None
    tat_order_to_complete: Optional[float] = None

    category: Optional[str] = None
    shift: Optional[str] = None

    # raw cell values keyed by canonical field, for debugging / the Detail sheet
    raw: Dict[str, str] = field(default_factory=dict)

    def get_time(self, field_name: str) -> Optional[datetime]:
        return getattr(self, field_name, None) if field_name in TIME_FIELDS else None

    def to_row(self) -> Dict[str, object]:
        """Flatten to a dict suitable for a spreadsheet Detail row."""
        row: Dict[str, object] = {
            "patient_name": self.patient_name,
            "mrn": self.mrn,
            "accession": self.accession,
            "test_name": self.test_name,
            "category": self.category,
            "shift": self.shift,
        }
        for tf in TIME_FIELDS:
            value = getattr(self, tf)
            row[tf] = value.strftime("%Y-%m-%d %H:%M") if value else None
        for tat in TAT_FIELDS:
            row[tat] = getattr(self, tat)
        return row
