#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Native actual-reference positives, wrong-reference and alias-guard controls."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from adjacent_baseline import load, validate, identity_line, write_header, digest_file, flags_digest, compiler_digest


def run(args,log):
    with log.open('w') as output:
        result=subprocess.run(args,stdout=output,stderr=subprocess.STDOUT,check=False,timeout=60)
    return result.returncode,log.read_text()


def main():
    env=os.environ;work=Path(env['NATIVE_WORK']);work.mkdir(parents=True,exist_ok=True)
    cc=shlex.split(env['NATIVE_CC']);tool_flags=shlex.split(env['NATIVE_CFLAGS']);library_flags=shlex.split(env['NATIVE_LIB_CFLAGS']);ldflags=shlex.split(env['NATIVE_LDFLAGS'])
    archive=Path(env['NATIVE_LIBRARY']);prior=Path(env['NATIVE_REFERENCE']);metadata=load(env['NATIVE_METADATA'])
    validate(metadata,prior,env['NATIVE_LIB_CFLAGS'],env['NATIVE_CC'])
    good_header=work/'good.identity.h';write_header(good_header,metadata)
    bad_source=work/'wrong.c';bad_source.write_text('double gmath_adjacent_prior_nextafter(double x,double y) {(void)x;(void)y;return 0.0;}\nfloat gmath_adjacent_prior_nextafterf(float x,float y) {(void)x;(void)y;return 0.0f;}\n')
    bad_object=work/'wrong.o';status,text=run(cc+library_flags+['-c',str(bad_source),'-o',str(bad_object)],work/'wrong-build.log')
    if status:raise RuntimeError('wrong-reference fixture did not compile: '+text)
    bad_meta={'revision':'f'*40,'object_sha256':digest_file(bad_object),'flags_sha256':flags_digest(library_flags),'compiler_sha256':compiler_digest(env['NATIVE_CC'])}
    (work/'wrong.o.json').write_text(json.dumps(bad_meta,sort_keys=True)+'\n');bad_header=work/'wrong.identity.h';write_header(bad_header,bad_meta)
    configurations=(('valid',prior,good_header,False),('wrong',bad_object,bad_header,False),('alias',prior,good_header,True))
    for label,object_path,header,alias in configurations:
        for kind,source in (('compare','tools/compare-adjacent.c'),('raw','tools/probe-adjacent.c'),('bench','tools/bench-adjacent.c')):
            double='gmath_nextafter' if alias else 'gmath_adjacent_prior_nextafter';single='gmath_nextafterf' if alias else 'gmath_adjacent_prior_nextafterf'
            stem='BASELINE' if kind=='bench' else 'REFERENCE'
            defines=['-DGMATH_NEXTAFTER_'+stem+'='+double,'-DGMATH_NEXTAFTERF_'+stem+'='+single]
            binary=work/(label+'-'+kind)
            status,text=run(cc+tool_flags+['-include',str(header)]+defines+['-o',str(binary),source,str(archive),str(object_path)]+ldflags+['-lm'],work/(label+'-'+kind+'-build.log'))
            if status:raise RuntimeError('native control compile failed '+label+'/'+kind+': '+text)
            args=[str(binary)]+(['0','100','1','127','0'] if kind=='compare' else [])
            status,text=run(args,work/(label+'-'+kind+'.log'))
            if label=='valid':
                if status or identity_line(metadata).strip() not in text:raise RuntimeError('valid native reference control failed '+kind+': '+text[-2000:])
            elif label=='alias':
                if status!=2 or 'aliases' not in text:raise RuntimeError('native alias guard escaped '+kind)
            else:
                expected=2 if kind=='bench' else 1
                diagnostic='adjacent mismatch input' if kind=='compare' else (' prior ' if kind=='raw' else 'baseline-bit guard failed')
                if status!=expected or diagnostic not in text:raise RuntimeError('native wrong reference escaped/wrong failure '+kind+': '+text[-2000:])
            print('  ok   adjacent native '+label+'/'+kind+(' passes' if label=='valid' else ' detected'),flush=True)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (RuntimeError,OSError,KeyError,ValueError,subprocess.SubprocessError) as error:raise SystemExit('adjacent native controls: FAIL: '+str(error))
