#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual pinned nearby target faults and real wrapper dispatch accounting."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('nearby_oracle','tools/oracle/oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    try:ref,version=oracle.check_pin(timeout=20)
    except oracle.Unavailable as e:
        if oracle.REQUIRED:raise RuntimeError(str(e))
        print('nearby oracle numerical controls: SKIPPED optional engine: '+str(e));ref=None
    source=Path('tools/oracle/gen_corpus_nearby.py').read_text()
    if ref:
        positive=oracle.engine_run(ref,['python','tools/oracle/gen_corpus_nearby.py','--self-test'],capture=True,timeout=60)
        if positive.returncode:raise RuntimeError('nearby publisher controls failed '+positive.stdout+positive.stderr)
        print(positive.stdout.strip(),flush=True)
        faults=[('directed-mode','gmpy2.RoundDown','gmpy2.RoundUp'),('nearest-mode','gmpy2.RoundToNearest','gmpy2.RoundToZero'),('target-bit','bits(float(r),width)','bits(float(r),width)^1'),('version',"gmpy2.version()!='2.3.2'","gmpy2.version()!='0.0.0'")]
        for name,old,new in faults:
            if source.count(old)!=1:raise RuntimeError('nonunique nearby oracle anchor '+name)
            with tempfile.TemporaryDirectory(prefix='nearby-oracle-',dir=a.work) as t:
                stage=Path(t);file=stage/'fault.py';out=stage/'out'
                changed=source.replace(old,new,1).replace('import argparse',"import sys\nsys.path.insert(0,'tools/oracle')\nimport argparse",1)
                changed=changed.replace("sys.path.insert(0,str(Path(__file__).resolve().parents[1]))","sys.path.insert(0,'tools')",1);file.write_text(changed)
                r=oracle.engine_run(ref,['python',str(file.resolve()),'--out',str(out.resolve()),'--count','0'],capture=True,timeout=120)
                (a.work/(name+'.log')).write_text(r.stdout+r.stderr)
                if r.returncode!=1 or not any(d in r.stderr for d in ['Fraction/MPFR nearby target differs','nearby oracle version differs']):raise RuntimeError('actual nearby numerical oracle fault escaped '+name+r.stdout+r.stderr)
                if out.exists() and list(out.iterdir()):raise RuntimeError('failed nearby oracle published')
        for name,replacement in [('ignored-seed','payloads(20261028,a.count,a.fresh,verify)'),('ignored-count','payloads(a.seed,0,a.fresh,verify)')]:
            with tempfile.TemporaryDirectory(prefix='nearby-request-',dir=a.work) as t:
                stage=Path(t);file=stage/'fault.py';out=stage/'out';old='payloads(a.seed,a.count,a.fresh,verify)'
                if source.count(old)!=1:raise RuntimeError('nearby request anchor')
                file.write_text(source.replace(old,replacement,1).replace('import argparse',"import sys\nsys.path.insert(0,'tools/oracle')\nimport argparse",1).replace("sys.path.insert(0,str(Path(__file__).resolve().parents[1]))","sys.path.insert(0,'tools')",1))
                r=oracle.engine_run(ref,['python',str(file.resolve()),'--out',str(out.resolve()),'--seed','4294967291','--count','113','--fresh'],capture=True,timeout=120)
                if r.returncode:raise RuntimeError('request control failed before publication '+r.stderr)
                check=subprocess.run([sys.executable,'tools/check-nearby.py','--directory',str(out),'--fresh','--seed','4294967291','--count','113'],capture_output=True,text=True,timeout=60)
                if check.returncode!=1 or 'complete population/target/widening differs' not in check.stderr:raise RuntimeError('actual nearby requested population fault escaped')
        print('nearby four actual oracle faults and two ignored-request defects detect',flush=True)
    # A recording engine calibrates actual wrapper argv dispatch, not numbers.
    wrapper=Path('tools/oracle/oracle.py').read_text();_,pin_version=oracle.pin()
    with tempfile.TemporaryDirectory(prefix='nearby-wrapper-',dir=a.work) as t:
        stage=Path(t);engine=stage/'engine';record=stage/'record.json';wrong=stage/'wrong-wrapper.py'
        engine.write_text('#!'+sys.executable+'\nimport sys,json\nfrom pathlib import Path\nargs=sys.argv[1:]\nif args[:2]==["image","exists"]:sys.exit(0)\nif args[-1:]==["mpfr-version"]:print('+repr(pin_version)+');sys.exit(0)\np=Path('+repr(str(record.resolve()))+')\nold=json.loads(p.read_text()) if p.exists() else []\nold.append(args);p.write_text(json.dumps(old))\n')
        engine.chmod(0o700);env=os.environ.copy();env['GHOTI_CONTAINER_ENGINE']=str(engine.resolve());env['GHOTI_ORACLE_REQUIRED']='1'
        dispatch=next(line for line in wrapper.splitlines() if line.startswith('    if a.cmd in ("logbase",'))
        omission=dispatch.replace('"nearby", "fresh-nearby", ','')
        if omission==dispatch:raise RuntimeError('wrapper family omission anchor absent')
        wrong.write_text(wrapper.replace(dispatch,omission,1))
        # Keep ROOT/HERE/pin lookup identical despite staging the actual source.
        wrong.write_text(wrong.read_text().replace('HERE = os.path.dirname(os.path.abspath(__file__))','HERE = '+repr(str(Path('tools/oracle').resolve())),1))
        for command in ('nearby','fresh-nearby'):
            for plant in (False,True):
                record.unlink(missing_ok=True);selected=wrong if plant else Path('tools/oracle/oracle.py')
                output=stage/('out-'+command+str(plant))
                r=subprocess.run([sys.executable,str(selected),'%s'%command,'--out',str(output.resolve()),'--seed','123','--count','17'],env=env,capture_output=True,text=True,timeout=30)
                calls=json.loads(record.read_text()) if record.exists() else []
                actual=[args[args.index('python')+1:] for args in calls if 'python' in args]
                expected=[['tools/oracle/gen_corpus_nearby.py','--out',str(output.resolve()),'--seed','123','--count','17']+(['--fresh'] if command.startswith('fresh-') else [])]
                if r.returncode or (actual==expected)==plant:raise RuntimeError('wrapper dispatch calibration wrong '+command+r.stdout+r.stderr)
                print('  ok   wrapper '+command+(' missing-family defect detected' if plant else ' valid dispatch'),flush=True)
        env['GHOTI_CONTAINER_ENGINE']=str((stage/'absent-engine').resolve())
        for required in (False,True):
            env['GHOTI_ORACLE_REQUIRED']='1' if required else '0';output=stage/('absent-'+str(required))
            r=subprocess.run([sys.executable,'tools/oracle/oracle.py','fresh-nearby','--out',str(output.resolve()),'--seed','123','--count','17'],env=env,capture_output=True,text=True,timeout=30)
            if r.returncode!=(1 if required else 3) or (output.exists() and list(output.iterdir())):raise RuntimeError('absent pinned engine semantics differ')
            print('  ok   '+('required' if required else 'optional')+' absent engine rejected/skipped without payloads',flush=True)
    print('nearby oracle controls pass; recording-engine controls are not numerical oracle evidence')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print('nearby oracle controls: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
