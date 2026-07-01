#!/usr/bin/env python3
"""Download all dependencies into ./vendor for an offline (air-gapped) install.

Run this on an internet-connected machine that has the SAME operating system and
the SAME Python version (3.11, 64-bit) as the target hospital machine. Then copy
the whole project folder — including the newly created ``vendor/`` directory — to
the target and install with:

    pip install --no-index --find-links vendor -r requirements.txt

``--no-index`` means pip never contacts the internet; it installs only from the
local ``vendor/`` folder.

This script performs no network access of its own beyond pip's download step,
and it does not touch any report/PHI data.
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")
VENDOR = os.path.join(ROOT, "vendor")


def main() -> int:
    if not os.path.exists(REQUIREMENTS):
        print(f"Could not find {REQUIREMENTS}", file=sys.stderr)
        return 1

    os.makedirs(VENDOR, exist_ok=True)
    print(f"Downloading dependencies into: {VENDOR}")
    print(f"Python: {sys.version.split()[0]}  Platform: {sys.platform}\n")

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "-r",
        REQUIREMENTS,
        "-d",
        VENDOR,
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\npip download failed. If you're behind a proxy, retry with:",
              file=sys.stderr)
        print("  pip download --proxy http://PROXY:PORT -r requirements.txt -d vendor",
              file=sys.stderr)
        return result.returncode

    print("\nDone. Next steps:")
    print("  1. Copy the whole project folder (including vendor/) to the target.")
    print("  2. On the target machine, run:")
    print("       pip install --no-index --find-links vendor -r requirements.txt")
    print("  3. Launch:  python run_gui.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
