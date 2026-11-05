#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Required pinned regeneration of all seventeen numerical references.

No host-oracle fallback; every named container has a deadline and final cleanup.
Caller resource scheduling/affinity is inherited by the one sequential worker.
"""
import argparse,hashlib,importlib.util,json,os,re,subprocess,sys,time,uuid
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('numerical certificates require assertion-enabled Python')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,default=Path('tests/corpus'));ap.add_argument('--work',type=Path,required=True);args=ap.parse_args()
 root=Path(__file__).resolve().parents[1];directory=args.directory.resolve();directory.relative_to(root)
 work=args.work.resolve();work.mkdir(parents=True,exist_ok=True);(work/'tmp').mkdir(exist_ok=True)
 spec=importlib.util.spec_from_file_location('seventeen_numerical',root/'tools/check-long-double-seventeen.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
 _,population=checker.load(directory) # Positive authenticated offline control before oracle work.
 engine=os.environ.get('GHOTI_CONTAINER_ENGINE','podman')
 pin_lines=[line.rstrip('\n').split('\t')for line in(root/'tools/oracle/containers/IMAGES').read_text().splitlines()if line.startswith('mpfr\t')]
 if len(pin_lines)!=1 or pin_lines[0][2]!=checker.c.PIN:raise SystemExit('required numerical oracle runtime pin mismatch')
 image=pin_lines[0][1]
 try:
  identity=subprocess.check_output([engine,'image','inspect','--format','{{.Id}}',image],text=True,timeout=30).strip().removeprefix('sha256:')
 except(subprocess.CalledProcessError,OSError)as error:raise SystemExit('required numerical oracle image unavailable')from error
 if not re.fullmatch('[0-9a-f]{64}',identity):raise SystemExit('required numerical oracle image identity invalid')
 image=identity
 style=os.environ.get('GHOTI_CONTAINER_STYLE','podman'if Path(engine).name.startswith('podman')else'docker')
 if style not in('podman','docker'):raise SystemExit('unsupported container engine style')
 token=uuid.uuid4().hex
 def run(arguments,label,deadline):
  name='ghoti-seventeen-numerical-'+uuid.uuid4().hex[:12]
  log=work/(label+'-'+token+'.log')
  command=[engine,'run','--rm','--name',name]
  if style=='podman':command+=['--timeout',str(deadline),'--cgroups=disabled','--cgroupns=host','--userns=keep-id','--security-opt','label=disable']
  else:command+=['--user',str(os.getuid())+':'+str(os.getgid())]
  command+=['-e','PYTHONDONTWRITEBYTECODE=1','-e','TMPDIR=/evidence/tmp','-v',str(work)+':/evidence','-v',str(root)+':/work:ro','-w','/work',image,'sh','-c','ulimit -v 1572864; exec "$@"','sh',*arguments]
  try:
   with log.open('x')as out:result=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=deadline+10)
   if result.returncode:raise SystemExit('required numerical oracle '+label+' failed: '+str(result.returncode)+'; '+str(log))
   return log
  finally:subprocess.run([engine,'rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
 version=run(['mpfr-version'],'version',30)
 if version.read_text().strip()!=checker.c.PIN:raise SystemExit('required numerical oracle runtime mismatch')
 start=time.monotonic()
 run(['python','tools/oracle/gen_long_double_seventeen_corpus.py','--out',str(Path('/work')/directory.relative_to(root)/checker.NAME),'--verify','--controls'],'regeneration',7200)
 summary={'actual_exit':0,'elapsed_seconds':time.monotonic()-start,'immutable_image_id':identity,'runtime_pin':checker.c.PIN,'corpus_sha256':checker.REFERENCE_SHA256,'cells':population['cells']}
 (work/('status-'+token+'.json')).write_text(json.dumps(summary,sort_keys=True)+'\n')
 print('required seventeen numerical oracle: pinned cells regenerate exactly and repinning controls pass')
if __name__=='__main__':main()
