#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exercise real optimized interpreters before any certification can run."""
import sys
if sys.flags.optimize:
 raise SystemExit('remaining-fifteen: optimized Python execution is unsupported')
import os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
names=['check-remaining.py','check-remaining-plants.py','gen-remaining-coefficients.py','oracle/gen_corpus_remaining.py','oracle/select_remaining_seams.py','run-remaining-oracle.py','check-remaining-optimization.py']
for name in names:
 for option in [True,False]:
  env=dict(os.environ);env.pop('PYTHONOPTIMIZE',None)
  if not option:env['PYTHONOPTIMIZE']='2'
  cmd=[sys.executable]+(['-O'] if option else [])+[str(root/'tools'/name),'--help']
  r=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=30)
  if r.returncode!=1 or r.stdout or r.stderr.strip()!='remaining-fifteen: optimized Python execution is unsupported':raise RuntimeError('optimized certification execution escaped: '+name)
print('remaining-fifteen: 14 actual optimized invocations rejected before success/output')
