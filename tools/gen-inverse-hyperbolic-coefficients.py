#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Reuse our exact rational logarithm/ln2 derivation and check its tails."""
import argparse,re,runpy
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def content():
    derive=runpy.run_path(str(root/'tools/gen-log1p-expm1-coefficients.py'))
    text=derive['content']()
    text=re.sub(r'static const gmath_pair plus_exp_coeff\[25\] = \{.*?\};\n','',text,flags=re.S)
    return text.replace('gen-log1p-expm1-coefficients','gen-inverse-hyperbolic-coefficients').replace('GHOTI_IO_GMATH_LOG1P_EXPM1_COEFF_H','GHOTI_IO_GMATH_INVERSE_HYPERBOLIC_COEFF_H').replace('plus_','ih_')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();path=root/'src/elementary/inverse_hyperbolic_coeff.h'
    if a.check:
        if path.read_text()!=content():raise SystemExit('inverse hyperbolic coefficient drift')
    else:path.write_text(content())
