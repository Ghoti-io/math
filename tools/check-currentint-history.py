#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compile actual historical helpers while deliberately poisoning current ones."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from currentint_baseline import REVISION, compiler_identity


def run(command, cwd=None, env=None):
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', required=True)
    parser.add_argument('--flags', required=True)
    parser.add_argument('--nm', default='nm')
    parser.add_argument('--objcopy', default='objcopy')
    args = parser.parse_args()
    if not Path('.git').exists():
        print('currentint historical helper control: SKIPPED source archive without Git')
        return
    try:
        compiler_identity(args.cc)
    except RuntimeError as error:
        if 'wrapper' not in str(error):
            raise
        print('currentint historical helper control: SKIPPED unsupported compiler wrapper')
        return
    source = {}
    for name in ['current_intround.c', 'elem_common.h', 'nearby_mode.h']:
        result = run(['git', 'show', REVISION+':src/elementary/'+name])
        if result.returncode:
            raise RuntimeError('pinned historical source is not resolvable: '+REVISION)
        source[name] = result.stdout
    flags = shlex.split(args.flags)
    for index, flag in enumerate(flags):
        if flag in ['-I', '-isystem', '-iquote'] and index+1 < len(flags):
            flags[index+1] = str(Path(flags[index+1]).resolve())
        elif flag.startswith('-I') and len(flag)>2:
            flags[index] = '-I'+str(Path(flag[2:]).resolve())
    with tempfile.TemporaryDirectory(prefix='currentint-history-') as temporary:
        root = Path(temporary)
        environment = dict(os.environ)
        for key in list(environment):
            if key.startswith('GIT_'):
                environment.pop(key)
        environment.update(GIT_AUTHOR_NAME='Math control', GIT_AUTHOR_EMAIL='control@example.invalid',
                           GIT_COMMITTER_NAME='Math control', GIT_COMMITTER_EMAIL='control@example.invalid',
                           GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        result = run(['git', 'init', '--quiet', '--initial-branch=master', str(root)], env=environment)
        if result.returncode:
            raise RuntimeError('historical helper fixture Git initialization failed')
        folder = root/'src/elementary'
        folder.mkdir(parents=True)
        for name, data in source.items():
            (folder/name).write_bytes(data)
        subprocess.run(['git', 'add', 'src'], cwd=root, env=environment, check=True, capture_output=True)
        tree = subprocess.check_output(['git', 'write-tree'], cwd=root, env=environment).strip()
        revision = subprocess.check_output(['git', 'commit-tree', tree.decode(), '-m', 'Record historical helper fixture'], cwd=root, env=environment).decode().strip()
        for name in ['elem_common.h', 'nearby_mode.h']:
            (folder/name).write_text('#error "current helper must not be compiled"\n')
        out = root/'historical'
        tool = Path(__file__).with_name('build-currentint-baseline.py').resolve()
        command = [sys.executable, str(tool), '--out', str(out), '--cc', args.cc,
                   '--flags', shlex.join(flags), '--revision', revision,
                   '--nm', args.nm, '--objcopy', args.objcopy]
        result = run(command, cwd=root, env=environment)
        if result.returncode:
            raise RuntimeError('actual historical helper compile failed: '+result.stderr.decode(errors='replace')[-600:])
        metadata = json.loads((out/'prior.o.json').read_text())
        if metadata['revision'] != revision or metadata['source_sha256'] != hashlib.sha256(source['current_intround.c']).hexdigest():
            raise RuntimeError('historical source identity differs')
        for name in ['elem_common.h', 'nearby_mode.h']:
            historical = hashlib.sha256(source[name]).hexdigest()
            current = hashlib.sha256((folder/name).read_bytes()).hexdigest()
            if (out/name).read_bytes() != source[name] or metadata['helpers_sha256'][name] != historical or metadata['current_helpers_sha256'][name] != current or historical == current:
                raise RuntimeError('historical/current helper provenance differs')
    print('currentint historical source/helper compile passes with poisoned current helpers and distinct recorded hashes')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit('currentint historical helper control: FAIL: '+str(error))
