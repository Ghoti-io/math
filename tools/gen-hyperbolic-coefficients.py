#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Reuse our exact rational exponential/ln2 derivation, without its log table."""
import argparse,re,runpy
from fractions import Fraction
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def content():
    # e>8/3 from the first five positive terms of its own Taylor series.
    # Thus 1-tanh(a)<2*exp(-2a) lies below half-spacing at both guards.
    for a,power in [(20,54),(10,25)]:
        if 2/Fraction(8,3)**(2*a)>=Fraction(2)**-power:
            raise RuntimeError('tanh saturation inequality failed')
    derive=runpy.run_path(str(root/'tools/gen-log1p-expm1-coefficients.py'))
    text=derive['content']() # exact exponential and ln2 tail inequalities checked
    text=re.sub(r'static const gmath_pair plus_log_coeff\[40\] = \{.*?\};\n','',text,flags=re.S)
    return text.replace('gen-log1p-expm1-coefficients','gen-hyperbolic-coefficients').replace('GHOTI_IO_GMATH_LOG1P_EXPM1_COEFF_H','GHOTI_IO_GMATH_HYPERBOLIC_COEFF_H').replace('plus_','hy_')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();path=root/'src/elementary/hyperbolic_coeff.h'
    if a.check:
        if path.read_text()!=content():raise SystemExit('hyperbolic coefficient drift')
    else:path.write_text(content())
