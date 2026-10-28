#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual pinned numerical/population faults and wrapper-dispatch controls."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True)
    ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--numeric-probe',type=Path,required=True)
    ap.add_argument('--long-bits',type=int,choices=(32,64),required=True);a=ap.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('longscale_oracle','tools/oracle/oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    source=Path('tools/oracle/gen_corpus_long_scale.py').read_text()
    faults=[('tie-parity','r*2==scaled.denominator and k&1','r*2==scaled.denominator and not(k&1)'),
      ('double-after','width==64 and exact is not None','False'),('float-before','width==64 and exact is not None','exact is not None'),
      ('mpfr-zero','m_n=max(-8192,min(8192,n))','m_n=0'),
      ('narrow-long','    p,bias,emax=parameters(width);sign=raw&','    n=((n+(1<<31))%(1<<32))-(1<<31)\n    p,bias,emax=parameters(width);sign=raw&'),
      ('signaling-invalid','if a>inf:return inf|quiet,int(not a&quiet)','if a>inf:return inf|quiet,0'),
      ('quiet-invalid','if a>inf:return inf|quiet,int(not a&quiet)','if a>inf:return inf|quiet,1'),
      ('canonical-payload','if a>inf:return inf|quiet,int(not a&quiet)','if a>inf:return inf|quiet|1,int(not a&quiet)')]
    try:ref,version=oracle.check_pin(timeout=20)
    except oracle.Unavailable as error:
        if oracle.REQUIRED:raise RuntimeError(str(error))
        print('long scale oracle plants: SKIPPED optional pinned numerical/population controls: '+str(error));ref=None
    if ref:
        for name,old,new in faults:
            if source.count(old)!=1:raise RuntimeError('nonunique oracle anchor '+name)
            with tempfile.TemporaryDirectory(prefix='longscale-fault-',dir=a.work) as t:
                stage=Path(t);script=stage/'fault.py';output=stage/'out'
                changed=source.replace(old,new,1).replace('import argparse',"import sys\nsys.path.insert(0,'tools')\nsys.path.insert(0,'tools/oracle')\nimport argparse",1);script.write_text(changed)
                r=oracle.engine_run(ref,['python',str(script.resolve()),'--out',str(output.resolve()),'--seed','20261028','--count','0'],capture=True,timeout=120)
                (a.work/(name+'.log')).write_text(r.stdout+r.stderr)
                if r.returncode!=1 or not any(x in r.stderr for x in ('Fraction/MPFR scaling disagreement','fixed long scaling reference failed')):raise RuntimeError('actual numerical oracle fault not detected '+name+' '+r.stdout+r.stderr)
                if output.exists() and list(output.iterdir()):raise RuntimeError('bad oracle published '+name)
                print('  ok   actual long scale oracle '+name+' rejected before publishing',flush=True)
        for name,replacement in (('ignored-count','pairs(width,a.seed,0)'),('ignored-seed','pairs(width,20261028,a.count)')):
            with tempfile.TemporaryDirectory(prefix='longscale-population-',dir=a.work) as t:
                stage=Path(t);script=stage/'fault.py';output=stage/'out';old='pairs(width,a.seed,a.count)'
                if source.count(old)!=1:raise RuntimeError('population anchor not unique')
                changed=source.replace(old,replacement,1).replace('import argparse',"import sys\nsys.path.insert(0,'tools')\nsys.path.insert(0,'tools/oracle')\nimport argparse",1);script.write_text(changed)
                r=oracle.engine_run(ref,['python',str(script.resolve()),'--out',str(output.resolve()),'--seed','4294967291','--count','113','--fresh'],capture=True,timeout=120)
                if r.returncode:raise RuntimeError('population fault did not reach publication '+name+r.stderr)
                r=subprocess.run([sys.executable,'tools/check-long-scale-output.py',str(a.probe.resolve()),'--fresh',str(output.resolve()),'--seed','4294967291','--count','113','--long-bits',str(a.long_bits),'--numeric-probe',str(a.numeric_probe.resolve())],capture_output=True,text=True,timeout=120)
                (a.work/(name+'.log')).write_text(r.stdout+r.stderr)
                if r.returncode!=1 or 'fresh requested input population differs' not in r.stderr:raise RuntimeError('actual requested population fault escaped '+name+r.stdout+r.stderr)
                print('  ok   actual generator '+name+' rejected by complete requested-pair check',flush=True)
    # A recording engine calibrates actual wrapper argv dispatch, not numbers.
    wrapper=Path('tools/oracle/oracle.py').read_text();_,pin_version=oracle.pin()
    with tempfile.TemporaryDirectory(prefix='longscale-wrapper-',dir=a.work) as t:
        stage=Path(t);engine=stage/'engine';record=stage/'record.json';wrong=stage/'wrong-wrapper.py'
        engine.write_text('#!'+sys.executable+'\nimport sys,json\nfrom pathlib import Path\nargs=sys.argv[1:]\nif args[:2]==["image","exists"]:sys.exit(0)\nif args[-1:]==["mpfr-version"]:print('+repr(pin_version)+');sys.exit(0)\np=Path('+repr(str(record.resolve()))+')\nold=json.loads(p.read_text()) if p.exists() else []\nold.append(args);p.write_text(json.dumps(old))\n')
        engine.chmod(0o700);env=os.environ.copy();env['GHOTI_CONTAINER_ENGINE']=str(engine.resolve());env['GHOTI_ORACLE_REQUIRED']='1'
        dispatch=next(line for line in wrapper.splitlines() if line.startswith('    if a.cmd in ("logbase",'))
        omission=dispatch.replace('"long_scale", "fresh-long_scale", ','')
        if omission==dispatch:raise RuntimeError('wrapper family omission anchor absent')
        wrong.write_text(wrapper.replace(dispatch,omission,1))
        # Keep ROOT/HERE/pin lookup identical despite staging the actual source.
        wrong.write_text(wrong.read_text().replace('HERE = os.path.dirname(os.path.abspath(__file__))','HERE = '+repr(str(Path('tools/oracle').resolve())),1))
        for command in ('long_scale','fresh-long_scale'):
            for plant in (False,True):
                record.unlink(missing_ok=True);selected=wrong if plant else Path('tools/oracle/oracle.py')
                output=stage/('out-'+command+str(plant))
                r=subprocess.run([sys.executable,str(selected),'%s'%command,'--out',str(output.resolve()),'--seed','123','--count','17'],env=env,capture_output=True,text=True,timeout=30)
                calls=json.loads(record.read_text()) if record.exists() else []
                actual=[args[args.index('python')+1:] for args in calls if 'python' in args]
                expected=[['tools/oracle/gen_corpus_long_scale.py','--out',str(output.resolve()),'--seed','123','--count','17']+(['--fresh'] if command.startswith('fresh-') else [])]
                if r.returncode or (actual==expected)==plant:raise RuntimeError('wrapper dispatch calibration wrong '+command+r.stdout+r.stderr)
                print('  ok   wrapper '+command+(' missing-family defect detected' if plant else ' valid dispatch'),flush=True)
        env['GHOTI_CONTAINER_ENGINE']=str((stage/'absent-engine').resolve())
        for required in (False,True):
            env['GHOTI_ORACLE_REQUIRED']='1' if required else '0';output=stage/('absent-'+str(required))
            r=subprocess.run([sys.executable,'tools/oracle/oracle.py','fresh-long_scale','--out',str(output.resolve()),'--seed','123','--count','17'],env=env,capture_output=True,text=True,timeout=30)
            if r.returncode!=(1 if required else 3) or (output.exists() and list(output.iterdir())):raise RuntimeError('absent pinned engine semantics differ')
            print('  ok   '+('required' if required else 'optional')+' absent engine rejected/skipped without payloads',flush=True)
    print('long scale oracle controls pass; recording-engine controls are not numerical oracle evidence')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as error:
        print('long scale oracle controls: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
