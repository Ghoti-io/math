#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Rebuild actual own prior integer conversions with caller-supplied exact library flags."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from adjacent_baseline import digest_file,flags_digest
from currentint_baseline import REVISION, compiler_identity

def run(args):return subprocess.check_output(args,stderr=subprocess.STDOUT,timeout=120)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',required=True);p.add_argument('--flags',required=True);p.add_argument('--nm',default='nm');p.add_argument('--objcopy',default='objcopy');p.add_argument('--revision',default=REVISION);a=p.parse_args()
 revision=run(['git','rev-parse',a.revision+'^{commit}']).decode().strip()
 if revision!=a.revision:raise RuntimeError('supply full canonical prior revision')
 source=run(['git','show',revision+':src/elementary/current_intround.c']);a.out.mkdir(parents=True,exist_ok=True);(a.out/'current_intround.c').write_bytes(source);helpers={}
 for name in ['elem_common.h','nearby_mode.h']:
  data=run(['git','show',revision+':src/elementary/'+name])
  if data!=Path('src/elementary',name).read_bytes():raise RuntimeError('current/prior helper differs: '+name)
  (a.out/name).write_bytes(data);helpers[name]=hashlib.sha256(data).hexdigest()
 compiler_identity(a.cc)
 cc=shlex.split(a.cc);flags=shlex.split(a.flags);public=a.out/'public.o';prior=a.out/'prior.o'
 run(cc+flags+['-c',str(a.out/'current_intround.c'),'-o',str(public)])
 def symbols(path):return [line.split()[-1] for line in run(shlex.split(a.nm)+['-g','--defined-only',str(path)]).decode().splitlines() if line.strip() and not line.split()[-1].startswith(('__x86.get_pc_thunk.','__sparc_get_pc_thunk.'))]
 names=symbols(public);families=['lrint','lrintf','llrint','llrintf'];renames=[]
 if len(names)!=4:raise RuntimeError('unexpected prior public symbol count')
 for family in families:
  matches=[name for name in names if name.endswith('_gmath_'+family)]
  if len(matches)!=1:raise RuntimeError('unexpected prior public symbol')
  prefix=matches[0][:len(matches[0])-len(matches[0].lstrip('_'))]
  renames+=['--redefine-sym',matches[0]+'='+prefix+'gmath_'+family+'_prior']
 run(shlex.split(a.objcopy)+renames+[str(public),str(prior)])
 if set(symbols(prior))!={name.split('=',1)[1] for name in renames[1::2]}:raise RuntimeError('prior rename result differs')
 metadata=dict(revision=revision,object_sha256=digest_file(prior),flags_sha256=flags_digest(flags),compiler_sha256=compiler_identity(a.cc),source_sha256=hashlib.sha256(source).hexdigest(),helpers_sha256=helpers,compiler_command=cc,library_arguments=flags)
 Path(str(prior)+'.json').write_text(json.dumps(metadata,indent=2)+'\n');print('currentint actual prior rebuilt from '+revision+': '+str(prior))
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('currentint prior build: FAIL: '+str(e)+'\n'+str(getattr(e,'output',''))[-3000:])
