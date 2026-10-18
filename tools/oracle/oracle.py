#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
#
# Copyright (C) 2026 Corey Pennycuff
#
# This file is part of Ghoti.io Math.
#
# Ghoti.io Math is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
"""Runs the multiple-precision oracle for gmath_sin, gmath_cos, gmath_tan, gmath_atan2,
gmath_exp, gmath_log, gmath_pow and gmath_hypot.

    oracle.py version                       check the image against its pin
    oracle.py fit                           print src/elementary/trig_tables.h
    oracle.py fit-kernel                    print src/elementary/trig_kernel_table.h
    oracle.py fit-explog                    print src/elementary/explog_tables.h
    oracle.py fit-atan2                     print src/elementary/atan2_table.h
    oracle.py fit-hypot                     print src/elementary/hypot_table.h
    oracle.py corpus --out DIR --seed N     write the committed-size corpus (sin, cos, tan, atan2, exp, log, pow, hypot,
                                    and sqrt, floor, ceil, trunc, round, rint, fabs, copysign, scalbn, frexp, ilogb)
    oracle.py fresh  --out DIR --seed N     write a small sample drawn now

The reference runs in the pinned image named by containers/IMAGES, never on
the host.  It does not fail open: a missing engine, a missing image or a
version line that differs from the pin is an error, except for `fresh`, which
a machine without the image is allowed to skip, loudly, unless
GHOTI_ORACLE_REQUIRED=1 turns the skip into a failure (exit 1).  A skipped
`fresh` exits 3 so that the caller can tell it from a pass.

The repository directory is mounted at its own host path, so paths mean the
same on both sides.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # the library: <lib>/tools/oracle
IMAGES = os.path.join(HERE, "containers", "IMAGES")
REQUIRED = os.environ.get("GHOTI_ORACLE_REQUIRED") == "1"
ENGINE = os.environ.get("GHOTI_CONTAINER_ENGINE", "podman")


class Unavailable(Exception):
    """The reference cannot be reached.  Never caught into a pass."""


def pin():
    with open(IMAGES) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            name, ref, version, _ = line.rstrip("\n").split("\t")
            if name == "mpfr":
                return ref, version
    raise SystemExit("oracle.py: no mpfr line in %s" % IMAGES)


def engine_run(ref, argv, capture=False):
    cmd = [ENGINE, "run", "--rm", "--userns=keep-id", "-v", "%s:%s:z" % (ROOT, ROOT),
           "-w", ROOT, ref] + argv
    return subprocess.run(cmd, check=False, capture_output=capture, text=True)


def check_pin():
    """Return (ref, provenance line); raise Unavailable when the instrument is not the pinned one."""
    if shutil.which(ENGINE) is None:
        raise Unavailable("no container engine (%s) on this machine" % ENGINE)
    ref, want = pin()
    have = subprocess.run([ENGINE, "image", "exists", ref], check=False)
    if have.returncode != 0:
        raise Unavailable("the image %s is not built here (make oracle-build)" % ref)
    r = engine_run(ref, ["mpfr-version"], capture=True)
    got = r.stdout.strip()
    if r.returncode != 0 or got != want:
        raise SystemExit("oracle.py: %s says '%s', the pin is '%s'; refusing" % (ref, got, want))
    return ref, got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("version", "fit", "fit-kernel", "fit-explog", "fit-atan2", "fit-hypot", "corpus", "fresh"))
    ap.add_argument("--out")
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    try:
        ref, prov = check_pin()
    except Unavailable as e:
        if a.cmd == "fresh" and not REQUIRED:
            sys.stderr.write("oracle: SKIPPED the fresh sample: %s\n" % e)
            sys.stderr.write("oracle: the committed corpus was still checked; "
                             "GHOTI_ORACLE_REQUIRED=1 makes this a failure\n")
            return 3
        sys.stderr.write("oracle: UNAVAILABLE: %s\n" % e)
        return 1
    sys.stderr.write("oracle: %s\n" % prov)
    if a.cmd == "version":
        return 0
    if a.cmd == "fit":
        return engine_run(ref, ["python", "tools/oracle/fit_coeffs.py"]).returncode
    if a.cmd == "fit-kernel":
        return engine_run(ref, ["python", "tools/oracle/fit_kernel.py"]).returncode
    if a.cmd == "fit-explog":
        return engine_run(ref, ["python", "tools/oracle/fit_explog.py"]).returncode
    if a.cmd == "fit-atan2":
        return engine_run(ref, ["python", "tools/oracle/fit_atan2.py"]).returncode
    if a.cmd == "fit-hypot":
        return engine_run(ref, ["python", "tools/oracle/fit_hypot.py"]).returncode
    if a.out is None or a.seed is None:
        sys.stderr.write("oracle.py: %s needs --out and --seed\n" % a.cmd)
        return 2
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    if not out.startswith(ROOT + os.sep):
        sys.stderr.write("oracle.py: --out must be inside %s\n" % ROOT)
        return 2
    size = "committed" if a.cmd == "corpus" else "fresh"
    for script in ("gen_corpus.py", "gen_corpus_elem.py", "gen_corpus_exact.py"):
        rc = engine_run(ref, ["python", "tools/oracle/" + script, "--out", out,
                              "--seed", str(a.seed), "--size", size]).returncode
        if rc != 0:
            return rc
    return 0


sys.exit(main())
