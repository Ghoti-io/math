#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Check real production commands, dynamic dependencies and bare C clients.

Test-only host references and platform floating-point-environment checks have
separate link flags; those are deliberately outside this production check.
"""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess

def forbidden(words):
 for word in words:
  for token in word.split(',') if word.startswith('-Wl,') else [word]:
   if token in ['-lm','-lstdc++'] or re.search(r'(?:^|/|:)(?:libm|libstdc\+\+)\.(?:a|so(?:\.|$)|dylib)',token):
    return token
 return None

def production_commands(text,compiler,shared,examples):
 links=[]
 for line in text.splitlines():
  try:words=shlex.split(line)
  except ValueError:continue
  if '-o' not in words:continue
  output=Path(words[words.index('-o')+1])
  if output!=shared and examples not in output.parents:continue
  if words[:len(compiler)]!=compiler:raise RuntimeError('production link does not use the declared C compiler')
  if forbidden(words):raise RuntimeError('production command includes forbidden library '+forbidden(words))
  links.append(output)
 if shared not in links:raise RuntimeError('dry build did not expose the shared-library link')
 if not any(examples in path.parents for path in links):raise RuntimeError('dry build did not expose an example link')

def dependencies(shared):
 r=subprocess.run(['readelf','-d',str(shared)],capture_output=True,text=True,timeout=30)
 if r.returncode:raise RuntimeError('cannot read production dynamic dependencies')
 needed=re.findall(r'\(NEEDED\).*\[([^]]+)\]',r.stdout)
 if not needed:raise RuntimeError('dynamic dependency check read no dependencies')
 for name in needed:
  if re.match(r'lib(?:m\.|stdc\+\+\.)',name):raise RuntimeError('production dynamic dependency includes '+name)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['shared','archive','work','examples']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--prefix',required=True);p.add_argument('--build-dir',required=True);a=p.parse_args()
 if os.uname().sysname!='Linux':raise RuntimeError('production ELF/client gate currently supports Linux only')
 a.work.mkdir(parents=True,exist_ok=True);compiler=shlex.split(os.environ['LINK_CC']);flags=shlex.split(os.environ['LINK_CFLAGS'])
 r=subprocess.run(['make','--no-print-directory','-Bn','PREFIX='+a.prefix,'BUILD_DIR='+a.build_dir,'CC='+os.environ['LINK_CC'],'CXX='+os.environ['LINK_CXX'],'all','examples'],capture_output=True,text=True,timeout=60)
 (a.work/'production-commands.log').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError('production command inspection failed')
 production_commands(r.stdout,compiler,a.shared,a.examples)
 # The checker must reject explicit libm even when --as-needed would erase
 # its unused dynamic dependency. Inspect real command text, not only ELF.
 for flag in ['-lm','-lstdc++','-Wl,-lm','/tmp/libm.so','-l:libm.a']:
  if not forbidden([flag]):raise RuntimeError('forbidden-link calibration escaped')
 mutant=r.stdout.replace(' -shared ',' -lm -shared ',1)
 if mutant==r.stdout:raise RuntimeError('production mutation anchor absent')
 try:production_commands(mutant,compiler,a.shared,a.examples)
 except RuntimeError as e:
  if 'forbidden library' not in str(e):raise
 else:raise RuntimeError('planted production -lm escaped')
 dependencies(a.shared)
 for line in Path('pkgconfig/ghoti.io-math.pc').read_text().splitlines():
  if line.startswith(('Libs:','Libs.private:')) and forbidden(shlex.split(line.split(':',1)[1])):
   raise RuntimeError('pkg-config exports a forbidden production library')
 fixture=a.work/'dependency-fixture.c';fixture.write_text('int gmath_link_fixture(void) {return 0;}\n')
 for flag in ['-lm','-lstdc++']:
  bad=a.work/('forbidden-'+flag[2:].replace('+','x')+'.so')
  r=subprocess.run(compiler+['-shared','-fPIC',str(fixture),'-Wl,--no-as-needed',flag,'-o',str(bad)],capture_output=True,text=True,timeout=60)
  if r.returncode:raise RuntimeError('cannot compile dependency calibration fixture')
  try:dependencies(bad)
  except RuntimeError as e:
   if 'production dynamic dependency includes' not in str(e):raise
  else:raise RuntimeError('planted dynamic dependency escaped')
 source=a.work/'client.c';source.write_text('''#include <ghoti.io/math/elementary.h>
#include <stdint.h>
#include <string.h>
int main(void) {
 volatile double x=1.0;double y=gmath_atan2(x,1.0);uint64_t word;
 memcpy(&word,&y,sizeof word);
 return word!=UINT64_C(0x3fe921fb54442d18);
}
''')
 for kind,link in [('static',['-Wl,--whole-archive',str(a.archive),'-Wl,--no-whole-archive']),('shared',[str(a.shared.resolve()),'-Wl,-rpath,'+str(a.shared.resolve().parent)])]:
  binary=a.work/('client-'+kind)
  command=compiler+flags+[str(source)]+link+['-o',str(binary)]
  if forbidden(command):raise RuntimeError('bare client accidentally links host math')
  r=subprocess.run(command,capture_output=True,text=True,timeout=60);(a.work/(kind+'-link.log')).write_text(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError('bare C '+kind+' client link failed')
  r=subprocess.run([str(binary.resolve())],capture_output=True,text=True,timeout=30)
  if r.returncode or r.stdout or r.stderr:raise RuntimeError('bare C '+kind+' client result differs')
  dependencies(binary)
 print('production C/shared/example links omit libm/C++ runtime; bare whole-archive/shared clients pass; planted -lm rejects')

if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('production link: FAIL: '+str(e))
