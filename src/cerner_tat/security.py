"""Runtime security safeguards for handling PHI locally.

Two independent defenses:

1. A NETWORK KILL-SWITCH that blocks all outbound TCP/IP connections and DNS
   lookups process-wide. The tool needs no network, so this guarantees that no
   patient data can leave the machine — even accidentally, and even from a
   transitive dependency. Installed automatically when the package is imported
   (see cerner_tat/__init__.py).

2. A FAIL-CLOSED PHI GUARD that scans generated output for anything that looks
   like a patient name or MRN and refuses to write the file if de-identification
   is supposed to be on. This catches configuration mistakes before a leak can
   reach disk.

Neither is a substitute for organizational HIPAA safeguards — see SECURITY.md.
"""

from __future__ import annotations

import os
import re
import socket
from typing import List, Tuple

import pandas as pd
from pandas.api.types import is_numeric_dtype


# ---------------------------------------------------------------------------
# 1. Network kill-switch
# ---------------------------------------------------------------------------

class NetworkBlocked(RuntimeError):
    """Raised when code attempts a network connection in this offline tool."""


_BLOCKED_FAMILIES = {socket.AF_INET, getattr(socket, "AF_INET6", socket.AF_INET)}
_guard_installed = False

# The environment variable below exists only as a documented, deliberate escape
# hatch. It should never be set in a hospital deployment.
_ALLOW_ENV = "CERNER_TAT_ALLOW_NETWORK"


def install_network_guard() -> bool:
    """Block outbound IP connections and DNS resolution process-wide.

    Returns True if the guard is active, False if it was disabled via the escape
    hatch env var. Safe to call more than once.
    """
    global _guard_installed
    if _guard_installed:
        return True
    if os.environ.get(_ALLOW_ENV) == "1":
        return False

    _orig_connect = socket.socket.connect
    _orig_connect_ex = socket.socket.connect_ex

    def _blocked_connect(self, address, *args, **kwargs):
        if getattr(self, "family", None) in _BLOCKED_FAMILIES:
            raise NetworkBlocked(
                "Outbound network access is disabled — Cerner TAT Scraper runs "
                "fully offline so no patient data can leave this machine."
            )
        return _orig_connect(self, address, *args, **kwargs)

    def _blocked_connect_ex(self, address, *args, **kwargs):
        if getattr(self, "family", None) in _BLOCKED_FAMILIES:
            raise NetworkBlocked("Outbound network access is disabled (offline-only).")
        return _orig_connect_ex(self, address, *args, **kwargs)

    def _blocked_dns(*args, **kwargs):
        raise NetworkBlocked("DNS resolution is disabled (offline-only).")

    socket.socket.connect = _blocked_connect
    socket.socket.connect_ex = _blocked_connect_ex
    socket.getaddrinfo = _blocked_dns
    socket.gethostbyname = _blocked_dns
    socket.create_connection = _blocked_dns

    _guard_installed = True
    return True


# ---------------------------------------------------------------------------
# 2. Fail-closed PHI guard
# ---------------------------------------------------------------------------

class PhiLeakError(RuntimeError):
    """Raised when output appears to contain patient identifiers."""


# "LASTNAME,FIRSTNAME" style names (letters, comma, letters). Note this also
# matches legitimate test names like "Urinalysis, Auto", so it is applied ONLY to
# identity-type columns — never to the Test column.
_NAME_RE = re.compile(r"[A-Za-z]{2,}\s*,\s*[A-Za-z]{2,}")

# Words that mark a column as holding (or being expected to hold) an identifier.
_IDENTITY_HINTS = ("patient", "mrn", "accession", "name", "fin")


def _is_identity_col(col: str) -> bool:
    c = str(col).strip().lower()
    return any(h in c for h in _IDENTITY_HINTS)


def scan_frame_for_phi(df: pd.DataFrame, config) -> List[Tuple[str, str]]:
    """Return (column, kind) hits in text columns of a frame.

    Two tiers, to catch real leaks without flagging legitimate test names:
      * every text column is checked against the strict patient-header pattern
        (an MRN followed by a LAST,FIRST name) — specific, no false positives on
        test names;
      * identity-type columns (Patient/MRN/Accession/Name) are ALSO checked
        against the looser LAST,FIRST name pattern, since those columns should be
        blank or anonymized once de-identification has run.
    Only object/text columns are scanned, so large numeric TAT values are never
    mistaken for an MRN.
    """
    hits: List[Tuple[str, str]] = []
    header_pat = getattr(config, "text_patient_header_pattern", None)
    for col in df.columns:
        # Skip numeric columns so large TAT values are never treated as text/MRNs;
        # scan everything else (object / str / string dtypes) as text.
        if is_numeric_dtype(df[col]):
            continue
        patterns = []
        if header_pat is not None:
            patterns.append(header_pat)
        if _is_identity_col(col):
            patterns.append(_NAME_RE)
        if not patterns:
            continue
        for val in df[col].tolist():
            if val is None:
                continue
            s = str(val)
            if any(p.search(s) for p in patterns):
                hits.append((str(col), "name/MRN pattern"))
                break
    return hits


def assert_no_phi(frames: List[pd.DataFrame], config) -> None:
    """Fail closed: if de-identification is on and any frame looks like it holds
    a name/MRN, refuse to proceed (no PHI-bearing file is written).

    The error names the offending column only — never the matched value — so the
    guard itself doesn't echo PHI into logs.
    """
    if not getattr(config, "deidentify", True):
        return  # the lab deliberately opted into identifiers; guard steps aside
    offending = []
    for df in frames:
        if df is None or df.empty:
            continue
        for col, _kind in scan_frame_for_phi(df, config):
            offending.append(col)
    if offending:
        cols = ", ".join(sorted(set(offending)))
        raise PhiLeakError(
            "Refusing to write output: possible patient identifiers detected in "
            f"column(s): {cols}. De-identification is on, so this indicates a "
            "configuration problem (e.g. a patient-header line that wasn't "
            "recognized, or a name/MRN column being mapped). Check config.yaml "
            "before proceeding."
        )
