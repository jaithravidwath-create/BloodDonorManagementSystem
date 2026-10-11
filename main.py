#!/usr/bin/env python3
"""Entry point:  python main.py [--demo] [--db PATH]"""
import sys

from bdms.cli import main

if __name__ == "__main__":
    sys.exit(main())
