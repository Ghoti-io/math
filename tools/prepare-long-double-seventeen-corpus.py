#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Authenticate compact committed references; no expanded cache is needed."""
import argparse,importlib.util,sys
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('seventeen corpus preparation requires assertion-enabled Python')
z=importlib.util.spec_from_file_location('seventeen_prepare',Path(__file__).with_name('check-long-double-seventeen.py'))
m=importlib.util.module_from_spec(z);z.loader.exec_module(m)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,default=Path('tests/corpus'));args=ap.parse_args()
 m.check_constants();_,summary=m.load(args.directory)
 print('seventeen compact references authenticated:',summary['cells'],'cells; no cache writes')
