#!/usr/bin/env python3
"""Orbit Desktop command line. Run `python orbit.py --help` for the list of commands."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.version_info < (3, 9):
    sys.stderr.write("Orbit Desktop needs Python 3.9 or newer.\n")
    sys.exit(1)

from orbitcore.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
