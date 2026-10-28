#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independently rounded pinned MPFR versus exact Fraction integer targets."""
import argparse
from pathlib import Path
import sys
import struct
import gmpy2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from current_ir_reference import payloads, layout, MASK, SEED, COUNT
from gen_corpus_float_scale import publish_set

def verify(raw,width,targets):
 p,bias,eb=layout(width)
 if (raw&((1<<(width-1))-1))>=((1<<eb)-1)<<p:return
 modes=[gmpy2.RoundToNearest,gmpy2.RoundDown,gmpy2.RoundUp,gmpy2.RoundToZero]
 for mode,rounding in enumerate(modes):
  with gmpy2.context(precision=1200,emin=-100000,emax=100000,round=rounding):
   x=gmpy2.mpfr(struct.unpack('>d' if width==64 else '>f',raw.to_bytes(width//8,'big'))[0])
   n=int(gmpy2.rint(x))
  for offset,bits in enumerate([32,64]):
   invalid=not -(1<<(bits-1))<=n<(1<<(bits-1))
   observed=[(-(1<<(bits-1)) if invalid else n)&MASK,1 if invalid else (2 if x!=n else 0)]
   if observed!=targets[mode*2+offset]:raise RuntimeError('Fraction/MPFR current integer target differs at%x'%raw)

def publication_controls():
 import tempfile
 from unittest import mock
 for existing in (False,True):
  for failure in range(7):
   with tempfile.TemporaryDirectory(prefix='currentint-publish-') as t:
    root=Path(t);data={'item%d'%i:'new%d'%i for i in range(7)}
    if existing:
     for name in data:(root/name).write_text('old');(root/name).chmod(0o640)
    original=Path.replace;calls=0
    def replace(path,target):
     nonlocal calls
     if path.name.startswith('new'):
      calls+=1
      if calls==failure+1:raise OSError('currentint injected publication failure')
     return original(path,target)
    try:
     with mock.patch.object(Path,'replace',replace):publish_set(root,data)
    except OSError as e:
     if 'currentint injected' not in str(e):raise
    else:raise RuntimeError('publication failure escaped')
    for name in data:
     if existing:
      if (root/name).read_text()!='old' or (root/name).stat().st_mode&0o777!=0o640:raise RuntimeError('publication rollback changed destination')
     elif (root/name).exists():raise RuntimeError('publication rollback left destination')
    if any(p.name.startswith('.float-scale-set.') for p in root.iterdir()):raise RuntimeError('publication staging leaked')
 for existing in (False,True):
  with tempfile.TemporaryDirectory(prefix='currentint-publish-positive-') as t:
   root=Path(t);data={'item%d'%i:'new%d'%i for i in range(7)}
   if existing:
    for name in data:(root/name).write_text('old');(root/name).chmod(0o640)
   publish_set(root,data)
   for name,text in data.items():
    if (root/name).read_text()!=text or (root/name).stat().st_mode&0o777!=(0o640 if existing else 0o644):raise RuntimeError('positive publication content/mode differs')
 print('currentint publication positive2/rollback14 cases pass; set is not crash-atomic')

def main():
 if gmpy2.version()!='2.3.2' or gmpy2.mpfr_version().split()[-1]!='4.2.2':raise RuntimeError('current integer oracle pin differs')
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);p.add_argument('--seed',type=int,default=SEED);p.add_argument('--count',type=int,default=COUNT);p.add_argument('--fresh',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:publication_controls();return
 if a.out is None:p.error('--out is required')
 data=payloads(a.seed,a.count,a.fresh,verify);a.out.mkdir(parents=True,exist_ok=True);publish_set(a.out,data)
 print('current integer Fraction/MPFR four-mode targets agree and publish')
if __name__=='__main__':main()
