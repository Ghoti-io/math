#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Explicit i686/SSE2 or Windows LLP64 validation; never part of native tests.

The caller supplies a compiler, target runner, generated SDK headers and target
GoogleTest. All commands, output, statuses and separate non-LTO objects remain
in --work. A successful status.json is published only after every selected gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys


def validate_identity(actual, target):
    expected = b'pointer ' + (b'32' if target == 'i686' else b'64') + b' long 32 mantissa 64 maxexp 16384\n'
    if actual != expected:
        raise RuntimeError('requested target identity differs: ' + repr(actual))


def file_identity(path):
    path = Path(path)
    return dict(path=str(path), resolved=str(path.resolve()), size=path.stat().st_size,
                mode=path.stat().st_mode & 0o777,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def resolve_runner(command):
    """Resolve observed runner inputs in the caller's directory, before chdir."""
    words = shlex.split(command)
    evidence = dict(requested=command, executable=None, supplied_files=[])
    if words:
        requested = words[0]
        executable = shutil.which(requested)
        evidence['executable'] = dict(requested=requested, resolved=executable)
        for index, word in enumerate(words):
            path = Path(word)
            if path.is_file():
                resolved = path.resolve()
                evidence['supplied_files'].append(dict(argument_index=index,
                    requested=word, identity=file_identity(resolved)))
                words[index] = str(resolved)
        if executable is not None:
            words[0] = str(Path(executable).resolve())
            evidence['executable']['resolved'] = words[0]
            evidence['executable']['identity'] = file_identity(words[0])
    return words, evidence


class CommandRecorder:
    def __init__(self, work):
        self.work = work
        self.commands = []
        self.publish()

    def publish(self):
        (self.work / 'commands.json').write_text(json.dumps(self.commands, indent=2) + '\n')

    def run(self, tag, command, *, expected=0, timeout=120, data=None):
        command = [str(x) for x in command]
        record = dict(tag=tag, command=command, expected_exit=expected)
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
        except OSError as error:
            (self.work / (tag + '.stdout')).write_bytes(b'')
            (self.work / (tag + '.stderr')).write_text(str(error) + '\n')
            record.update(actual_exit=None, outcome='launch-error', error=str(error))
            self.commands.append(record)
            self.publish()
            raise
        try:
            stdout, stderr = process.communicate(data, timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            (self.work / (tag + '.stdout')).write_bytes(stdout)
            (self.work / (tag + '.stderr')).write_bytes(stderr)
            record.update(actual_exit=process.returncode, outcome='timeout', timeout=timeout,
                          process_group=process.pid, group_signal=int(signal.SIGKILL))
            self.commands.append(record)
            self.publish()
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
        (self.work / (tag + '.stdout')).write_bytes(stdout)
        (self.work / (tag + '.stderr')).write_bytes(stderr)
        record.update(actual_exit=process.returncode)
        self.commands.append(record)
        self.publish()
        if process.returncode != expected:
            raise RuntimeError(tag + ': exit ' + str(process.returncode) + '\n' +
                               stderr.decode(errors='replace')[-6000:])
        print(tag + ': exit ' + str(process.returncode), flush=True)
        return stdout.replace(b'\r\n', b'\n')


def main():
    if not __debug__ or sys.flags.optimize:
        raise RuntimeError('target contracts require assertion-enabled Python')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', choices=('i686', 'windows'), required=True)
    p.add_argument('--cc', required=True)
    p.add_argument('--cxx', required=True)
    p.add_argument('--ar', required=True)
    p.add_argument('--objdump', required=True)
    p.add_argument('--nm', required=True)
    p.add_argument('--readelf', default='readelf')
    p.add_argument('--runner', default='')
    p.add_argument('--generated', type=Path, required=True)
    p.add_argument('--gtest-include', type=Path, required=True)
    p.add_argument('--gtest-lib', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    a = p.parse_args()
    for name in ('work', 'generated', 'gtest_include', 'gtest_lib'):
        setattr(a, name, getattr(a, name).resolve())
    root = Path(__file__).resolve().parents[1]
    work = a.work
    work.mkdir(parents=True, exist_ok=True)
    status = work / 'status.json'
    status.unlink(missing_ok=True)
    recorder = CommandRecorder(work)
    commands, run = recorder.commands, recorder.run
    runner, runner_evidence = resolve_runner(a.runner)
    a.runner = shlex.join(runner)
    os.chdir(root)
    if not (a.generated / 'ghoti.io/math/libver_gen.h').is_file():
        raise RuntimeError('generated SDK header absent: ' + str(a.generated))
    for path in [a.gtest_include / 'gtest/gtest.h', a.gtest_lib / 'libgtest.a',
                 a.gtest_lib / 'libgtest_main.a']:
        if not path.is_file():
            raise RuntimeError('target GoogleTest input absent: ' + str(path))
    external = dict(generated_sdk_header=file_identity(a.generated / 'ghoti.io/math/libver_gen.h'),
                    gtest_headers=[file_identity(path) for path in sorted(
                        (a.gtest_include / 'gtest').rglob('*')) if path.is_file()],
                    gtest_archives=[file_identity(a.gtest_lib / name)
                                    for name in ('libgtest.a', 'libgtest_main.a')],
                    runner=runner_evidence)
    (work / 'external-input-identities.json').write_text(json.dumps(external, indent=2) + '\n')
    population = {}
    for path in sorted([*root.glob('src/**/*'), *root.glob('include/**/*'), *root.glob('tests/corpus/*'),
                        *root.glob('tools/*.py'), *root.glob('tools/*.c'), *root.glob('tools/*.h'),
                        *root.glob('tests/*.h'), root / 'tests/unit/test_currentint.cpp']):
        if path.is_file():
            population[str(path.relative_to(root))] = dict(size=path.stat().st_size,
                mode=path.stat().st_mode & 0o777, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (work / 'input-identities.json').write_text(json.dumps(population, indent=2) + '\n')
    (work / 'runner-source.py').write_bytes(Path(__file__).read_bytes())
    def py(tag, script, *args, timeout=1800):
        return run(tag, [sys.executable, root / 'tools' / script, *args], timeout=timeout)

    cc, cxx = shlex.split(a.cc), shlex.split(a.cxx)
    fp = ['-msse2', '-mfpmath=sse'] if a.target == 'i686' else []
    strict = ['-std=c17', '-O2', '-pedantic-errors', '-Wall', '-Wextra', '-Werror',
              '-ffp-contract=off', '-fno-lto', *fp]
    include = ['-I' + str(root / 'include'), '-I' + str(a.generated.resolve())]
    suffix = '.exe' if a.target == 'windows' else ''
    libs = ['-lm']
    for tag, tool in [('compiler', cc), ('cxx', cxx), ('runner-version', runner)]:
        if tool:
            run(tag, [*tool, '--version'])
    identity = work / 'identity.c'
    identity.write_text('#include <stdio.h>\n#include <limits.h>\n#include <float.h>\n'
                        'int main(void) { printf("pointer %zu long %zu mantissa %d maxexp %d\\n",'
                        'sizeof(void*)*CHAR_BIT,sizeof(long)*CHAR_BIT,LDBL_MANT_DIG,LDBL_MAX_EXP);return 0;}\n')
    identity_exe = work / ('identity' + suffix)
    run('identity-compile', [*cc, *strict, identity, '-o', identity_exe])
    actual = run('identity', [*runner, identity_exe])
    validate_identity(actual, a.target)
    # A real good observation must precede the identity rejecting control.
    try:
        validate_identity(actual, 'windows' if a.target == 'i686' else 'i686')
    except RuntimeError as error:
        if 'requested target identity differs' not in str(error):
            raise
    else:
        raise RuntimeError('wrong-identity control escaped')
    for field, replacement in [(b'long 32', b'long 64'), (b'mantissa 64', b'mantissa 53')]:
        try:
            validate_identity(actual.replace(field, replacement), a.target)
        except RuntimeError as error:
            if 'requested target identity differs' not in str(error):
                raise
        else:
            raise RuntimeError('wrong-width control escaped')
    (work / 'identity-control.txt').write_text('good actual identity accepted; wrong long64 identity rejected\n')
    sources = sorted((root / 'src').rglob('*.c'))
    objects = []
    for source in sources:
        obj = work / (source.stem + '.o')
        run('compile-' + source.stem, [*cc, *strict, *include, '-DGMATH_BUILD', '-c', source, '-o', obj], timeout=600)
        objects.append(obj)
    archive = work / 'libmath.a'
    archive.unlink(missing_ok=True)
    run('archive', [*shlex.split(a.ar), 'rcs', archive, *objects])
    run('archive-symbols', [*shlex.split(a.nm), '-g', archive])

    def client(name, source, linkage=None, imported=False):
        obj, binary = work / (name + '-caller.o'), work / (name + suffix)
        run(name + '-compile', [*cc, *strict, *include, *([] if imported else ['-DGMATH_STATIC']), '-c', root / source, '-o', obj])
        run(name + '-link', [*cc, *fp, '-fno-lto', obj, *(linkage or [archive]), *libs,
                            *(['-Wl,--stack,8388608'] if a.target == 'windows' else []), '-o', binary])
        run(name + '-relocations', [*shlex.split(a.objdump), '-r', obj])
        # Existing checkers accept a single executable path, so use an explicit
        # runner wrapper. exec preserves process failures; no output is hidden.
        wrapper = work / (name + '-run')
        wrapper.write_text('#!/bin/sh\nexec ' + shlex.join([*runner, str(binary)]) + ' "$@"\n')
        wrapper.chmod(0o755)
        return wrapper

    corpus = root / 'tests/corpus'
    legacy = client('legacy', 'tools/corpus-hash.c')
    stdout = run('legacy', [legacy, corpus], timeout=300)
    if len(stdout) != 7319 or hashlib.sha256(stdout).hexdigest() != '0d972320da7b26f67e45263b52dae60056cc09947bd7342450d97d2fd18ad480':
        raise RuntimeError('complete legacy stdout differs')
    # Reuse the calibrated strict downstream source gate and its numerical and
    # warning plants, in addition to the genuine static archive client above.
    py('strict', 'check-strict-build.py', '--cc', a.cc, '--fp-flags=' + ' '.join(fp),
       '--runner', a.runner, '--exe-suffix', suffix, '--platform-libs=-lm', '--generated', a.generated,
       '--work', work / 'strict', timeout=1800)
    current = client('currentint', 'tools/probe-currentint.c')
    py('currentint', 'check-currentint.py', '--probe', current)
    py('currentint-controls', 'check-currentint-controls.py', '--probe', current)
    run('currentint-state', [current, '--control-cases'])
    intround = client('intround', 'tools/probe-intround.c')
    observed = run('intround', [intround, corpus])
    (work / 'intround-normalized.stdout').write_bytes(observed)
    py('intround-check', 'check-intround-output.py', work / 'intround-normalized.stdout', corpus)
    scale = client('long-scale', 'tools/probe-long-scale.c')
    run('long-scale-raw-diagnostics', [scale, '--diagnostics'])
    py('long-scale-payloads', 'check-long-scale.py', corpus)
    py('long-scale-controls', 'check-long-scale-output.py', scale, '--corpus', corpus, '--long-bits', '32')
    scale_source = (root / 'src/elementary/long_scale.c').read_text()
    anchor = 'return gmath_scalbn(x, k);'
    if scale_source.count(anchor) != 1:
        raise RuntimeError('long-scale compiled flag control anchor changed')
    for label, operation in [('good', None), ('lose-uf', 'feclearexcept(FE_UNDERFLOW)'),
                             ('lose-ix', 'feclearexcept(FE_INEXACT)'),
                             ('extra-divzero', 'feraiseexcept(FE_DIVBYZERO)')]:
        text = scale_source if operation is None else scale_source.replace(anchor,
            'double value = gmath_scalbn(x, k); (void)' + operation + '; return value;', 1)
        src, obj = work / ('scale-' + label + '.c'), work / ('scale-' + label + '.o')
        src.write_text('#include <fenv.h>\n' + text)
        run('scale-' + label + '-source-compile', [*cc, *strict, *include,
             '-DGMATH_STATIC', '-c', src, '-o', obj])
        binary = client('scale-' + label, 'tools/probe-long-scale.c', [obj, archive])
        run('scale-' + label, [binary, corpus], expected=0 if operation is None else 1)
        if operation is not None:
            error = (work / ('scale-' + label + '.stderr')).read_bytes()
            if b'long scale mismatch width64' not in error or b'long scale mismatch width32' in error:
                raise RuntimeError('long-scale flag control failed outside intended double assertion: ' + label)
    unit_obj, unit = work / 'currentint-unit.o', work / ('currentint-unit' + suffix)
    run('unit-compile', [*cxx, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-ffp-contract=off', '-fno-lto', *fp, *include, '-DGMATH_STATIC',
                        '-I' + str(a.gtest_include.resolve()), '-I' + str(root / 'tests'),
                        '-c', root / 'tests/unit/test_currentint.cpp', '-o', unit_obj])
    run('unit-link', [*cxx, *fp, unit_obj, archive, a.gtest_lib / 'libgtest_main.a',
                      a.gtest_lib / 'libgtest.a', '-pthread', *libs, '-o', unit])
    unit_out = run('unit', [*runner, unit, '--gtest_color=no'])
    boundary = b'[       OK ] CurrentInteger.NativeLong32ChecksTheRoundedBoundaryBeforeInexact'
    if boundary not in unit_out or b'[  SKIPPED ]' in unit_out or b'[  PASSED  ] 6 tests.' not in unit_out:
        raise RuntimeError('native32 boundary unit did not execute all six tests')
    # Real compiled faults are separate from transcript/loader controls. Use the
    # existing portable path so these controls exercise the shared boundary and
    # state assertions even when the production target admits hardware calls.
    source = (root / 'src/elementary/current_intround.c').read_text()
    marker = 'uint64_t sign ='
    mutations = [('good', source),
                 ('numerical', source.replace('magnitude > maximum + sign', 'magnitude >= maximum + sign', 1)),
                 ('state', source.replace(marker, 'errno=0;\n  ' + marker, 1))]
    for label, text in mutations:
        if label != 'good' and text == source:
            raise RuntimeError('ineffective compiled control ' + label)
        src, obj = work / ('plant-' + label + '.c'), work / ('plant-' + label + '.o')
        src.write_text('#include <errno.h>\n#include <fenv.h>\n' + text)
        run('plant-' + label + '-source-compile', [*cc, *strict, *include, '-DGMATH_STATIC',
              '-DGMATH_CURRENTINT_PORTABLE', '-I' + str(root / 'src/elementary'), '-c', src, '-o', obj])
        binary = client('plant-' + label, 'tools/probe-currentint.c', [obj, archive])
        run('plant-' + label, [binary, corpus], expected=0 if label == 'good' else 1)
        if label != 'good':
            error = (work / ('plant-' + label + '.stderr')).read_bytes()
            if b'currentint mismatch' not in error:
                raise RuntimeError('compiled control failed outside intended value/state assertion: ' + label)
    basic = client('ld-basic', 'tools/probe-long-double-dd-basic.c', [work / 'long_double_basic.o'])
    ldscale = client('ld-scale', 'tools/probe-long-double-scale.c', [work / 'long_double_scale.o'])
    nine = client('ld-nine', 'tools/probe-long-double-nine.c', [work / 'long_double_nine.o'])
    eleven = client('ld-eleven', 'tools/probe-long-double-eleven.c', [work / 'long_double_eleven.o'])
    seventeen = client('ld-seventeen', 'tools/probe-long-double-seventeen-state.c', [work / 'long_double_seventeen.o'])
    if a.target == 'i686':
        os.environ.update(OBJDUMP=a.objdump, NM=a.nm, READELF=a.readelf)
        for family, caller, production in [('', 'ld-basic', 'basic'), ('-scale', 'ld-scale', 'scale'),
                                            ('-nine', 'ld-nine', 'nine'), ('-eleven', 'ld-eleven', 'eleven'),
                                            ('-seventeen', 'ld-seventeen', 'seventeen')]:
            checker = 'check-long-double' + family + '-abi.py'
            py(caller + '-object-abi', checker, '--object', work / ('long_double_' + production + '.o'))
            py(caller + '-caller-abi', checker, '--caller-object', work / (caller + '-caller.o'))
    py('ld-foundation', 'check-long-double.py', '--probe', basic, '--corpus', corpus / 'long-double-foundation.json')
    py('ld-dd', 'check-long-double-dd.py', '--basic', basic, '--nine', nine, '--corpus', corpus / 'long-double-dd.json')
    py('ld-scale', 'check-long-double-scale.py', '--probe', ldscale, '--corpus', corpus / 'long-double-scale.json')
    py('ld-nine', 'check-long-double-nine.py', '--probe', nine, '--directory', corpus)
    py('ld-eleven', 'check-long-double-eleven.py', '--probe', eleven, '--directory', corpus, '--native-only')
    os.environ['LONG_DOUBLE_SEVENTEEN_EVIDENCE'] = str(work / 'seventeen-evidence')
    py('ld-seventeen', 'check-long-double-seventeen.py', '--probe', seventeen, '--directory', corpus, '--native-only', '--state-repetitions', '24')
    if a.target == 'windows':
        dll, implib = work / 'math.dll', work / 'libmath.dll.a'
        run('dll-link', [*cc, '-shared', *objects, '-Wl,--out-implib,' + str(implib), '-o', dll])
        run('dll-exports', [*shlex.split(a.objdump), '-p', dll])
        # Compile again without GMATH_STATIC: this must import real DLL APIs.
        obj, binary = work / 'dll-caller.o', work / 'dll-client.exe'
        run('dll-client-compile', [*cc, *strict, *include, '-c', root / 'tools/corpus-hash.c', '-o', obj])
        run('dll-client-link', [*cc, obj, implib, *libs, '-Wl,--stack,8388608', '-o', binary])
        imports = run('dll-client-imports', [*shlex.split(a.objdump), '-p', binary])
        if b'math.dll' not in imports or b'gmath_' not in imports:
            raise RuntimeError('DLL client has no public math imports')
        if run('dll-client', [*runner, binary, corpus], timeout=300) != stdout:
            raise RuntimeError('DLL legacy stdout differs')
        # Native long-double public entry points must cross the DLL as well.
        for name, source, checker, options in [
            ('dll-basic', 'tools/probe-long-double-dd-basic.c', 'check-long-double.py', ['--corpus', corpus / 'long-double-foundation.json']),
            ('dll-scale', 'tools/probe-long-double-scale.c', 'check-long-double-scale.py', ['--corpus', corpus / 'long-double-scale.json']),
            ('dll-nine', 'tools/probe-long-double-nine.c', 'check-long-double-nine.py', ['--directory', corpus]),
            ('dll-eleven', 'tools/probe-long-double-eleven.c', 'check-long-double-eleven.py', ['--directory', corpus, '--native-only']),
            ('dll-seventeen', 'tools/probe-long-double-seventeen-state.c', 'check-long-double-seventeen.py', ['--directory', corpus, '--native-only', '--state-repetitions', '24'])]:
            wrapper = client(name, source, [implib], imported=True)
            if name == 'dll-seventeen':
                os.environ['LONG_DOUBLE_SEVENTEEN_EVIDENCE'] = str(work / 'dll-seventeen-evidence')
            py(name, checker, '--probe', wrapper, *options)
    status.write_text(json.dumps(dict(actual_exit=0, target=a.target,
                      identity=actual.decode().strip(), commands=commands,
                      limits='Emulated target execution; PE runtime/symbol/relocation evidence is distinct from ELF SysV instruction/CFI proofs.'), indent=2) + '\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit('target contracts: FAIL: ' + str(error))
