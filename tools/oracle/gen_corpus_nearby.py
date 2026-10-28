#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact Fraction floor/ceil/ties versus separately rounded pinned MPFR outputs."""
import argparse
from pathlib import Path
import sys
import gmpy2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nearby_reference import payloads,layout,value,bits
from gen_corpus_float_scale import publish_set

def verify(row,width):
 raw,*targets,flag=row;p,bias,eb=layout(width);sign=raw&1<<(width-1);inf=((1<<eb)-1)<<p
 if (raw&((1<<(width-1))-1))>=inf:return
 observed=[]
 for mode in [gmpy2.RoundToNearest,gmpy2.RoundDown,gmpy2.RoundUp,gmpy2.RoundToZero]:
  with gmpy2.context(precision=1200,emin=-100000,emax=100000,round=mode):
   x=gmpy2.mpfr(value(raw,width));r=gmpy2.rint(x)
   observed.append(bits(float(r),width) if r else sign)
 if tuple(observed)!=tuple(targets):raise RuntimeError('Fraction/MPFR nearby target differs at%x'%raw)

def publication_controls():
 import tempfile
 from unittest import mock
 for existing in (False,True):
  for failure in range(5):
   with tempfile.TemporaryDirectory(prefix='nearby-publish-') as t:
    root=Path(t);data={'item%d'%i:'new%d'%i for i in range(5)}
    if existing:
     for name in data:(root/name).write_text('old');(root/name).chmod(0o640)
    original=Path.replace;calls=0
    def replace(path,target):
     nonlocal calls
     if path.name.startswith('new'):
      calls+=1
      if calls==failure+1:raise OSError('nearby injected publication failure')
     return original(path,target)
    try:
     with mock.patch.object(Path,'replace',replace):publish_set(root,data)
    except OSError as e:
     if 'nearby injected' not in str(e):raise
    else:raise RuntimeError('publication failure escaped')
    for name in data:
     if existing:
      if (root/name).read_text()!='old' or (root/name).stat().st_mode&0o777!=0o640:raise RuntimeError('publication rollback changed destination')
     elif (root/name).exists():raise RuntimeError('publication rollback left destination')
    if any(p.name.startswith('.float-scale-set.') for p in root.iterdir()):raise RuntimeError('publication staging leaked')
 for existing in (False,True):
  with tempfile.TemporaryDirectory(prefix='nearby-publish-positive-') as t:
   root=Path(t);data={'item%d'%i:'new%d'%i for i in range(5)}
   if existing:
    for name in data:(root/name).write_text('old');(root/name).chmod(0o640)
   publish_set(root,data)
   for name,text in data.items():
    if (root/name).read_text()!=text or (root/name).stat().st_mode&0o777!=(0o640 if existing else 0o644):raise RuntimeError('positive publication content/mode differs')
 print('nearby publication positive2/rollback10 cases pass; set is not crash-atomic')

def main():
 if gmpy2.version()!='2.3.2' or gmpy2.mpfr_version().split()[-1]!='4.2.2':raise RuntimeError('nearby oracle version differs')
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);p.add_argument('--seed',type=int,default=20261028);p.add_argument('--count',type=int,default=2000);p.add_argument('--fresh',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:publication_controls();return
 if a.out is None:p.error('--out is required')
 data=payloads(a.seed,a.count,a.fresh,verify);a.out.mkdir(parents=True,exist_ok=True);publish_set(a.out,data)
 print('nearby Fraction/pinned MPFR four-mode targets agree and publish',flush=True)
if __name__=='__main__':main()
