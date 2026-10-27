#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Account for disjoint result-only atan f compatibility intervals.

Default samples both signs in all modes. --exhaustive scans every finite raw
Float encoding under nearest; it is not an independent accuracy/flag proof.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
from pathlib import Path
import subprocess
import threading

END=0x7f800000


def check(binary,start,end,step,signs,mode,timeout,stopped,active,lock):
    with lock:
        if stopped.is_set():raise RuntimeError('compatibility scan cancelled after another failure')
        process=subprocess.Popen([str(binary),str(start),str(end),str(step),str(signs),str(mode)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        active.add(process)
    try:
        try:stdout,stderr=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            process.kill();process.communicate()
            raise RuntimeError('compatibility interval timed out after %gs; no result mismatch established: %r'%(timeout,(start,end,step,signs,mode))) from error
    finally:
        with lock:active.discard(process)
    count=((end-start-1)//step+1)*((signs&1)+((signs>>1)&1))
    expected='atanf.compare %d %d %d %d %d %d\n'%(start,end,step,signs,mode,count)
    if process.returncode or stdout!=expected or stderr:
        reason='result mismatch' if 'atanf mismatch input' in stderr else 'probe/coverage failure'
        raise RuntimeError('compatibility '+reason+': '+repr((start,end,step,signs,mode))+'\n'+(stdout+stderr)[-4000:])
    print('  ok   atanf interval %d..%d step%d signs%d mode%d count%d'%(start,end,step,signs,mode,count),flush=True)
    return count


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path);parser.add_argument('--exhaustive',action='store_true')
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--timeout',type=float,default=1800,help='positive finite per-interval seconds; increase for slow targets')
    args=parser.parse_args()
    if not 1<=args.jobs<=32:parser.error('--jobs must be in1..32')
    if not math.isfinite(args.timeout) or args.timeout<=0:parser.error('--timeout must be positive and finite')
    binary=args.binary.resolve()
    intervals=[(0,END,65537,3,mode) for mode in range(4)]
    if args.exhaustive:
        intervals=[(END*i//32,END*(i+1)//32,1,3,0) for i in range(32)]
        if intervals[0][0]!=0 or intervals[-1][1]!=END or any(a[1]!=b[0] for a,b in zip(intervals,intervals[1:])):
            raise RuntimeError('incomplete/overlapping exhaustive intervals')
    stopped=threading.Event();active=set();lock=threading.Lock();total=0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures=[pool.submit(check,binary,*interval,args.timeout,stopped,active,lock) for interval in intervals]
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
    expected=2*END if args.exhaustive else 8*((END-1)//65537+1)
    if total!=expected:raise RuntimeError('compatibility total differs from required coverage')
    unit='signed finite encodings' if args.exhaustive else 'signed input/mode evaluations'
    print('atanf compatibility: %d %s; %s; result-only, not reference accuracy/flags'%(total,unit,'exhaustive nearest' if args.exhaustive else 'stratified all-mode sample'),flush=True)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,RuntimeError) as error:raise SystemExit('check-atanf-compat: FAIL: '+str(error))
