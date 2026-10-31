#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Source-linked unary guards/index/range certificate, NOT global accuracy proof.

The old kernel's fitted approximation/evaluation one-ULP contract remains
measurement-supported. These assertions certify the new guard mathematics,
constant cell, index safety and necessary finite-range conditions. Source
fingerprints bind the reviewed operation model, not formal C/compiler proof.
"""
if not __debug__:
    raise SystemExit("atan budget certificate requires assertions; run without -O/PYTHONOPTIMIZE")
import argparse
import hashlib
from pathlib import Path
import re
import sys
from fractions import Fraction
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from atan_reference import fraction,power,round_word,TINY,LARGE,PIO2
import gmpy2
ROOT=Path(__file__).resolve().parents[2]
SOURCE_SHA='4ef33fb237df7ff5c2d3d42ec2cc41a3a5ce341781cc2d087c70a36990a0ec16'
KERNEL_SHA='3ab8d1a6d0a6679ccccc10c56b6c2b3dd022b127605f643ec378f6eb23ec168e'
HELPER_SHA='1c5133eec6e6d4c8016779f9575e84c45d212d3b8ffc94fa36f6cbf7d0596992'
TABLE_SHA='cc6a484780baaeb2995ac3f8ac4922faec02ca4d9d85a876a94a3f094167a130'

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'src/elementary/atan.c');p.add_argument('--kernel',type=Path,default=ROOT/'src/elementary/atan2.c');p.add_argument('--table',type=Path,default=ROOT/'src/elementary/atan2_table.h');p.add_argument('--helper',type=Path,default=ROOT/'src/elementary/elem_common.h');a=p.parse_args()
 assert gmpy2.mpfr_version()=='MPFR 4.2.2' and gmpy2.version()=='2.3.2','atan certificate dependency pin'
 for path,expected in [(a.source,SOURCE_SHA),(a.kernel,KERNEL_SHA),(a.table,TABLE_SHA),(a.helper,HELPER_SHA)]:
  assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,'atan source applicability: '+path.name
 assert fraction(TINY)==power(-30) and fraction(LARGE)==power(54)
 assert PIO2==0x3ff921fb54442d18
 # For normal x, the nearest-cell half width toward zero is >=x*2^-54,
 # including predecessor spacing at powers of two. Subnormal half cells
 # are fixed at2^-1075. The following are uniform strict upper bounds.
 assert power(-60+54)/3 < 1,'atan tiny nearest cell'
 assert power(-3066)/3 < power(-1075),'atan subnormal nearest cell'
 # Signed-error zero enclosure for input<2^-104; use predecessor-binade
 # spacing conservatively even when the input is an exact power of two.
 assert power(-154)/3 < power(-150),'atan tiny signed-error cell'
 assert power(-1992)/3 < power(-150)
 bounds=[]
 for mode in [gmpy2.RoundDown,gmpy2.RoundUp]:
  with gmpy2.context(precision=1200,round=mode):
   value=gmpy2.const_pi()/2;n,d=value.as_integer_ratio();bounds.append(Fraction(int(n),int(d)))
 low,high=bounds;center=fraction(PIO2);half=power(-53)
 assert center-half < low-power(-54) and high < center+half,'atan large nearest cell'
 assert round_word(low)==PIO2 and round_word(high)==PIO2
 # Unary operands give qa=x exactly below one or round(1/x)<=1 above one.
 # Multiplication by64 is exact. The magic addition is monotone in each
 # mode and the endpoint atqa=1 is exact, so j cannot exceed64.
 for mode in [gmpy2.RoundToNearest,gmpy2.RoundDown,gmpy2.RoundUp,gmpy2.RoundToZero]:
  with gmpy2.context(precision=53,round=mode):
   for q in [gmpy2.mpfr(1)/8,gmpy2.mpfr(1)]:
    t=q*64+gmpy2.mpfr(float.fromhex('0x1.8p52'))
    index=int(t-gmpy2.mpfr(float.fromhex('0x1.8p52')))
    assert 8<=index<=64,'atan unary index endpoints'
 # Necessary range conditions for the separately reviewed flag model:
 # tiny quotient branch has q>=2^-54; direct polynomial q>=2^-30,
 # while table q>=1/8 gives v<=8 and nonzero beta>=2^-62.
 assert power(-54)>power(-1022)
 assert power(-240-80)>power(-1022)
 assert power(-62*8-80)>power(-1022)
 table=a.table.read_text();values=[float.fromhex(x) for x in re.findall(r'[-+]?0x[0-9a-f.]+p[-+][0-9]+',table)]
 nonzero=[abs(v) for v in values if v]
 assert nonzero and min(nonzero)>float.fromhex('0x1p-80'),'atan stored constant range'
 print('PASS: atan tiny/large guards, directed constant cell, unary index0..64 and finite-range model; NO global approximation/evaluation proof')
if __name__=='__main__':main()
