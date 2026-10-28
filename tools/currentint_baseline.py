#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Bind declared own-project current-integer baseline build bytes, not source authenticity."""
import argparse
import json
from pathlib import Path
import tempfile
import shlex
import shutil
from adjacent_baseline import load, validate, FIELDS, compiler_digest
REVISION='68e71f73a26360700f529db886d332def2dc0f41'

def compiler_identity(command):
 # Do not pretend to bind the underlying compiler of an arbitrary wrapper.
 if len(shlex.split(command)) != 1:
  raise RuntimeError("currentint identity requires a single compiler executable; wrapper commands are unsupported")
 executable=shutil.which(shlex.split(command)[0])
 if executable and Path(executable).resolve().name in ('ccache','sccache','distcc','icecc'):
  raise RuntimeError("currentint identity does not support compiler wrappers")
 # This binds the selected executable, not arbitrary indirect toolchain bytes.
 return compiler_digest(command)

def identity(metadata):
 return 'currentint.baseline declared_revision %s object_sha256 %s flags_sha256 %s compiler_sha256 %s\n'%tuple(metadata[key] for key in FIELDS)

def header(path,metadata):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=None
 try:
  with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'.',delete=False) as out:
   temporary=Path(out.name);out.write('/* Caller-declared baseline identity, not source authentication. */\n#define GMATH_CURRENTINT_BASELINE_IDENTITY '+json.dumps(identity(metadata))+'\n')
  temporary.chmod(path.stat().st_mode&0o777 if path.exists() else 0o644);temporary.replace(path)
 finally:
  if temporary is not None:temporary.unlink(missing_ok=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('object',type=Path);p.add_argument('metadata',type=Path);p.add_argument('--cc',required=True);p.add_argument('--flags',required=True);p.add_argument('--header',type=Path,required=True);p.add_argument('--expected-revision',default=REVISION);a=p.parse_args()
 data=load(a.metadata)
 if data['revision']!=a.expected_revision:raise RuntimeError('currentint baseline revision differs')
 compiler_identity(a.cc)
 validate(data,a.object,a.flags,a.cc);header(a.header,data);print(identity(data),end='')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError) as e:raise SystemExit('currentint baseline: FAIL: '+str(e))
