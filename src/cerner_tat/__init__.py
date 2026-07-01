"""Cerner TAT Scraper — a local, offline tool for turning Cerner HTML/PDF
lab reports into a turn-around-time spreadsheet.

This package makes no network calls. Importing it installs a process-wide
network kill-switch (see security.py) so that no patient data can leave the
machine, even accidentally.
"""

from .security import install_network_guard

__version__ = "0.1.0"

# Enforce offline operation as early as possible — on any import of the package.
install_network_guard()
