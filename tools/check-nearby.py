#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Mandatory complete reference SHA and independently reconstructed exact population."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
from nearby_reference import payloads,coverage
EXPECTED={'nearbyint-special.corpus': 'fd3ba2b79a8c5d87121cde5a63c302c82a503d3ada7d1229372f6e60d4dc8540', 'nearbyintf-special.corpus': 'daf40af024db6c747e6a8ec0f4a2228cc3c83420e3e10fbc0a055de942c5305a', 'nearbyint.corpus': '53da89bb24063cb6410723966ffd5ebd470a2ec4192392f4afc341decae0e6c9', 'nearbyintf.corpus': '7401f2ff57d61fb753dcf8da6831ab2ec0d9dc990ff3c349498ad015244cd428', 'nearby-special.hash': '7d39fcb5ad87c52a350c176efd4033537b83041610d620f83f1b9a37fbdd8bf2'}
def check(root,seed,count,fresh,pinned=True):
 data=payloads(seed,count,fresh)
 for name,text in data.items():
  path=root/name
  if path.stat().st_size>32*1024*1024:raise RuntimeError('nearby payload exceeds bound')
  observed=path.read_bytes()
  if pinned and hashlib.sha256(observed).hexdigest()!=EXPECTED[name]:raise RuntimeError('nearby complete checksum differs: '+name)
  if name.endswith('-special.corpus'):
   coverage((int(line.split()[0],16) for line in observed.decode().splitlines() if not line.startswith('#')),64 if name=='nearbyint-special.corpus' else 32)
  if observed!=text.encode():raise RuntimeError('nearby complete population/target/widening differs: '+name)
 return data

def probe(command,root,data):
 p=subprocess.run(command+[str(root)],capture_output=True,text=True,timeout=120)
 expected=''.join(line+' from '+str(root)+'\n' for line in data['nearby-special.hash'].splitlines())
 if p.returncode or p.stderr or p.stdout!=expected:raise RuntimeError('nearby probe output/state/count/path differs: '+p.stdout[-250:]+p.stderr[-250:])

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path);p.add_argument('--directory',type=Path,default=Path('tests/corpus'));p.add_argument('--seed',type=int,default=20261028);p.add_argument('--count',type=int,default=2000);p.add_argument('--fresh',action='store_true');a=p.parse_args()
 data=check(a.directory,a.seed,a.count,a.fresh,not a.fresh)
 if a.probe:probe([str(a.probe.resolve())],a.directory,data)
 print('nearby complete SHA/exact population/widening and compiled state checks pass')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('nearby checks: FAIL: '+str(e))
