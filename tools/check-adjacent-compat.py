#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Account for disjoint result-only adjacent-value compatibility intervals.

Default samples all32-bit source patterns in all modes with seven target
classes. --exhaustive scans every raw Float source toward both infinities
under nearest; it is not an independent accuracy/flag proof.
"""
import argparse
import contextlib
import sys
import io
import os
import tempfile
import json
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
from pathlib import Path
import subprocess
import threading
from adjacent_baseline import load as load_baseline, identity_line, flags_digest, compiler_digest, digest_file, validate as validate_baseline, write_header

END=0x100000000


def check(binary,start,end,step,targets,mode,timeout,stopped,active,lock,identity):
    with lock:
        if stopped.is_set():raise RuntimeError('compatibility scan cancelled after another failure')
        process=subprocess.Popen([str(binary),str(start),str(end),str(step),str(targets),str(mode)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        active.add(process)
    try:
        try:stdout,stderr=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            process.kill();process.communicate()
            raise RuntimeError('compatibility interval timed out after %gs; no result mismatch established: %r'%(timeout,(start,end,step,targets,mode))) from error
    finally:
        with lock:active.discard(process)
    count=((end-start-1)//step+1)*targets.bit_count()
    expected=identity+'adjacent.compare %d %d %d %d %d %d\n'%(start,end,step,targets,mode,count)
    if process.returncode or stdout!=expected or stderr:
        reason='result mismatch' if 'adjacent mismatch input' in stderr else 'probe/coverage failure'
        raise RuntimeError('compatibility '+reason+': '+repr((start,end,step,targets,mode))+'\n'+(stdout+stderr)[-4000:])
    print('  ok   adjacent interval %d..%d step%d targets%d mode%d count%d'%(start,end,step,targets,mode,count),flush=True)
    return count


def scan(binary,intervals,jobs,timeout,identity):
    stopped=threading.Event();active=set();lock=threading.Lock();total=0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures=[pool.submit(check,binary,*interval,timeout,stopped,active,lock,identity) for interval in intervals]
        try:
            for future in as_completed(futures):total+=future.result()
        except BaseException:
            with lock:
                stopped.set();processes=list(active)
            for future in futures:future.cancel()
            for process in processes:
                if process.poll() is None:
                    try:process.terminate()
                    except ProcessLookupError:pass
            for process in processes:
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait()
            raise
    return total


def sample_intervals():
    centers=(0,1,0x007fffff,0x00800000,0x3f800000,0x7f7fffff,0x7f800000,0x7f800001,0x7fc00000,0x7fffffff)
    windows=sorted((max(0,(word|sign)-2),min(END,(word|sign)+3)) for word in centers for sign in (0,0x80000000))
    merged=[]
    for start,end in windows:
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],end))
        else:merged.append((start,end))
    return [(0,END,65537,127,mode) for mode in range(4)]+[(start,end,1,127,mode) for start,end in merged for mode in range(4)]


def calibrate():
    with tempfile.TemporaryDirectory(prefix='adjacent-compat-controls-') as temporary:
        directory=Path(temporary);binary=directory/'fake-probe'
        metadata={'revision':'0'*40,'object_sha256':'1'*64,'flags_sha256':'2'*64,'compiler_sha256':'3'*64}
        identity=identity_line(metadata)
        prefix='#!/usr/bin/env python3\nimport os,sys,time\nfrom pathlib import Path\na,b,step,targets,mode=map(int,sys.argv[1:])\ncount=((b-a-1)//step+1)*targets.bit_count()\nIDENTITY='+repr(identity)+'\n'
        output="sys.stdout.write(IDENTITY)\nprint('adjacent.compare %d %d %d %d %d %d'%(a,b,step,targets,mode,count))\n"
        def write(code):binary.write_text(prefix+code);binary.chmod(0o755)
        def one(code,expected_error=None,timeout=2):
            write(code);active=set();lock=threading.Lock();stopped=threading.Event()
            try:
                with contextlib.redirect_stdout(io.StringIO()):check(binary,0,100,3,127,2,timeout,stopped,active,lock,identity)
            except RuntimeError as error:
                if expected_error is None or expected_error not in str(error):raise RuntimeError('wrong calibration failure: '+str(error)) from error
            else:
                if expected_error is not None:raise RuntimeError('calibration defect escaped')
            if active:raise RuntimeError('calibration left tracked children')
        one(output);print('  ok   adjacent compatibility metadata control passes',flush=True)
        for name,change in (('count','count+=1\n'),('interval','a+=1\n'),('target-mask','targets^=4\n'),('mode','mode=(mode+1)%4\n'),('stderr',"print('unexpected',file=sys.stderr)\n"),('baseline-identity',"IDENTITY=IDENTITY.replace('declared_revision ','wrong_revision ')\n")):
            one(change+output,'probe/coverage failure');print('  ok   adjacent compatibility wrong '+name+' detected',flush=True)
        one(output+'sys.exit(1)\n','probe/coverage failure')
        print('  ok   adjacent compatibility exit-status detected',flush=True)
        marker=directory/'timeout-pid'
        one('Path('+repr(str(marker))+').write_text(str(os.getpid()))\ntime.sleep(30)\n','timed out',timeout=0.1)
        if marker.exists():
            try:os.kill(int(marker.read_text()),0)
            except ProcessLookupError:pass
            else:raise RuntimeError('timeout child survived')
        print('  ok   adjacent compatibility timeout and child cleanup pass',flush=True)
        # Sleeping worker cannot complete naturally until the parent releases it.
        # Failure worker waits for its ready handshake before exiting; no short
        # wall-clock performance threshold is used to infer cancellation.
        handshake="root=Path("+repr(str(directory))+")\n(root/('late-'+str(mode))).write_text(str(os.getpid()))\nif mode==0:\n (root/'ready-0').touch()\n while not (root/'release').exists():time.sleep(0.01)\n (root/'natural-completion').touch()\nif mode==1:\n while not (root/'ready-0').exists():time.sleep(0.01)\n (root/'failure-ready').touch()\n sys.exit(1)\n"
        write(handshake+output)
        try:
            with contextlib.redirect_stdout(io.StringIO()):scan(binary,[(0,100,3,127,mode) for mode in range(4)],2,120,identity)
        except RuntimeError as error:
            if 'probe/coverage failure' not in str(error):raise
        else:raise RuntimeError('late failure escaped')
        if not (directory/'ready-0').exists() or not (directory/'failure-ready').exists() or (directory/'natural-completion').exists():raise RuntimeError('cancellation handshake/completion control failed')
        for marker in directory.glob('late-*'):
            try:os.kill(int(marker.read_text()),0)
            except ProcessLookupError:pass
            else:raise RuntimeError('cancelled child survived')
        (directory/'release').touch()
        print('  ok   adjacent compatibility completion-order handshake/cancellation/child cleanup pass',flush=True)
        # Identity verification binds object/build bytes, not arbitrary source claims.
        obj=directory/'object';obj.write_bytes(b'controlled baseline object')
        compiler_command=shlex.quote(sys.executable)
        fields={'revision':'0'*40,'object_sha256':digest_file(obj),'flags_sha256':flags_digest('-std=c17 -O2'),'compiler_sha256':compiler_digest(compiler_command)}
        path=directory/'baseline.json';path.write_text(json.dumps(fields));loaded=load_baseline(path)
        validate_baseline(loaded,obj,'-std=c17 -O2',compiler_command);write_header(directory/'identity.h',loaded)
        for name in ('object','flags','compiler','revision'):
            changed=dict(fields)
            if name=='object':changed['object_sha256']='0'*64
            elif name=='flags':changed['flags_sha256']='0'*64
            elif name=='compiler':changed['compiler_sha256']='0'*64
            else:changed['revision']='invalid'
            path.write_text(json.dumps(changed))
            try:validate_baseline(load_baseline(path),obj,'-std=c17 -O2',compiler_command)
            except RuntimeError:pass
            else:raise RuntimeError('baseline identity control escaped '+name)
        print('  ok   adjacent baseline object/flags/compiler/identity controls pass',flush=True)
        executable=Path(sys.executable)
        alternative=str(executable.parent/'..'/executable.parent.name/executable.name)
        if compiler_digest(compiler_command)==compiler_digest(shlex.quote(alternative)):raise RuntimeError('compiler invocation name omitted from identity')
        print('  ok   adjacent compiler invocation-name identity control passes',flush=True)
        required=(1,0x007fffff,0x00800000,0x7f7fffff,0x80000001,0x807fffff,0x80800000,0xff7fffff)
        intervals=sample_intervals()
        if not all(any(step==1 and start<=word<end and mode==0 for start,end,step,targets,mode in intervals) for word in required):raise RuntimeError('boundary strata omit required sources')
        print('  ok   adjacent explicit boundary strata contain required sources',flush=True)
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path,nargs='?');parser.add_argument('--calibrate',action='store_true')
    parser.add_argument('--baseline-metadata',type=Path);parser.add_argument('--exhaustive',action='store_true')
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--timeout',type=float,default=1800,help='positive finite per-interval seconds; increase for slow targets')
    args=parser.parse_args()
    if not 1<=args.jobs<=32:parser.error('--jobs must be in1..32')
    if not math.isfinite(args.timeout) or args.timeout<=0:parser.error('--timeout must be positive and finite')
    if args.calibrate:return calibrate()
    if args.binary is None:parser.error('a comparison binary is required')
    if args.baseline_metadata is None:parser.error('--baseline-metadata is required')
    identity=identity_line(load_baseline(args.baseline_metadata));print(identity,end='',flush=True)
    binary=args.binary.resolve()
    intervals=sample_intervals()
    if args.exhaustive:
        intervals=[(END*i//32,END*(i+1)//32,1,3,0) for i in range(32)]
        if intervals[0][0]!=0 or intervals[-1][1]!=END or any(a[1]!=b[0] for a,b in zip(intervals,intervals[1:])):
            raise RuntimeError('incomplete/overlapping exhaustive intervals')
    total=scan(binary,intervals,args.jobs,args.timeout,identity)
    expected=2*END if args.exhaustive else sum(((end-start-1)//step+1)*targets.bit_count() for start,end,step,targets,mode in intervals)
    if total!=expected:raise RuntimeError('compatibility total differs from required coverage')
    unit='source/direction result pairs (all 2^32 source patterns)' if args.exhaustive else 'source/target/mode evaluations (strata may overlap)'
    print('adjacent compatibility: %d %s; %s; result-only, not reference accuracy/flags'%(total,unit,'exhaustive nearest' if args.exhaustive else 'stratified all-mode sample'),flush=True)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,RuntimeError,ValueError) as error:raise SystemExit('check-adjacent-compat: FAIL: '+str(error))
