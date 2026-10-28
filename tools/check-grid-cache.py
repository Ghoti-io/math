#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exercise full native reconstruction, literal seeds, cache faults and Make edges."""
import argparse
from contextlib import ExitStack, contextmanager
import importlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('grid_cache', Path(__file__).with_name('prepare-grid-corpora.py'))
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


def rejects(action, text):
    try:
        action()
    except (RuntimeError, OSError) as error:
        if text not in str(error):
            raise RuntimeError('grid control failed at unintended layer: '+str(error)) from error
    else:
        raise RuntimeError('grid counterfactual escaped: '+text)


def graph(prefix, active):
    environment = dict(os.environ)
    # Query the actual default registration, independently of a caller's
    # command-line TEST_GATES override inherited through GNU Make flags.
    for name in ['MAKEFLAGS', 'MFLAGS', 'GNUMAKEFLAGS', 'TEST_GATES']:
        environment.pop(name, None)
    for extra in [[], ['TEST_GATES=check-corpus-hash']]:
        result = subprocess.run(['make', '-qp', 'PREFIX='+prefix]+extra+['prepare-grid-corpora'],
                                env=environment, capture_output=True, text=True, timeout=30)
        if result.returncode not in [0, 1]:
            raise RuntimeError('grid Make query failed: '+result.stderr[-500:])
        text = result.stdout
        variables = dict(re.findall(r'^(HASH_PROBE|TEST_EXECUTABLES|ASAN_TEST_EXECUTABLES|GRID_DIRECT_TARGETS) := (.+)$', text, re.M))
        def default_membership(database):
            rows = [line for line in database.splitlines() if line.startswith('TEST_GATES = ')]
            if len(rows) != 1 or 'check-grid-cache' not in rows[0].split():
                raise RuntimeError('grid control absent from default gates')
        if not extra:
            default_membership(text)
            rejects(lambda: default_membership(text.replace('check-grid-cache', 'missing-grid-control')), 'absent from default gates')
        targets = ['test', 'test-asan', 'test-valgrind', 'test-valgrind-quiet',
                   'corpus-hash-update', variables['HASH_PROBE']]
        targets += variables['TEST_EXECUTABLES'].split()+variables['ASAN_TEST_EXECUTABLES'].split()
        targets += variables['GRID_DIRECT_TARGETS'].split()
        families = {
            'nearby': ['check-nearby', 'check-planted-nearby', 'check-nearby-controls',
                       'check-nearby-oracle', 'check-nearby-oracle-controls',
                       'check-nearby-mode-plants', 'check-nearby-link'],
            'currentint': ['check-currentint', 'check-planted-currentint',
                           'check-currentint-controls', 'check-currentint-oracle',
                           'check-currentint-oracle-controls', 'check-currentint-link'],
            'fdim': ['check-positive-difference', 'check-planted-positive-difference',
                     'check-positive-difference-harness', 'check-positive-difference-controls',
                     'check-positive-difference-oracle', 'check-positive-difference-oracle-controls',
                     'check-positive-difference-bench-controls', 'bench-positive-difference'],
        }
        for name, _ in active:
            targets += families[name]
        if Path(__file__).with_name('currentint_baseline.py').is_file():
            targets += ['check-currentint-prior', 'bench-currentint-prior']
        def validate(database):
            for target in targets:
                key = str(Path(target))+':'
                rows = [line for line in database.splitlines() if line.startswith(key)]
                if len(rows) != 1 or 'prepare-grid-corpora' not in rows[0].partition('|')[2].split():
                    raise RuntimeError('grid Make preparation edge missing: '+target)
            if not any(line.startswith('clean:') and 'clean-grid-corpora' in line.split()
                       for line in database.splitlines()):
                raise RuntimeError('grid Make clean edge missing')
        validate(text)
        broken = '\n'.join(line.replace('prepare-grid-corpora', '')
                           if line.startswith('test:') else line for line in text.splitlines())
        rejects(lambda: validate(broken), 'preparation edge missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('tests/corpus'))
    parser.add_argument('--prefix', default='')
    args = parser.parse_args()
    expected, seed_hashes, active = cache.configuration(args.directory)
    with tempfile.TemporaryDirectory(prefix='grid-cache-control-') as name, ExitStack() as patches:
        root = Path(name)
        for filename in ['grid-payloads.sha256', 'grid-seeds.sha256']+list(seed_hashes):
            shutil.copy2(args.directory/filename, root/filename)
        payload_manifest = root/'grid-payloads.sha256'
        seed_manifest = root/'grid-seeds.sha256'
        original_payload_manifest = payload_manifest.read_bytes()
        original_seed_manifest = seed_manifest.read_bytes()
        omitted = active[-1][1]
        payload_manifest.write_text(''.join(line+'\n' for line in payload_manifest.read_text().splitlines() if line.split()[1] not in omitted[3]))
        seed_manifest.write_text(''.join(line+'\n' for line in seed_manifest.read_text().splitlines() if line.split()[1] != omitted[2]))
        rejects(lambda: cache.configuration(root), 'family/source availability differs' if len(active)>1 else 'file missing/nonregular/oversized')
        payload_manifest.write_bytes(original_payload_manifest)
        seed_manifest.write_bytes(original_seed_manifest)
        recorded = {}
        # Only the first positive invokes real exact reference generation.
        # Later publication/accounting faults replay those exact payloads;
        # they are not additional independent numerical-oracle evidence.
        for _, family in active:
            module = importlib.import_module(family[0])
            original = module.payloads
            def recording(seed, count, original=original, key=family[0]):
                if (seed, count) != (cache.SEED, cache.COUNT):
                    raise RuntimeError('grid reconstruction requested wrong population')
                if key not in recorded:
                    recorded[key] = original(seed, count)
                return dict(recorded[key])
            patches.enter_context(patch.object(module, 'payloads', recording))
        rejects(lambda: cache.prepare(root, True), 'cache missing')
        cache.prepare(root)
        snapshots = {filename: (root/filename).read_bytes() for filename in expected}
        if len(recorded) != len(active):
            raise RuntimeError('grid positive omitted a native reference family')
        cache.prepare(root, True)
        for filename in expected:
            path = root/filename
            path.chmod(0o640)
            before = path.stat().st_mtime_ns
            cache.prepare(root)
            if path.stat().st_mtime_ns != before or path.stat().st_mode & 0o777 != 0o640:
                raise RuntimeError('warm grid was rewritten')
            path.write_bytes(snapshots[filename][:-2]+b'x\n')
            rejects(lambda: cache.prepare(root), 'existing grid cache SHA256 differs')
            if path.read_bytes() != snapshots[filename][:-2]+b'x\n':
                raise RuntimeError('corrupt grid cache silently repaired')
            path.write_bytes(snapshots[filename])
        first_family = active[0][1]
        seed = root/first_family[2]
        saved_seed = seed.read_bytes()
        saved_manifest = (root/'grid-seeds.sha256').read_bytes()
        for index in [0, 1, 3]:
            headers = saved_seed.decode().splitlines()
            headers[index] += ' wrong'
            seed.write_text('\n'.join(headers)+'\n')
            (root/'grid-seeds.sha256').write_text(saved_manifest.decode().replace(seed_hashes[first_family[2]], cache.digest(seed.read_bytes())))
            rejects(lambda: cache.prepare(root), 'provenance/schema differs')
        seed.write_bytes(saved_seed)
        (root/'grid-seeds.sha256').write_bytes(saved_manifest)
        seed.write_bytes(saved_seed+b'\n')
        rejects(lambda: cache.prepare(root), 'literal grid seed SHA256 differs')
        seed.write_bytes(saved_seed)
        lines = saved_seed.decode().splitlines()
        fields = lines[4].split()
        fields[first_family[4]] = '%016x' % (int(fields[first_family[4]], 16)^1)
        lines[4] = ' '.join(fields)
        seed.write_text('\n'.join(lines)+'\n')
        manifest = root/'grid-seeds.sha256'
        saved_manifest = manifest.read_bytes()
        manifest.write_text(manifest.read_text().replace(seed_hashes[first_family[2]], cache.digest(seed.read_bytes())))
        rejects(lambda: cache.prepare(root), 'literal seed disagrees')
        seed.write_bytes(saved_seed)
        manifest.write_bytes(saved_manifest)
        def remove():
            for filename in expected:
                (root/filename).unlink(missing_ok=True)
        remove()
        original_temporary = cache.tempfile.NamedTemporaryFile
        for kind in ['write', 'close']:
            @contextmanager
            def broken_temporary(*a, **kw):
                with original_temporary(*a, **kw) as stream:
                    if kind == 'write':
                        class Broken:
                            name = stream.name
                            def fileno(self): return stream.fileno()
                            def write(self, data): raise OSError('injected grid write')
                        yield Broken()
                    else:
                        yield stream
                raise OSError('injected grid close')
            with patch.object(cache.tempfile, 'NamedTemporaryFile', broken_temporary):
                rejects(lambda: cache.prepare(root), 'injected grid '+kind)
            if list(root.glob('.grid-cache-*')) or any((root/f).exists() for f in expected):
                raise RuntimeError('failed grid staging leaked files')
        link = cache.os.link
        count = 0
        def second_failure(source, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('injected partial grid publication')
            return link(source, target)
        with patch.object(cache.os, 'link', second_failure):
            rejects(lambda: cache.prepare(root), 'injected partial grid publication')
        cache.prepare(root)
        for filename in expected:
            if (root/filename).read_bytes() != snapshots[filename]:
                raise RuntimeError('partial grid recovery changed answers')
        for valid in [False, True]:
            remove()
            raced = False
            def race(source, target):
                nonlocal raced
                if not raced:
                    raced = True
                    target.write_bytes(snapshots[target.name] if valid else b'corrupt race')
                    target.chmod(0o600)
                return link(source, target)
            with patch.object(cache.os, 'link', race):
                if valid:
                    cache.prepare(root)
                else:
                    rejects(lambda: cache.prepare(root), 'grid cache changed during publication')
            first = root/next(iter(expected))
            if first.stat().st_mode & 0o777 != 0o600 or (not valid and first.read_bytes() != b'corrupt race'):
                raise RuntimeError('concurrent grid winner was overwritten')
            if list(root.glob('.grid-cache-*')):
                raise RuntimeError('grid publication leaked staging')
    graph(args.prefix, active)
    print('grid native exact-byte positive, literal seeds, cache corruption/publication/race and Make edge controls pass; replay faults are accounting only')


if __name__ == '__main__':
    try:
        main()
    except (OSError, UnicodeError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit('grid cache controls: FAIL: '+str(error))
