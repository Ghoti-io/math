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
    oracle.py fit-logbase                   print split inverse-ln(2)/ln(10) constants
    oracle.py fit-atan2                     print src/elementary/atan2_table.h
    oracle.py fit-hypot                     print src/elementary/hypot_table.h
    oracle.py corpus --out DIR --seed N     write the committed-size corpus (sin, cos, tan, atan2, exp, log, pow, hypot,
                                    and sqrt, floor, ceil, trunc, round, rint, fabs, copysign, scalbn, frexp, ilogb,
                                    and decimal_parse, decimal_shortest)
    oracle.py fresh  --out DIR --seed N     write a small sample drawn now
    oracle.py logbase --out DIR --seed N --count N
                                           write log2/log10/log2f reference corpora
    oracle.py fresh-logbase --out DIR --seed N
                                           write a fresh base-logarithm sample
    oracle.py floattrig --out DIR --seed N --count N
                                           write binary32 trig references
    oracle.py fresh-floattrig --out DIR --seed N
                                           write a fresh binary32 trig sample
    oracle.py floatbasic --out DIR --seed N --count N
                                           write exact binary32 basic references
    oracle.py fresh-floatbasic --out DIR --seed N
                                           write a fresh binary32 sample
    oracle.py fit-floattrig-reduce [--out FILE]
                                           generate certified binary32 2/pi residues
    oracle.py fit-cbrt                       generate cube-root seed table
    oracle.py cbrt --out DIR --seed N --count N
                                           write real cube-root references
    oracle.py fresh-cbrt --out DIR --seed N  write a fresh cube-root sample
    oracle.py intround --out DIR --seed N --count N
                                           write exact integer-return rounding references
    oracle.py fresh-intround --out DIR --seed N  write a fresh exact integer sample
    oracle.py atanf --out DIR --seed N --count N
                                           write binary32 unary arctangent references
    oracle.py fresh-atanf --out DIR --seed N  write a fresh unary arctangent sample
    oracle.py atan2f --out DIR --seed N --count N
                                           write binary32 atan2 references
    oracle.py fresh-atan2f --out DIR --seed N  write a fresh binary32 atan2 sample
    oracle.py budget-atan2f                 certify the binary32 atan2 model
    oracle.py hypotf --out DIR --seed N --count N
                                           write binary32 hypotenuse references
    oracle.py fresh-hypotf --out DIR --seed N  write a fresh hypotenuse sample
    oracle.py budget-hypotf                 certify the binary32 hypotenuse model
    oracle.py budget-log10f                 certify the binary32 base-ten error budget
    oracle.py log10f --out DIR --seed N --count N
                                           write binary32 base-ten logarithm references
    oracle.py fresh-log10f --out DIR --seed N  write a fresh binary32 base-ten sample
    oracle.py logf --out DIR --seed N --count N
                                           write binary32 natural logarithm references
    oracle.py fresh-logf --out DIR --seed N  write a fresh binary32 natural-log sample
    oracle.py expf --out DIR --seed N --count N
                                           write binary32 natural exponential references
    oracle.py fresh-expf --out DIR --seed N  write a fresh binary32 natural-exp sample
    oracle.py exp2f --out DIR --seed N --count N
                                           write binary32 binary exponential references
    oracle.py fresh-exp2f --out DIR --seed N write a fresh binary32 exponential sample
    oracle.py exp2 --out DIR --seed N --count N
                                           write binary exponential references
    oracle.py fresh-exp2 --out DIR --seed N  write a fresh binary exponential sample

The reference runs in the pinned image named by containers/IMAGES, never on
the host.  It does not fail open: a missing engine, a missing image or a
version line that differs from the pin is an error, except for `fresh`, which
a machine without the image is allowed to skip, loudly, unless
GHOTI_ORACLE_REQUIRED=1 turns the skip into a failure (exit 1).  A skipped
`fresh` exits 3 so that the caller can tell it from a pass.

The repository directory is mounted at its own host path, so paths mean the
same on both sides.
Float decomposition/scaling (Fraction and pinned MPFR):
    python3 tools/oracle/oracle.py float_scale --out DIR --seed 20261027 --count 1000
    python3 tools/oracle/oracle.py fresh-float_scale --out DIR --seed SEED --count 1000
The random-input count is bounded at50,000; each expands to at most49 exponent
rows. Fresh checks also run the generated raw/state hashes, not just unit values.

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


def engine_run(ref, argv, capture=False, timeout=None):
    cmd = [ENGINE, "run", "--rm", "--userns=keep-id", "-v", "%s:%s:z" % (ROOT, ROOT),
           "-w", ROOT, ref] + argv
    return subprocess.run(cmd, check=False, capture_output=capture, text=True, timeout=timeout)


def check_pin(timeout=None):
    """Return (ref, provenance); raise Unavailable for a missing pinned instrument.

    Optional timeout bounds each engine subprocess and propagates TimeoutExpired.
    """
    if shutil.which(ENGINE) is None:
        raise Unavailable("no container engine (%s) on this machine" % ENGINE)
    ref, want = pin()
    have = subprocess.run([ENGINE, "image", "exists", ref], check=False, timeout=timeout)
    if have.returncode != 0:
        raise Unavailable("the image %s is not built here (make oracle-build)" % ref)
    r = engine_run(ref, ["mpfr-version"], capture=True, timeout=timeout)
    got = r.stdout.strip()
    if r.returncode != 0 or got != want:
        raise SystemExit("oracle.py: %s says '%s', the pin is '%s'; refusing" % (ref, got, want))
    return ref, got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("version", "fit", "fit-kernel", "fit-explog", "fit-logbase", "fit-cbrt", "fit-floattrig-reduce", "fit-atan2", "fit-hypot", "corpus", "fresh", "logbase", "fresh-logbase", "exp2", "fresh-exp2", "cbrt", "fresh-cbrt", "floatbasic", "fresh-floatbasic", "floattrig", "fresh-floattrig", "exp2f", "fresh-exp2f", "expf", "fresh-expf", "logf", "fresh-logf", "log10f", "fresh-log10f", "hypotf", "fresh-hypotf", "atan2f", "fresh-atan2f", "atanf", "fresh-atanf", "intround", "fresh-intround", "float_scale", "fresh-float_scale", "adjacent", "fresh-adjacent", "budget-log10f", "budget-hypotf", "budget-atan2f"))
    ap.add_argument("--out")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--count", type=int, default=3000)
    a = ap.parse_args()
    try:
        ref, prov = check_pin()
    except Unavailable as e:
        if a.cmd in ("fresh", "fresh-logbase", "fresh-exp2", "fresh-cbrt", "fresh-floatbasic", "fresh-floattrig", "fresh-exp2f", "fresh-expf", "fresh-logf", "fresh-log10f", "fresh-hypotf", "fresh-atan2f", "fresh-atanf", "fresh-intround", "fresh-float_scale", "fresh-adjacent") and not REQUIRED:
            sys.stderr.write("oracle: SKIPPED the fresh sample: %s\n" % e)
            sys.stderr.write("oracle: the committed corpus was still checked; "
                             "GHOTI_ORACLE_REQUIRED=1 makes this a failure\n")
            return 3
        sys.stderr.write("oracle: UNAVAILABLE: %s\n" % e)
        return 1
    sys.stderr.write("oracle: %s\n" % prov)
    if a.cmd == "version":
        return 0
    if a.cmd == "budget-atan2f":
        return engine_run(ref, ["python", "tools/oracle/check_atan2f_budget.py"]).returncode
    if a.cmd == "budget-hypotf":
        return engine_run(ref, ["python", "tools/oracle/check_hypotf_budget.py"]).returncode
    if a.cmd == "budget-log10f":
        return engine_run(ref, ["python", "tools/oracle/check_log10f_budget.py"]).returncode
    if a.cmd == "fit":
        return engine_run(ref, ["python", "tools/oracle/fit_coeffs.py"]).returncode
    if a.cmd == "fit-kernel":
        return engine_run(ref, ["python", "tools/oracle/fit_kernel.py"]).returncode
    if a.cmd == "fit-explog":
        return engine_run(ref, ["python", "tools/oracle/fit_explog.py"]).returncode
    if a.cmd == "fit-logbase":
        return engine_run(ref, ["python", "tools/oracle/fit_logbase.py"]).returncode
    if a.cmd == "fit-cbrt":
        return engine_run(ref, ["python", "tools/oracle/gen_cbrt_table.py"]).returncode
    if a.cmd == "fit-floattrig-reduce":
        argv = ["python", "tools/oracle/gen_floattrig_reduce_table.py"]
        if a.out is not None:
            header = os.path.abspath(a.out)
            if not header.startswith(ROOT + os.sep):
                sys.stderr.write("oracle.py: --out must be inside %s\n" % ROOT)
                return 2
            argv += ["--out", header]
        return engine_run(ref, argv).returncode
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
    if a.cmd in ("logbase", "fresh-logbase", "exp2", "fresh-exp2", "cbrt", "fresh-cbrt", "floatbasic", "fresh-floatbasic", "floattrig", "fresh-floattrig", "exp2f", "fresh-exp2f", "expf", "fresh-expf", "logf", "fresh-logf", "log10f", "fresh-log10f", "hypotf", "fresh-hypotf", "atan2f", "fresh-atan2f", "atanf", "fresh-atanf", "intround", "fresh-intround", "float_scale", "fresh-float_scale", "adjacent", "fresh-adjacent"):
        family = a.cmd.removeprefix("fresh-")
        argv = ["python", "tools/oracle/gen_corpus_" + family + ".py", "--out", out,
                "--seed", str(a.seed), "--count", str(a.count)]
        if a.cmd.startswith("fresh-"):
            argv.append("--fresh")
        return engine_run(ref, argv).returncode
    size = "committed" if a.cmd == "corpus" else "fresh"
    for script in ("gen_corpus.py", "gen_corpus_elem.py", "gen_corpus_exact.py", "gen_corpus_decimal.py"):
        rc = engine_run(ref, ["python", "tools/oracle/" + script, "--out", out,
                              "--seed", str(a.seed), "--size", size]).returncode
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
