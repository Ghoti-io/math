#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Calibrate declared baseline byte/context binding; not numerical/source proof."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from adjacent_baseline import compiler_digest, digest_file, flags_digest
from currentint_baseline import REVISION, identity, compiler_identity

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cc',required=True);p.add_argument('--flags',required=True);a=p.parse_args()
 configured=a.cc;rejected=None
 try:compiler_identity(configured)
 except RuntimeError as error:
  if 'wrapper' not in str(error):raise
  rejected=str(error);a.cc=sys.executable
  print('currentint configured wrapper is unsupported by optional baseline tools; default accounting calibration uses a direct Python executable')
 with tempfile.TemporaryDirectory(prefix='currentint-identity-') as tmp:
  root=Path(tmp);obj=root/'object';obj.write_bytes(b'identity control bytes, not a numerical baseline\n');meta=root/'metadata.json';out=root/'identity.h'
  good=dict(revision=REVISION,object_sha256=digest_file(obj),compiler_sha256=compiler_digest(a.cc),flags_sha256=flags_digest(a.flags))
  def call(data,cc=a.cc,flags=a.flags,want=None):
   meta.write_text(json.dumps(data));before=out.read_bytes() if out.exists() else None
   command=[sys.executable,'tools/currentint_baseline.py',str(obj),str(meta),'--cc='+cc,'--flags='+flags,'--header',str(out)]
   r=subprocess.run(command,capture_output=True,text=True,timeout=30)
   if want is None:
    if r.returncode or r.stderr or r.stdout!=identity(data) or json.dumps(identity(data)) not in out.read_text():raise RuntimeError('positive identity control differs')
   elif r.returncode!=1 or r.stdout or want not in r.stderr or (out.read_bytes() if out.exists() else None)!=before:raise RuntimeError('negative identity control differs: '+str(want))
  call(good)
  if rejected:call(good,cc=configured,want=rejected)
  out.chmod(0o755);call(good)
  if out.stat().st_mode&0o777!=0o755:raise RuntimeError('identity publication loses executable permission')
  for key,diagnostic in [('revision','revision differs'),('object_sha256','object digest differs'),('compiler_sha256','compiler identity differs'),('flags_sha256','library flags identity differs')]:
   wrong=dict(good);wrong[key]='0'*len(wrong[key]);call(wrong,want=diagnostic)
  wrong=dict(good);wrong.pop('object_sha256');call(wrong,want='invalid baseline identity field')
  wrong=dict(good);wrong['revision']='not-a-revision';call(wrong,want='invalid baseline identity field')
  call(good,flags=a.flags+' -DGMATH_IDENTITY_CONTROL',want='library flags identity differs')
  call(good,cc=a.cc+' -DGMATH_IDENTITY_CONTROL',want='single compiler executable')
  wrapper=root/'ccache';wrapper.write_text('#!/bin/sh\nexit 99\n');wrapper.chmod(0o755)
  masquerade=root/'compiler';masquerade.symlink_to(wrapper)
  call(good,cc=str(masquerade),want='does not support compiler wrappers')
  obj.write_bytes(obj.read_bytes()+b'stale');call(good,want='object digest differs')
  leftovers=[v for v in root.iterdir() if v.name.startswith('.identity.h.')]
  if leftovers:raise RuntimeError('identity publication leaves temporary files')
 print('currentint baseline binding: positive publication and ten stale/context/schema/wrapper faults pass; accounting only')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('currentint baseline controls: FAIL: '+str(e))
