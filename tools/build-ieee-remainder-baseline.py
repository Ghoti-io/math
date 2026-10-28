#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Rebuild the own-project pre-optimization IEEE remainder family, without modifying Git.

Compile with the current caller-supplied library arguments, then rename only
its four public symbols. Metadata identifies declared source and actual build bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
from adjacent_baseline import compiler_digest,digest_file,flags_digest
REVISION='a54cfbacafa735c0bc7fd1a56af869b8877fa501'

def run(args):
    return subprocess.check_output(args,stderr=subprocess.STDOUT,timeout=120)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--cc',required=True);p.add_argument('--flags',required=True)
    p.add_argument('--nm',default='nm');p.add_argument('--objcopy',default='objcopy');a=p.parse_args()
    if run(['git','rev-parse',REVISION+'^{commit}']).decode().strip()!=REVISION:raise RuntimeError('prior revision unavailable')
    source=run(['git','show',REVISION+':src/elementary/ieee_remainder.c'])
    helper=run(['git','show',REVISION+':src/elementary/elem_common.h'])
    if helper!=Path('src/elementary/elem_common.h').read_bytes():raise RuntimeError('current helper differs from prior source')
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'ieee_remainder.c').write_bytes(source);(a.out/'elem_common.h').write_bytes(helper)
    public=a.out/'public.o';prior=a.out/'prior.o'
    cc=shlex.split(a.cc);flags=shlex.split(a.flags)
    run(cc+flags+['-c',str(a.out/'ieee_remainder.c'),'-o',str(public)])
    def symbols(path):
        return [line.split()[-1] for line in run(shlex.split(a.nm)+['-g','--defined-only',str(path)]).decode().splitlines() if line.strip() and not line.split()[-1].startswith(('__x86.get_pc_thunk.','__sparc_get_pc_thunk.'))]
    names=symbols(public)
    functions=('remainder','remainderf','remquo','remquof')
    if len(names)!=4:raise RuntimeError('unexpected public symbol count')
    renames=[]
    for function in functions:
        found=[name for name in names if name.endswith('_gmath_'+function)]
        if len(found)!=1:raise RuntimeError('unexpected public symbol: '+function)
        renames+=['--redefine-sym',found[0]+'=gmath_ieee_prior_'+function]
    run(shlex.split(a.objcopy)+renames+[str(public),str(prior)])
    if sorted(symbols(prior))!=sorted('gmath_ieee_prior_'+f for f in functions):raise RuntimeError('prior public symbol rename failed')
    metadata=dict(revision=REVISION,object_sha256=digest_file(prior),flags_sha256=flags_digest(flags),compiler_sha256=compiler_digest(a.cc),source_sha256=hashlib.sha256(source).hexdigest(),helper_sha256=hashlib.sha256(helper).hexdigest(),compiler_command=cc,library_arguments=flags)
    Path(str(prior)+'.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('IEEE remainder prior object rebuilt from '+REVISION+': '+str(prior))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        output=getattr(error,'output',None)
        if output:print(output.decode(errors='replace')[-4000:] if isinstance(output,bytes) else output[-4000:],file=sys.stderr)
        raise SystemExit('IEEE remainder baseline build: FAIL: '+str(error))
