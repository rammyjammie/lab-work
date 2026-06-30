#!/usr/bin/env python3
"""Double-clickable launcher for the Cerner TAT Scraper GUI.

Adds src/ to the path so you can run it without installing the package.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from cerner_tat.gui import main  # noqa: E402

if __name__ == "__main__":
    main()
