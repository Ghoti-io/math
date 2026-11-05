#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
import importlib.util
from pathlib import Path
z=importlib.util.spec_from_file_location('eleven',Path(__file__).with_name('check-long-double-eleven.py'))
m=importlib.util.module_from_spec(z);z.loader.exec_module(m)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('tests/corpus'));a=p.parse_args()
    print('long-double eleven cache cells',len(m.prepare(a.directory)['cells']))
