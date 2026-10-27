#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Identify a caller-declared adjacent baseline and bind its object/build bytes.

This records declared provenance; it does not authenticate that an arbitrary
object was compiled from its claimed revision. Reproduce the own-project build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile

FIELDS=('revision','object_sha256','flags_sha256','compiler_sha256')


def digest_file(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1<<20),b''):result.update(block)
    return result.hexdigest()


def flags_digest(flags):
    words=shlex.split(flags) if isinstance(flags,str) else flags
    if not isinstance(words,list) or not words or any(not isinstance(word,str) for word in words):raise RuntimeError('baseline flags must be a nonempty argument vector')
    return hashlib.sha256(json.dumps(words,separators=(',',':'),ensure_ascii=True).encode('ascii')).hexdigest()


def compiler_digest(command):
    words=shlex.split(command)
    if not words:raise RuntimeError('empty compiler command')
    executable=shutil.which(words[0])
    if executable is None:raise RuntimeError('baseline compiler command is unavailable')
    context=bytes.fromhex(digest_file(Path(executable).resolve()))+json.dumps(words,separators=(',',':'),ensure_ascii=True).encode('ascii')
    return hashlib.sha256(context).hexdigest()


def load(path):
    metadata=json.loads(Path(path).read_text())
    if not isinstance(metadata,dict):raise RuntimeError('baseline metadata must be an object')
    for name in FIELDS:
        value=metadata.get(name);width=40 if name=='revision' else 64
        if not isinstance(value,str) or re.fullmatch('[0-9a-f]{%d}'%width,value) is None:raise RuntimeError('invalid baseline identity field: '+name)
    return metadata


def identity_line(metadata):
    return 'adjacent.baseline declared_revision %s object_sha256 %s flags_sha256 %s compiler_sha256 %s\n'%tuple(metadata[name] for name in FIELDS)


def validate(metadata,object_path,flags,compiler):
    if digest_file(object_path)!=metadata['object_sha256']:raise RuntimeError('baseline object digest differs')
    if flags_digest(flags)!=metadata['flags_sha256']:raise RuntimeError('baseline library flags identity differs')
    if compiler_digest(compiler)!=metadata['compiler_sha256']:raise RuntimeError('baseline compiler identity differs')


def write_header(path,metadata):
    path=Path(path);temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'.',delete=False) as target:
            temporary=Path(target.name)
            target.write('/* Generated baseline identity; caller-declared revision. */\n#define GMATH_ADJACENT_BASELINE_IDENTITY '+json.dumps(identity_line(metadata),ensure_ascii=True)+'\n')
        temporary.replace(path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('object',type=Path);parser.add_argument('metadata',type=Path)
    parser.add_argument('--flags',required=True);parser.add_argument('--cc',required=True);parser.add_argument('--header',type=Path,required=True)
    args=parser.parse_args();metadata=load(args.metadata)
    validate(metadata,args.object,args.flags,args.cc);write_header(args.header,metadata)
    print(identity_line(metadata),end='');return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (RuntimeError,OSError,ValueError) as error:raise SystemExit('adjacent baseline: FAIL: '+str(error))
