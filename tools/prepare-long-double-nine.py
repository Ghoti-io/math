#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Reconstruct only missing pinned integer-arithmetic state grids.

Answers come exclusively from compact committed per-input literals; state
expansion is deterministic. An existing corrupt cache fails without repair.
The separate Fraction gate recomputes every expanded answer independently.
"""
import sys
if not __debug__ or sys.flags.optimize:
    raise SystemExit("long-double nine gates require assertion-enabled Python")

import argparse, importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('nine',Path(__file__).with_name('check-long-double-nine.py'))
nine=importlib.util.module_from_spec(spec);spec.loader.exec_module(nine)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=Path('tests/corpus'));args=parser.parse_args()
    meta=nine.prepare(args.directory)
    print(f'long-double nine cache: {meta["literal_cells"]} literal answer cells / {meta["rows"]} expanded rows / {meta["bytes"]} bytes pinned')
