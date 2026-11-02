#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Required pinned independent instrument, named deadline and finally cleanup."""
import sys
if sys.flags.optimize:
 raise SystemExit('remaining-fifteen: optimized Python execution is unsupported')
import argparse,os,subprocess,signal,uuid
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--seed',type=int,default=20261109);p.add_argument('--count',type=int,default=128);a=p.parse_args()
root=Path(__file__).resolve().parents[1];engine=os.environ.get('GHOTI_CONTAINER_ENGINE','podman');pin=next(line.split('\t') for line in (root/'tools/oracle/containers/IMAGES').read_text().splitlines() if line.startswith('mpfr\t'));ref,version=pin[1:3]
def invoke(args,capture=False):
 name='gmath-remaining-oracle-'+uuid.uuid4().hex[:12]
 cmd=[engine,'run','--rm','--name',name,'--cgroups=disabled','--cgroupns=host','--timeout=7200','--userns=keep-id','-v',str(root)+':'+str(root)+':z','-w',str(root),ref]+args
 try:return subprocess.run(cmd,check=True,capture_output=capture,text=True,timeout=7230)
 finally:subprocess.run([engine,'rm','-f',name],capture_output=True,timeout=20)
for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,lambda s,f:(_ for _ in ()).throw(SystemExit(128+s)))
assert invoke(['mpfr-version'],True).stdout.strip()==version,'independent instrument version differs'
invoke(['python3','tools/oracle/gen_corpus_remaining.py','--out',str(a.out.resolve()),'--seed',str(a.seed),'--count',str(a.count)])
