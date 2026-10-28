#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual Float cube-root oracle faults and wrapper accounting controls."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--probe',type=Path,required=True);a=ap.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('cbrtf_oracle','tools/oracle/oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    source=Path('tools/oracle/gen_corpus_cbrtf.py').read_text()
    faults=[('MPFR-root','gmpy2.cbrt(','gmpy2.sqrt('),
      ('adjacent-target','rb=round32(root);mb=round32(other)','rb=round32(root)+1;mb=round32(other)+1'),
      ('error-sign','certify(raw,rb,eb)','eb^=SIGN;certify(raw,rb,eb)'),
      ('finite-flags','return rb,eb,flags(raw)','return rb,eb,0'),
      ('signaling-invalid','return QNAN,0,flags(raw)','return QNAN,0,0'),
      ('canonical-NaN','return QNAN,0,flags(raw)','return QNAN|1,0,flags(raw)'),
      ('mpmath-pin','mpmath.__version__','"untrusted"')]
    try:ref,version=oracle.check_pin(timeout=20)
    except oracle.Unavailable as error:
        if oracle.REQUIRED:raise RuntimeError(str(error))
        print('cbrtf oracle plants: SKIPPED optional pinned numerical/population controls: '+str(error));ref=None
    if ref:
        for name,old,new in faults:
            if source.count(old)!=1:raise RuntimeError('nonunique oracle anchor '+name)
            with tempfile.TemporaryDirectory(prefix='cbrtf-fault-',dir=a.work) as t:
                stage=Path(t);script=stage/'fault.py';output=stage/'out'
                changed=source.replace(old,new,1).replace('import argparse',"import sys\nsys.path.insert(0,'tools')\nsys.path.insert(0,'tools/oracle')\nimport argparse",1);script.write_text(changed)
                r=oracle.engine_run(ref,['python',str(script.resolve()),'--out',str(output.resolve()),'--seed','20261028','--count','0'],capture=True,timeout=120)
                (a.work/(name+'.log')).write_text(r.stdout+r.stderr)
                if r.returncode!=1 or not any(x in r.stderr for x in ('certificate failed','independent oracle disagreement','fixed reference control failed','incorrect pinned')):raise RuntimeError('actual oracle fault not detected '+name+' '+r.stdout+r.stderr)
                if output.exists() and list(output.iterdir()):raise RuntimeError('bad oracle published '+name)
                print('  ok   actual cbrtf oracle '+name+' rejected before publishing',flush=True)
        for name,replacement in (('ignored-count','inputs(a.seed,0)'),('ignored-seed','inputs(20261028,a.count)')):
            with tempfile.TemporaryDirectory(prefix='cbrtf-population-',dir=a.work) as t:
                stage=Path(t);script=stage/'fault.py';output=stage/'out';old='inputs(a.seed,a.count)'
                if source.count(old)!=1:raise RuntimeError('population anchor not unique')
                changed=source.replace(old,replacement,1).replace('import argparse',"import sys\nsys.path.insert(0,'tools')\nsys.path.insert(0,'tools/oracle')\nimport argparse",1);script.write_text(changed)
                r=oracle.engine_run(ref,['python',str(script.resolve()),'--out',str(output.resolve()),'--seed','4294967291','--count','113','--fresh'],capture=True,timeout=120)
                if r.returncode:raise RuntimeError('population fault did not publish '+name+r.stderr)
                r=subprocess.run([sys.executable,'tools/check-cbrtf.py','--probe',str(a.probe.resolve()),'--corpus',str(output.resolve()),'--fresh','--seed','4294967291','--count','113'],capture_output=True,text=True,timeout=120)
                (a.work/(name+'.log')).write_text(r.stdout+r.stderr)
                if r.returncode!=1 or 'complete ordered population mismatch' not in r.stderr:raise RuntimeError('actual population fault escaped '+name+r.stdout+r.stderr)
                print('  ok   actual generator '+name+' rejected by complete population check',flush=True)
    # A recording engine calibrates actual wrapper argv dispatch, not numbers.
    wrapper=Path('tools/oracle/oracle.py').read_text();_,pin_version=oracle.pin()
    with tempfile.TemporaryDirectory(prefix='cbrtf-wrapper-',dir=a.work) as t:
        stage=Path(t);engine=stage/'engine';record=stage/'record.json';wrong=stage/'wrong-wrapper.py'
        engine.write_text('#!'+sys.executable+'\nimport sys,json\nfrom pathlib import Path\nargs=sys.argv[1:]\nif args[:2]==["image","exists"]:sys.exit(0)\nif args[-1:]==["mpfr-version"]:print('+repr(pin_version)+');sys.exit(0)\np=Path('+repr(str(record.resolve()))+')\nold=json.loads(p.read_text()) if p.exists() else []\nold.append(args);p.write_text(json.dumps(old))\n')
        engine.chmod(0o700);env=os.environ.copy();env['GHOTI_CONTAINER_ENGINE']=str(engine.resolve());env['GHOTI_ORACLE_REQUIRED']='1'
        dispatch=next(line for line in wrapper.splitlines() if line.startswith('    if a.cmd in ("logbase",'))
        omission=dispatch.replace('"cbrtf", "fresh-cbrtf", ','')
        if omission==dispatch:raise RuntimeError('wrapper family omission anchor absent')
        wrong.write_text(wrapper.replace(dispatch,omission,1))
        # Keep ROOT/HERE/pin lookup identical despite staging the actual source.
        wrong.write_text(wrong.read_text().replace('HERE = os.path.dirname(os.path.abspath(__file__))','HERE = '+repr(str(Path('tools/oracle').resolve())),1))
        for command in ('cbrtf','fresh-cbrtf'):
            for plant in (False,True):
                record.unlink(missing_ok=True);selected=wrong if plant else Path('tools/oracle/oracle.py')
                output=stage/('out-'+command+str(plant))
                r=subprocess.run([sys.executable,str(selected),'%s'%command,'--out',str(output.resolve()),'--seed','123','--count','17'],env=env,capture_output=True,text=True,timeout=30)
                calls=json.loads(record.read_text()) if record.exists() else []
                actual=[args[args.index('python')+1:] for args in calls if 'python' in args]
                expected=[['tools/oracle/gen_corpus_cbrtf.py','--out',str(output.resolve()),'--seed','123','--count','17']+(['--fresh'] if command.startswith('fresh-') else [])]
                if r.returncode or (actual==expected)==plant:raise RuntimeError('wrapper dispatch calibration wrong '+command+r.stdout+r.stderr)
                print('  ok   wrapper '+command+(' missing-family defect detected' if plant else ' valid dispatch'),flush=True)
        env['GHOTI_CONTAINER_ENGINE']=str((stage/'absent-engine').resolve())
        for required in (False,True):
            env['GHOTI_ORACLE_REQUIRED']='1' if required else '0';output=stage/('absent-'+str(required))
            r=subprocess.run([sys.executable,'tools/oracle/oracle.py','fresh-cbrtf','--out',str(output.resolve()),'--seed','123','--count','17'],env=env,capture_output=True,text=True,timeout=30)
            if r.returncode!=(1 if required else 3) or (output.exists() and list(output.iterdir())):raise RuntimeError('absent pinned engine semantics differ')
            print('  ok   '+('required' if required else 'optional')+' absent engine rejected/skipped without payloads',flush=True)
    print('cbrtf oracle controls pass; recording-engine controls are not numerical oracle evidence')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print('cbrtf oracle controls: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
