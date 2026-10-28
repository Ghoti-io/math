#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent struct-decoded pinned MPFR versus exact Fraction differences.

Numerical targets are independently rounded by MPFR. Exception classes are
explicit library contracts, not claims about MPFR's exception instrumentation.
"""
import argparse
from pathlib import Path
import struct
import sys
import gmpy2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from positive_difference_reference import payloads, layout, SEED, COUNT
from gen_corpus_float_scale import publish_set

def verify(x,y,width,result,flags):
 p,bias,eb=layout(width);mask=(1<<(width-1))-1;inf=((1<<eb)-1)<<p
 if (x&mask)>inf or (y&mask)>inf:return
 fmt='>d' if width==64 else '>f'
 with gmpy2.context(precision=1200,emin=-100000,emax=100000,round=gmpy2.RoundToNearest):
  a=gmpy2.mpfr(struct.unpack(fmt,x.to_bytes(width//8,'big'))[0])
  b=gmpy2.mpfr(struct.unpack(fmt,y.to_bytes(width//8,'big'))[0])
 if a<=b:other=0
 elif gmpy2.is_infinite(a) or gmpy2.is_infinite(b):other=inf
 else:
  with gmpy2.context(precision=p+1,emin=2-bias-p,emax=bias+1,subnormalize=True,round=gmpy2.RoundToNearest):
   r=gmpy2.sub(a,b)
  other=inf if gmpy2.is_infinite(r) else int.from_bytes(struct.pack(fmt,float(r)),'big')
 if other!=result:raise RuntimeError('positive difference Fraction/MPFR target differs width%d x%x y%x'%(width,x,y))

def publication_controls():
 import tempfile
 from unittest import mock
 for existing in (False,True):
  for failure in range(5):
   with tempfile.TemporaryDirectory(prefix='fdim-publish-') as t:
    root=Path(t);data={'item%d'%i:'new%d'%i for i in range(5)}
    if existing:
     for name in data:(root/name).write_text('old');(root/name).chmod(0o640)
    original=Path.replace;calls=0
    def replace(path,target):
     nonlocal calls
     if path.name.startswith('new'):
      calls+=1
      if calls==failure+1:raise OSError('positive difference injected publication failure')
     return original(path,target)
    try:
     with mock.patch.object(Path,'replace',replace):publish_set(root,data)
    except OSError as e:
     if 'positive difference injected' not in str(e):raise
    else:raise RuntimeError('publication failure escaped')
    for name in data:
     if existing:
      if (root/name).read_text()!='old' or (root/name).stat().st_mode&0o777!=0o640:raise RuntimeError('publication rollback changed destination')
     elif (root/name).exists():raise RuntimeError('publication rollback left destination')
    if any(p.name.startswith('.float-scale-set.') for p in root.iterdir()):raise RuntimeError('publication staging leaked')
 for existing in (False,True):
  with tempfile.TemporaryDirectory(prefix='fdim-publish-positive-') as t:
   root=Path(t);data={'item%d'%i:'new%d'%i for i in range(5)}
   if existing:
    for name in data:(root/name).write_text('old');(root/name).chmod(0o640)
   publish_set(root,data)
   for name,text in data.items():
    if (root/name).read_text()!=text or (root/name).stat().st_mode&0o777!=(0o640 if existing else 0o644):raise RuntimeError('positive publication content/mode differs')
 print('positive difference publication positive2/rollback10 cases pass; set is not crash-atomic')

def main():
 if gmpy2.version()!='2.3.2' or gmpy2.mpfr_version().split()[-1]!='4.2.2':raise RuntimeError('positive difference oracle pin differs')
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);p.add_argument('--seed',type=int,default=SEED);p.add_argument('--count',type=int,default=COUNT);p.add_argument('--fresh',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:publication_controls();return
 if a.out is None:p.error('--out is required')
 data=payloads(a.seed,a.count,a.fresh,verify);a.out.mkdir(parents=True,exist_ok=True);publish_set(a.out,data)
 print('positive difference Fraction/pinned MPFR numerical targets agree and publish; flags derive from explicit contracts')
if __name__=='__main__':main()
