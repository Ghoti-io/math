#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Calibrate native grid reconstruction, seed retention and corrupt-cache rejection."""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('atan_cache', Path(__file__).with_name('prepare-atan-corpus.py'))
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


def rejects(action, message):
    try:
        action()
    except (RuntimeError, OSError) as error:
        if message not in str(error):
            raise RuntimeError('cache control failed at unintended layer: '+str(error)) from error
    else:
        raise RuntimeError('cache counterfactual escaped: '+message)


def make_graph(prefix):
    def database(extra):
        result = subprocess.run(['make', '-qp', 'PREFIX='+prefix]+extra+['prepare-atan-corpus'],
                                capture_output=True, text=True, timeout=30)
        if result.returncode not in [0, 1]:
            raise RuntimeError('Make cache graph query failed: '+result.stderr[-500:])
        return result.stdout
    def validate(text):
        import re
        variables = dict(re.findall(r'^(HASH_PROBE|APP_DIR|ASAN_APP_DIR) := (.+)$', text, re.M))
        targets = ['test', 'test-asan', 'test-valgrind', 'test-valgrind-quiet',
                   'check-atan', 'check-planted-atan', 'check-atan-controls',
                   'check-atan-harness', 'check-atan-oracle-controls',
                   'check-atan-bench-controls', 'bench-atan',
                   variables['HASH_PROBE'], variables['APP_DIR']+'/testAtan',
                   variables['ASAN_APP_DIR']+'/testAtan']
        for target in targets:
            key = str(Path(target))+':'
            lines = [line for line in text.splitlines() if line.startswith(key)]
            if len(lines) != 1 or 'prepare-atan-corpus' not in lines[0].partition('|')[2].split():
                raise RuntimeError('Make cache preparation edge missing: '+target)
        if not any(line.startswith('clean:') and 'clean-atan-corpus' in line.split()
                   for line in text.splitlines()):
            raise RuntimeError('Make cache clean edge missing')
    for overrides in [[], ['TEST_GATES=check-corpus-hash']]:
        text = database(overrides)
        validate(text)
        broken = '\n'.join(line.replace('prepare-atan-corpus', '')
                           if line.startswith('test:') else line for line in text.splitlines())
        rejects(lambda: validate(broken), 'preparation edge missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('tests/corpus'))
    parser.add_argument('--prefix', default='')
    args = parser.parse_args()
    source = args.directory
    rows = cache.seeds(source)
    for precision in [130, 170, 210]:
        data = cache.payloads(rows, precision)
        for name, expected in cache.EXPECTED.items():
            if hashlib.sha256(data[name]).hexdigest() != expected:
                raise RuntimeError('native cache precision/pinned-byte agreement differs')
    with tempfile.TemporaryDirectory(prefix='atan-cache-control-') as name:
        root = Path(name)
        shutil.copy2(source/'atan-seeded.corpus', root)
        rejects(lambda: cache.prepare(root, True), 'cache missing')
        original = cache.answer
        seen = set()
        def tracked(word, pi):
            if word in rows:
                raise RuntimeError('literal seeded answer was regenerated')
            seen.add(word)
            return original(word, pi)
        cache.answer = tracked
        try:
            cache.prepare(root)
        finally:
            cache.answer = original
        if len(seen) != 26382:
            raise RuntimeError('native deterministic population accounting differs')
        cache.prepare(root, True)
        payload = root/'atan.corpus'
        payload.chmod(0o640)
        before = payload.stat().st_mtime_ns
        cache.prepare(root)
        if payload.stat().st_mtime_ns != before or payload.stat().st_mode & 0o777 != 0o640:
            raise RuntimeError('valid cache was unnecessarily rewritten')
        saved = payload.read_bytes()
        payload.write_bytes(saved[:-2]+b'x\n')
        rejects(lambda: cache.prepare(root), 'existing cache SHA256 differs')
        if payload.read_bytes() != saved[:-2]+b'x\n':
            raise RuntimeError('corrupt cache was silently repaired')
        payload.unlink()
        cache.prepare(root)
        if payload.read_bytes() != saved:
            raise RuntimeError('missing cache reconstruction differs')
        seed = root/'atan-seeded.corpus'
        seed.write_bytes(seed.read_bytes()+b'\n')
        rejects(lambda: cache.prepare(root), 'seeded answers SHA256 differs')
        shutil.copy2(source/'atan-seeded.corpus', seed)
        for filename in cache.EXPECTED:
            (root/filename).unlink(missing_ok=True)
        def wrong(word, pi):
            target, error = original(word, pi)
            return target ^ 1, error
        cache.answer = wrong
        try:
            rejects(lambda: cache.prepare(root), 'reconstructed pinned SHA256 differs')
        finally:
            cache.answer = original
        if any((root/filename).exists() for filename in cache.EXPECTED):
            raise RuntimeError('uncertified cache was published')
        if list(root.glob('.atan-cache-*')):
            raise RuntimeError('native cache staging files leaked')
        original_temporary = cache.tempfile.NamedTemporaryFile
        for kind in ['write', 'close']:
            @contextmanager
            def broken_temporary(*args, **kwargs):
                with original_temporary(*args, **kwargs) as stream:
                    if kind == 'write':
                        class Broken:
                            name = stream.name
                            def fileno(self): return stream.fileno()
                            def write(self, data): raise OSError('injected cache write')
                        yield Broken()
                    else:
                        yield stream
                raise OSError('injected cache close')
            with patch.object(cache.tempfile, 'NamedTemporaryFile', broken_temporary):
                rejects(lambda: cache.prepare(root), 'injected cache '+kind)
            if any((root/f).exists() for f in cache.EXPECTED) or list(root.glob('.atan-cache-*')):
                raise RuntimeError('failed cache staging left files')
        original_link = cache.os.link
        publications = 0
        def second_failure(source, destination):
            nonlocal publications
            publications += 1
            if publications == 2:
                raise OSError('injected second cache publication')
            return original_link(source, destination)
        with patch.object(cache.os, 'link', second_failure):
            rejects(lambda: cache.prepare(root), 'injected second cache publication')
        if list(root.glob('.atan-cache-*')) or not (root/'atan-special.corpus').is_file():
            raise RuntimeError('partial cache publication cleanup differs')
        cache.prepare(root)  # Valid first file survives; missing second recovers.
        for valid in [False, True]:
            for filename in cache.EXPECTED:
                (root/filename).unlink(missing_ok=True)
            raced = False
            def race(staged, destination):
                nonlocal raced
                if not raced:
                    raced = True
                    destination.write_bytes((source/destination.name).read_bytes() if valid else b'corrupt race')
                    destination.chmod(0o600)
                return original_link(staged, destination)
            with patch.object(cache.os, 'link', race):
                if valid:
                    cache.prepare(root)
                else:
                    rejects(lambda: cache.prepare(root), 'cache changed during publication')
            first = root/'atan-special.corpus'
            if first.stat().st_mode & 0o777 != 0o600:
                raise RuntimeError('concurrent cache winner was replaced')
            if not valid and first.read_bytes() != b'corrupt race':
                raise RuntimeError('concurrent corrupt cache was repaired')
            if list(root.glob('.atan-cache-*')):
                raise RuntimeError('concurrent publication leaked staging')
        # Execute preparation and cleanup against an alternate directory. Graph
        # checks cover direct consumers and overridden gates without building a
        # second SDK or running concurrent compiler jobs.
        alternate = root/'alternate'
        alternate.mkdir()
        shutil.copy2(source/'atan-seeded.corpus', alternate)
        command = ['make', '-j1', '--no-print-directory', 'PREFIX='+args.prefix,
                   'CORPUS_DIR='+str(alternate)]
        for target in ['prepare-atan-corpus', 'clean-atan-corpus']:
            result = subprocess.run(command+[target], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise RuntimeError('alternate cache Make target failed: '+result.stderr[-500:])
        if any((alternate/name).exists() for name in cache.EXPECTED):
            raise RuntimeError('alternate cache clean left files')
        if not (alternate/'atan-seeded.corpus').is_file():
            raise RuntimeError('alternate cache clean removed literal seeds')
    make_graph(args.prefix)
    print('atan cache precision/seed/pinned-byte, corruption/race/I/O/publication and Make graph/alternate-directory controls pass')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit('atan cache controls: FAIL: '+str(error))
