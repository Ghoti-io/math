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
"""Show that the atan2/exp/log/pow/hypot checks fail on planted defects (CAP-1).

The companion of check-planted.py for src/elementary/explog.c, atan2.c and
hypot.c.  A test that has never been seen to fail may measure nothing.  For
each defect below, this builds a copy of src/elementary with one literal
replacement applied (the replacement must match exactly once and must change
the file), links the copy with testElementary's object, and requires the check
named for it to fail.  The unplanted copy is the control: it must pass, which is
what makes a failure mean the defect and not the build.

Five families:

  oracle   a defect that the accuracy check must catch (Elementary.
           CorpusIsWithinOneUlp): a coefficient or table entry wrong by more
           than rounding, a reduction constant, a threshold or a scaling step
           moved
  special  a defect in a branch of the special values or the exceptions, caught
           by the test named (Annex F is tested row by row)
  hash     a defect too small for the accuracy bounds to see (a coefficient
           perturbed by one unit in its last place) that the committed corpus
           hash must still catch, because a different bit on one target is what
           the cross-target gate exists for.  The corpus holds witnesses for
           these, found by search (gen_corpus_elem.py, WITNESSES)
  table    a defect in a table that no corpus input can show, caught by
           testElementary_tables, which checks every row against an independent
           series (built here from the planted copy of the sources)
  corpus   a defect in the oracle's data, not the library: a wrong answer, a
           truncated file, a missing file and a changed hash line, which the
           tests must refuse

What is NOT planted, and why (story 4).  Every defect that moves a result by
less than a rounding for all but a vanishing share of inputs is invisible to any
test that runs the function, however many inputs it has, and is accepted:

  - the high-order polynomial coefficients: exp's c1 .. c3 (weights r^3 .. r^5,
    r <= 2.7e-3), log's P3 .. P5, pow's R1 up, R2 down and R3 .. R6, the arctangent's direct
    P3 .. P6 and the Taylor coefficients G3 .. G8 of the rows.  One unit in the last
    place of such a coefficient moves a result by 2^-80 of itself or less, and
    changes a correctly rounded result for about one argument in 2^27 or fewer.
    Measured for each of these but G7 and G8: searching 4e7 random arguments per
    direction, drawn where the coefficient has most weight, found no witness
    (G3 to G6 only for row 40; pow's R1 up and R2 down: none in 2e8, R1 down: one
    in 1e8; R1 and R2 enter through a sum that rounds at 2^-54 while a unit in
    their last place is 2^-62 or less, so they change a result in about one input
    in 2^27).  G7 and G8 have weights 2^-49 and 2^-56 before their coefficients
    and are as invisible as G6.  A coefficient that is wrong by
    more than that is planted, with the size at which the accuracy check sees
    it (a few times 2^-57 of the result)
  - the "lo" columns of the tables (exp's 2^(j/128) low parts, log's t_lo, the
    arctangent's atan F lo) by one unit in the last place: each is a rounding
    correction of about 2^-54 of the value, so one ulp of it is 2^-107.  A
    zeroed one is planted and seen
  - the starting table of the reciprocal square root (gmath_hypot's, now the portable gmath_sqrt's: it only starts
    a Newton iteration, which converges to the same value from any start within
    2^-9; an entry that is off by up to 2^-9 changes no result.  A start that is
    wrong by more is seen by testElementary_tables, which checks each entry
  - the thresholds that are margins of the design and not boundaries a result
    can tell: pow's early exit for |y| >= 2^64 (the same overflow or underflow
    follows from the general path, without the spurious exception it would
    raise), atan2's and hypot's scale limits at 2^600 and 2^300 (conservative: a
    limit twice as far gives the same bits)
  - rows 65 to 127 of the arctangent table, which repeat row 64 and are never
    read, and rows 0 to 7, which the direct path never reads: testElementary_tables
    checks rows 65 to 127 against row 64 and rows 0 to 7 against the series

Visible only through the corpus hash, by design: one ulp of the coefficients
that carry a witness (see the hash family below).

Run by `make check-planted` from the library directory, with the build's
compile and link flags in the PLANT_* environment variables.
"""

import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SRC = Path("src/elementary")
CORPUS = Path("tests/corpus")
ORACLE_TEST = "Elementary.CorpusIsWithinOneUlp"
SOURCES = ("elem_common.h", "explog.c", "explog_tables.h", "logbase_constants.h", "atan2.c", "atan2_table.h", "hypot.c", "hypot_table.h", "sqrt_impl.h")
OBJECTS = ("explog", "atan2", "hypot")
TABLE_TEST = "tests/unit/test_elementary_tables.cpp"

failures = []
lock = threading.Lock()


def say(msg, err=False):
    """One write per line, so that the pool's output is not interleaved."""
    with lock:
        (sys.stderr if err else sys.stdout).write(msg + "\n")
        (sys.stderr if err else sys.stdout).flush()


def fail(msg):
    failures.append(msg)
    say("check-planted-elem: FAIL: %s" % msg, err=True)


# ---------------------------------------------------------------------------
# Patches.  A patch is (file, old, new): the text old appears exactly once in
# the file of the staged copy.
# ---------------------------------------------------------------------------

def ulp_step(v, how):
    if how == "up":
        return math.nextafter(v, math.inf)
    if how == "down":
        return math.nextafter(v, -math.inf)
    raise ValueError(how)


def hexf(v):
    return float(v).hex()


def array_line(fname, array):
    text = (SRC / fname).read_text()
    m = re.search(r"^(static const double %s\[[^\]]*\] = \{)([^}]*)(\};)$" % re.escape(array), text, re.M)
    if m is None:
        fail("%s is not in %s where the plant looks" % (array, fname))
        return None
    return m


def coef_patch(fname, array, index, how, delta=None):
    """The patch that changes element `index` of the array: one ulp up or down
    (how = "up" / "down"), or by the relative amount delta (how = "rel")."""
    m = array_line(fname, array)
    if m is None:
        return (fname, "", "")
    vals = [v.strip() for v in m.group(2).split(",")]
    v = float.fromhex(vals[index])
    if how == "rel":
        vals[index] = hexf(v * (1.0 + delta))
    elif how == "abs":
        vals[index] = hexf(v + delta)
    else:
        vals[index] = hexf(ulp_step(v, how))
    return (fname, m.group(0), m.group(1) + ", ".join(vals) + m.group(3))


def define_patch(fname, name, value):
    """The patch that sets a #define to the given text."""
    text = (SRC / fname).read_text()
    m = re.search(r"^#define %s (.*)$" % re.escape(name), text, re.M)
    if m is None:
        fail("%s is not in %s where the plant looks" % (name, fname))
        return (fname, "", "")
    return (fname, m.group(0), "#define %s %s" % (name, value))


def row_patch(fname, array, row, col, how, delta=None):
    """The patch that changes column col of row `row` of the table `array`, whose rows are
    `  /* n */ v, v, ...,` (exp), or `  /* n */ {v, v, ...},` (log, atan2)."""
    text = (SRC / fname).read_text()
    start = text.find(array + "[")
    if start < 0:
        fail("%s is not in %s where the plant looks" % (array, fname))
        return (fname, "", "")
    m = re.compile(r"^  /\* *%d \*/ (\{?)(.*?)(\}?),$" % row, re.M).search(text, start)
    if m is None:
        fail("row %d of %s is not where the plant looks" % (row, fname))
        return (fname, "", "")
    vals = [v.strip() for v in m.group(2).split(",")]
    v = float.fromhex(vals[col])
    if how == "zero":
        vals[col] = "0x0.0p+0"
    elif how == "rel":
        vals[col] = hexf(v * (1.0 + delta))
    elif how == "abs":
        vals[col] = hexf(v + delta)
    else:
        vals[col] = hexf(ulp_step(v, how))
    return (fname, m.group(0), m.group(0).split("*/")[0] + "*/ " + m.group(1) + ", ".join(vals) + m.group(3) + ",")


E = "explog.c"
ET = "explog_tables.h"
A = "atan2.c"
AT = "atan2_table.h"
H = "hypot.c"
HT = "hypot_table.h"
EXPTAB = "gmath_exp_tab"
LOGROWS = "gmath_log_rows"
AROWS = "gmath_atan2_rows"


def rel(bits):
    return 2.0 ** -bits


# The coefficients of each polynomial and the size of the change at which the
# accuracy check sees it: a change of delta in coefficient k moves a result by
# about delta times the weight of the term (r^(k+2) for exp, z^(k+2)/z for log,
# ...), and the accuracy bound is 2^-57 or so of the result above the measured
# worst, so each delta below is several times that.
EXP_C = [("c0", 0, rel(36)), ("c1", 1, rel(26)), ("c2", 2, rel(18)), ("c3", 3, rel(10))]
LOG_P = [("P0", 0, rel(44)), ("P1", 1, rel(37)), ("P2", 2, rel(30)), ("P3", 3, rel(23)), ("P4", 4, rel(16)), ("P5", 5, rel(9))]
LOG_R = [("R0", 0, rel(40)), ("R1", 1, rel(33)), ("R2", 2, rel(26)), ("R3", 3, rel(19)), ("R4", 4, rel(12)), ("R5", 5, rel(6)), ("R6", 6, rel(2))]
ATAN_P = [("P0", 0, rel(45)), ("P1", 1, rel(39)), ("P2", 2, rel(33)), ("P3", 3, rel(27)), ("P4", 4, rel(21)), ("P5", 5, rel(15)), ("P6", 6, rel(9))]
ATAN_G = [("G1", 2, rel(44)), ("G2", 3, rel(37)), ("G3", 4, rel(30)), ("G4", 5, rel(23)), ("G5", 6, rel(16)), ("G6", 7, rel(9)), ("G7", 8, rel(2))]

# (name, patches, function, distribution): the coefficients whose change by one
# unit in the last place the corpus hash must see, with the search that found
# the witnesses (the function and the input distribution of the search, see
# gen_corpus_elem.py, WITNESSES).  Built lazily: it reads the generated headers.
def hash_plants():
    out = []
    for how in ("up", "down"):
        out.append(("exp c0 %s one ulp" % how, [coef_patch(ET, "gmath_exp_poly", 0, how)], "exp", 0))
    for label, k in (("P0", 0), ("P1", 1), ("P2", 2)):
        for how in ("up", "down"):
            out.append(("log %s %s one ulp" % (label, how), [coef_patch(ET, "gmath_log_poly", k, how)], "log", 0 if k < 2 else 2))
    for how in ("up", "down"):
        out.append(("pow R0 %s one ulp" % how, [coef_patch(ET, "gmath_log_dd_poly", 0, how)], "pow", 0))
    out.append(("pow R1 down one ulp", [coef_patch(ET, "gmath_log_dd_poly", 1, "down")], "pow", 0))
    out.append(("pow R2 up one ulp", [coef_patch(ET, "gmath_log_dd_poly", 2, "up")], "pow", 2))
    for label, k in (("P0", 0), ("P1", 1), ("P2", 2)):
        for how in ("up", "down"):
            out.append(("atan2 %s %s one ulp" % (label, how), [coef_patch(AT, "gmath_atan2_poly", k, how)], "atan2", 0))
    return out


def row_hash_plants(rows):
    """G1 and G2 of the given rows of the arctangent table, one ulp each way."""
    out = []
    for j in rows:
        for label, col in (("G1", 2), ("G2", 3)):
            for how in ("up", "down"):
                out.append(("atan2 row %d %s %s one ulp" % (j, label, how), [row_patch(AT, AROWS, j, col, how)], "atan2", 1000 + j))
    return out


# ---------------------------------------------------------------------------


def main():
    env = os.environ
    work = Path(env["PLANT_WORK"])
    cc = shlex.split(env["PLANT_CC"])
    cflags = shlex.split(env["PLANT_CFLAGS"])
    cxx = shlex.split(env["PLANT_CXX"])
    ldflags = shlex.split(env["PLANT_LDFLAGS"])
    cxx_include = shlex.split(env["PLANT_CXX_INCLUDE"])
    test_obj = env["PLANT_TEST_OBJ"]
    probe_cflags = shlex.split(env["PLANT_PROBE_CFLAGS"])
    ld_path = env["PLANT_LD_PATH"]
    trig_obj = env["PLANT_TRIG_OBJ"]
    obj_dir = Path(env["PLANT_OBJ_DIR"])
    jobs = int(env.get("PLANT_JOBS", "4"))

    def stage(name, patches):
        """Copy the sources, apply (file, old, new) patches, return the directory (or None)."""
        d = work / name
        d.mkdir(parents=True)
        for f in SOURCES:
            shutil.copy(SRC / f, d / f)
        for fname, old, new in patches:
            text = (d / fname).read_text()
            if old == "" or text.count(old) != 1:
                fail("%s: '%s' matches %d times in %s, not once; the plant has rotted" % (name, old, text.count(old) if old else 0, fname))
                return None
            (d / fname).write_text(text.replace(old, new))
            if (d / fname).read_text() == (SRC / fname).read_text():
                fail("%s: the replacement changed nothing" % name)
                return None
        return d

    DEPENDS = {"explog": ("explog.c", "explog_tables.h", "logbase_constants.h", "elem_common.h"),
               "atan2": ("atan2.c", "atan2_table.h", "elem_common.h"),
               "hypot": ("hypot.c", "hypot_table.h", "sqrt_impl.h", "elem_common.h")}

    def variant(name, patches):
        """stage(), then build the library objects the patches touch (the others are the build's own)
        and link them with testElementary's."""
        d = stage(name, patches)
        if d is None:
            return None
        patched = {p[0] for p in patches}
        objs = []
        for o in OBJECTS:
            if patched & set(DEPENDS[o]):
                r = subprocess.run(cc + cflags + ["-c", str(d / (o + ".c")), "-o", str(d / (o + ".o"))], capture_output=True, text=True)
                if r.returncode != 0:
                    fail("%s: the planted library does not compile:\n%s" % (name, r.stderr))
                    return None
                objs.append(str(d / (o + ".o")))
            else:
                objs.append(str(obj_dir / (o + ".o")))
        r = subprocess.run(cxx + ["-o", str(d / "testElementary"), test_obj] + objs + ldflags, capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the planted test does not link:\n%s%s" % (name, r.stdout, r.stderr))
            return None
        (d / "objs.txt").write_text("\n".join(objs))
        return d

    def table_variant(name, patches):
        """stage(), then build tests/unit/test_elementary_tables.cpp against the planted sources."""
        d = stage(name, patches)
        if d is None:
            return None
        text = Path(TABLE_TEST).read_text()
        for f in ("atan2.c", "explog.c", "hypot.c"):
            inc = '#include "../../src/elementary/%s"' % f
            if text.count(inc) != 1:
                fail("%s: %s no longer includes %s by that name" % (name, TABLE_TEST, f))
                return None
            text = text.replace(inc, '#include "%s"' % (d / f).resolve())
        (d / "test_elementary_tables.cpp").write_text(text)
        r = subprocess.run(cxx + cxx_include + ["-c", str(d / "test_elementary_tables.cpp"), "-o", str(d / "test_elementary_tables.o")], capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the planted table test does not compile:\n%s" % (name, r.stderr))
            return None
        r = subprocess.run(cxx + ["-o", str(d / "testElementaryTables"), str(d / "test_elementary_tables.o")] + ldflags, capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the planted table test does not link:\n%s%s" % (name, r.stdout, r.stderr))
            return None
        return d

    def run_env(corpus_dir=None):
        e = dict(env)
        e["LD_LIBRARY_PATH"] = ld_path + (":" + e["LD_LIBRARY_PATH"] if e.get("LD_LIBRARY_PATH") else "")
        if corpus_dir is not None:
            e["GMATH_TRIG_CORPUS_DIR"] = str(corpus_dir)
        return e

    def run_test(d, corpus_dir=None):
        r = subprocess.run([str(d / "testElementary"), "--gtest_brief=1"], capture_output=True, text=True, env=run_env(corpus_dir))
        failed = sorted(set(re.findall(r"\[\s*FAILED\s*\]\s+(Elementary\.\w+)", r.stdout)))
        return r.returncode, failed, r.stdout

    def expect_test_fails(name, patches, wanted=(ORACLE_TEST,)):
        d = variant(name, patches)
        if d is None:
            return
        rc, failed, out = run_test(d)
        if rc == 0:
            fail("%s: testElementary passed with the defect planted" % name)
        elif not any(w in failed for w in wanted):
            fail("%s: testElementary failed (%s) but not %s:\n%s" % (name, failed, "/".join(wanted), out[-1500:]))
        else:
            say("  ok   %-52s caught by %s" % (name, ", ".join(failed)))

    def build_probe(d):
        exe = d / "corpus-hash"
        objs = (d / "objs.txt").read_text().split("\n")
        rest = [str(obj_dir / o) for o in ("sqrt.o", "round.o", "scale.o", "remainder.o", "extrema.o", "cbrt.o", "floatbasic.o", "floattrig.o", "intround.o", "float_scale.o", "adjacent.o", "fraction_split.o", "exponent_value.o")]  # the exact functions, built by the Makefile
        r = subprocess.run(cc + probe_cflags + ["tools/corpus-hash.c"] + objs + rest + [trig_obj] + shlex.split(os.environ["PLANT_DECIMAL_OBJS"]) + ["-o", str(exe), "-lm"], capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the probe does not build:\n%s" % (d.name, r.stderr))
            return None
        return exe

    def hash_gate(exe, hash_file=CORPUS / "trig.hash"):
        r = subprocess.run(["tools/check-corpus-hash.sh", str(exe), str(CORPUS), str(hash_file)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def expect_hash_fails(name, patches):
        d = variant(name, patches)
        if d is None:
            return
        exe = build_probe(d)
        if exe is None:
            return
        rc, out = hash_gate(exe)
        if rc == 0:
            fail("%s: the corpus hash gate passed with the defect planted" % name)
        elif "FAIL" not in out:
            fail("%s: the hash gate failed without saying FAIL:\n%s" % (name, out))
        else:
            say("  ok   %-52s caught by the corpus hash" % name)

    def expect_table_test_fails(name, patches, wanted):
        d = table_variant(name, patches)
        if d is None:
            return
        r = subprocess.run([str(d / "testElementaryTables"), "--gtest_brief=1"], capture_output=True, text=True, env=run_env())
        failed = sorted(set(re.findall(r"\[\s*FAILED\s*\]\s+(ElementaryTables\.\w+)", r.stdout)))
        if r.returncode == 0:
            fail("%s: testElementary_tables passed with the defect planted" % name)
        elif wanted not in failed:
            fail("%s: testElementary_tables failed (%s) but not %s:\n%s" % (name, failed, wanted, r.stdout[-1500:]))
        else:
            say("  ok   %-52s caught by %s" % (name, wanted))

    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)

    print("check-planted-elem")

    # Every plant is an independent build in its own directory: they are queued and run in a pool.
    tasks = []

    def queued(f):
        def wrapper(*a, **k):
            tasks.append(lambda: f(*a, **k))
        return wrapper

    expect_test_fails = queued(expect_test_fails)
    expect_hash_fails = queued(expect_hash_fails)
    expect_table_test_fails = queued(expect_table_test_fails)

    # The control: the unplanted copy builds the same way, passes the tests and has the committed hash.
    ctl = variant("control", [])
    if ctl is not None:
        rc, failed, out = run_test(ctl)
        if rc != 0:
            fail("control: testElementary fails on the unplanted copy:\n%s" % out[-1500:])
        else:
            print("  ok   control: the unplanted copy passes testElementary")
        exe = build_probe(ctl)
        if exe is not None:
            rc, out = hash_gate(exe)
            if rc != 0:
                fail("control: the hash gate fails on the unplanted copy:\n%s" % out)
            else:
                print("  ok   control: the unplanted copy has the committed hash")

    # ----- oracle: exp -----
    for label, k, delta in EXP_C:
        expect_test_fails("exp/poly %s off by %g" % (label, delta), [coef_patch(ET, "gmath_exp_poly", k, "rel", delta)])
    expect_test_fails("exp/L1 wrong in its last bit", [define_patch(ET, "GMATH_EXP_L1", "0x1.62e42fe800001p-8")])
    expect_test_fails("exp/L2 off by 2^-30", [coef_define(ET, "GMATH_EXP_L2", rel(30))])
    expect_test_fails("exp/magic number 2^52 not 1.5 * 2^52", [define_patch(E, "GMATH_EXP_MAGIC", "0x1.0p52")])
    expect_test_fails("exp/1 + x taken up to 2^-20", [define_patch(E, "GMATH_EXP_TINY", "0x1p-20")])
    expect_test_fails("exp/fast path taken up to 730", [define_patch(E, "GMATH_EXP_FAST_LIMIT", "730.0")])
    expect_test_fails("exp/subnormal scale 2^(k + 999)", [(E, "double s = gmath_double((uint64_t)(k + 1000 + 1023) << 52);", "double s = gmath_double((uint64_t)(k + 999 + 1023) << 52);")])
    expect_test_fails("exp/overflow scale not in two steps", [(E, "return (y * gmath_double((uint64_t)(k - 1 + 1023) << 52)) * 2.0;", "return y * gmath_double((uint64_t)((k > 1023 ? 1023 : k) + 1023) << 52);")])
    expect_test_fails("exp/certain-overflow 710 not 1000", [define_patch(E, "GMATH_EXP_CERTAIN_OVER", "1000.0")])
    expect_test_fails("exp/low part of the table dropped", [(E, "return th + (tl + th * p);", "return th + (0.0 * tl + th * p);")])
    expect_test_fails("exp/pow's xl dropped", [(E, "double r = (a - nd * GMATH_EXP_L2) + xl;", "double r = (a - nd * GMATH_EXP_L2);")])
    expect_test_fails("exp/n from xh alone for pow", [(E, "double t = (has_lo ? xh + xl : xh) * GMATH_EXP_INV_LN2_N;", "double t = (has_lo ? xh : xh + 0.0 * xl) * GMATH_EXP_INV_LN2_N;")])
    for j in (0, 1, 37, 64, 100, 127):
        expect_test_fails("exp/table row %d hi up one ulp" % j, [row_patch(ET, EXPTAB, j, 0, "up")])
    for j in (5, 100):
        expect_test_fails("exp/table row %d lo zeroed" % j, [row_patch(ET, EXPTAB, j, 1, "zero")])

    # ----- oracle: log -----
    for label, k, delta in LOG_P:
        expect_test_fails("log/poly %s off by %g" % (label, delta), [coef_patch(ET, "gmath_log_poly", k, "rel", delta)])
    expect_test_fails("log/LN2_HI wrong in its last bit", [coef_define(ET, "GMATH_LN2_HI", rel(35))])
    expect_test_fails("log/LN2_LO off by 2^-8", [coef_define(ET, "GMATH_LN2_LO", rel(8))])
    expect_test_fails("log/offset pattern shifted", [define_patch(ET, "GMATH_LOG_OFF", "0x3FE6B00000000000ULL")])
    expect_test_fails("log/zl dropped", [(E, "double tail = ((ed * GMATH_LN2_LO + row[2]) + zl) + sc.lo;", "double tail = (ed * GMATH_LN2_LO + row[2]) + sc.lo;")])
    expect_test_fails("log/sc.lo dropped", [(E, "double tail = ((ed * GMATH_LN2_LO + row[2]) + zl) + sc.lo;", "double tail = (ed * GMATH_LN2_LO + row[2]) + zl;")])
    expect_test_fails("log/t_lo dropped", [(E, "double tail = ((ed * GMATH_LN2_LO + row[2]) + zl) + sc.lo;", "double tail = ((ed * GMATH_LN2_LO) + zl) + sc.lo;")])
    expect_test_fails("log/low half of m dropped from z", [(E, "double ml = m - mh;", "double ml = m - m;")])
    expect_test_fails("log/split mask one bit short", [define_patch(E, "GMATH_LOG_LOW_MASK", "0x1ffffffull")])
    expect_test_fails("log/subnormal scale 2^51", [(E, "xb = gmath_bits(gmath_double(xb) * 0x1p52);", "xb = gmath_bits(gmath_double(xb) * 0x1p51);")])
    for j in (0, 33, 74, 75, 127):
        expect_test_fails("log/row %d c up one ulp" % j, [row_patch(ET, LOGROWS, j, 0, "up")])
    for j in (3, 74, 100):
        expect_test_fails("log/row %d t_hi off by 2^-41" % j, [row_patch(ET, LOGROWS, j, 1, "abs", 2.0 ** -41)])
    for j in (20, 110):
        expect_test_fails("log/row %d t_lo zeroed" % j, [row_patch(ET, LOGROWS, j, 2, "zero")])

    # ----- oracle: pow -----
    for label, k, delta in LOG_R:
        expect_test_fails("pow/poly %s off by %g" % (label, delta), [coef_patch(ET, "gmath_log_dd_poly", k, "rel", delta)])
    expect_test_fails("pow/z^2 dropped from the logarithm", [(E, "gmath_pair s2 = gmath_fast_two_sum(s1.hi, -0.5 * p1);", "gmath_pair s2 = gmath_fast_two_sum(s1.hi, 0.0 * p1);")])
    expect_test_fails("pow/z^2 low part dropped", [(E, "(((t - 0.5 * p2) + (zl - zh * zl))", "(((t - 0.0 * p2) + (zl - zh * zl))")])
    expect_test_fails("pow/cubic term dropped", [(E, "(((t - 0.5 * p2) + (zl - zh * zl))", "(((0.0 * t - 0.5 * p2) + (zl - zh * zl))")])
    expect_test_fails("pow/zl dropped", [(E, "(((t - 0.5 * p2) + (zl - zh * zl))", "(((t - 0.5 * p2) + 0.0 * (zl - zh * zl))")])
    expect_hash_fails("pow/zh zl cross term dropped (1 - zh)", [(E, "(((t - 0.5 * p2) + (zl - zh * zl))", "(((t - 0.5 * p2) + (zl - 0.0 * zh * zl))")])
    expect_test_fails("pow/y times the low part of the logarithm dropped", [(E, "double wl = w.lo + y * lg.lo;", "double wl = w.lo;")])
    expect_test_fails("pow/low part of the product dropped", [(E, "double wl = w.lo + y * lg.lo;", "double wl = y * lg.lo;")])
    expect_test_fails("pow/product halves cut at one bit more", [(E, "double yl = y - yh;", "double yl = 0.0 * (y - yh);")])
    expect_test_fails("pow/squared split mask short", [(E, "double zhh = gmath_double(gmath_bits(zh) & ~GMATH_LOG_SPLIT_MASK);", "double zhh = zh;")])

    # ----- oracle: atan2 -----
    for label, k, delta in ATAN_P:
        expect_test_fails("atan2/poly %s off by %g" % (label, delta), [coef_patch(AT, "gmath_atan2_poly", k, "rel", delta)])
    for j in (8, 40, 56):
        for label, col, delta in ATAN_G:
            expect_test_fails("atan2/row %d %s off by %g" % (j, label, delta), [row_patch(AT, AROWS, j, col, "rel", delta)])
    for j in (8, 21, 40, 64):
        expect_test_fails("atan2/row %d atan hi up one ulp" % j, [row_patch(AT, AROWS, j, 0, "up")])
    for j in (21, 40):
        expect_test_fails("atan2/row %d atan lo zeroed" % j, [row_patch(AT, AROWS, j, 1, "zero")])
    expect_test_fails("atan2/pi/2 low part dropped", [define_patch(AT, "GMATH_PIO2_LO", "0x0p+0")])
    expect_test_fails("atan2/pi low part dropped", [define_patch(AT, "GMATH_PI_LO", "0x0p+0")])
    expect_test_fails("atan2/quotient taken as the result below 2^-20", [define_patch(A, "GMATH_ATAN2_TINY", "0x1p-20")])
    expect_test_fails("atan2/direct polynomial taken up to 1/4", [define_patch(A, "GMATH_ATAN2_DIRECT", "0.25")])
    expect_test_fails("atan2/qm cut at 27 bits", [define_patch(A, "GMATH_ATAN2_LOW27", "0x3ffffffull")])
    expect_test_fails("atan2/high half of v has 29 bits", [define_patch(A, "GMATH_ATAN2_LOW26", "0xffffffull")])
    expect_test_fails("atan2/scale limit 2^1020", [define_patch(A, "GMATH_ATAN2_SCALE_LIMIT", "0x1p1020")])
    expect_test_fails("atan2/remainder low part dropped", [(A, "double rem = (u - qm * vh) - qm * vl;", "double rem = (u - qm * vh);")])
    expect_test_fails("atan2/numerator low part dropped", [(A, "double num = (u - f * vh) - f * vl;", "double num = (u - f * vh);")])
    expect_test_fails("atan2/ql dropped", [(A, "c = ql + (qa * w) * poly;", "c = 0.0 * ql + (qa * w) * poly;")])
    expect_test_fails("atan2/reflection sign table", [(A, "static const uint64_t reflect_sign[4] = {0, GMATH_SIGN_BIT, GMATH_SIGN_BIT, 0};", "static const uint64_t reflect_sign[4] = {0, GMATH_SIGN_BIT, 0, 0};")])
    expect_test_fails("atan2/reflection constants", [(A, "static const double reflect_hi[4] = {0.0, GMATH_PIO2_HI, GMATH_PI_HI, GMATH_PIO2_HI};", "static const double reflect_hi[4] = {0.0, GMATH_PIO2_HI, GMATH_PI_HI, GMATH_PI_HI};")])
    expect_test_fails("atan2/octant code ignores the sign of x", [(A, "unsigned code = (unsigned)((xb >> 62) & 2u) | (unsigned)swap;", "unsigned code = (unsigned)swap;")])
    expect_test_fails("atan2/nearest row by truncation", [(A, "double t = qa * 64.0 + GMATH_ATAN2_MAGIC;", "double t = qa * 64.0 - 0.5 + GMATH_ATAN2_MAGIC;")])

    # ----- oracle: hypot -----
    expect_test_fails("hypot/s0 (the square root) off by 1 per cent", [(H, "double s0 = gmath_sqrt_impl(sf);", "double s0 = 1.01 * gmath_sqrt_impl(sf);")])
    expect_test_fails("hypot/lower part dropped", [(H, "double lower = (2.0 * (ah * al + bh * bl) + (al * al + bl * bl)) + lead.lo;", "double lower = (2.0 * (ah * al + bh * bl)) + lead.lo;")])
    expect_test_fails("hypot/cross terms dropped", [(H, "double lower = (2.0 * (ah * al + bh * bl) + (al * al + bl * bl)) + lead.lo;", "double lower = ((al * al + bl * bl)) + lead.lo;")])
    expect_test_fails("hypot/lead.lo dropped", [(H, "double lower = (2.0 * (ah * al + bh * bl) + (al * al + bl * bl)) + lead.lo;", "double lower = (2.0 * (ah * al + bh * bl) + (al * al + bl * bl));")])
    expect_test_fails("hypot/c cut at 27 bits", [define_patch(H, "GMATH_HYPOT_LOW27", "0x3ffffffull")])
    expect_test_fails("hypot/b negligible below 2^-19", [(H, "if (abits - bbits >= ((uint64_t)28 << 52) || bbits == 0) {", "if (abits - bbits >= ((uint64_t)20 << 52) || bbits == 0) {")])
    expect_test_fails("hypot/scale limit 2^1000", [define_patch(H, "GMATH_HYPOT_LIMIT", "0x1p1000")])
    expect_test_fails("hypot/residual without the lower part", [(H, "double resid = (s1 - c * c) + lower;", "double resid = (s1 - c * c);")])
    expect_test_fails("hypot/correction denominator c alone", [(H, "double h = c + resid / (c + s0);", "double h = c + resid / (c + c);")])

    # ----- special: exp, log, pow, atan2, hypot branches -----
    sp = lambda name, patches, *tests: expect_test_fails(name, patches, wanted=tests)
    sp("special/exp(-inf) is not zero", [(E, "return x > 0 ? x : 0.0;", "return x;")], "Elementary.ExpSpecialValuesOverflowUnderflowAndSubnormals")
    sp("special/exp(NaN) is not quiet", [(E, "if (ab > GMATH_INF_BITS) {\n    return gmath_nan_of(x);\n  }\n  if (ab == GMATH_INF_BITS) {\n    return x > 0 ? x : 0.0;", "if (ab > GMATH_INF_BITS) {\n    return x;\n  }\n  if (ab == GMATH_INF_BITS) {\n    return x > 0 ? x : 0.0;")], "Elementary.ExpSpecialValuesOverflowUnderflowAndSubnormals", "Elementary.NonFiniteArgumentsGiveTheSameQuietNan", ORACLE_TEST)
    sp("special/exp overflow raises no exception", [(E, "    return gmath_overflow(0);\n  }\n  if (x < GMATH_EXP_CERTAIN_UNDER) {", "    return gmath_double(GMATH_INF_BITS);\n  }\n  if (x < GMATH_EXP_CERTAIN_UNDER) {")], "Elementary.ExpExceptions")
    sp("special/exp underflow raises no exception", [(E, "    return gmath_underflow(0);\n  }\n  int k;\n  double y = exp_core(x, 0.0, 0, &k);\n  return scale_slow(y, k);", "    return 0.0;\n  }\n  int k;\n  double y = exp_core(x, 0.0, 0, &k);\n  return scale_slow(y, k);")], "Elementary.ExpExceptions")
    sp("special/log(0) is invalid, not divide-by-zero", [(E, "      return gmath_div_by_zero(GMATH_SIGN_BIT);", "      return gmath_invalid();")], "Elementary.LogSpecialValuesAndExceptions")
    sp("special/log(-1) is -inf", [(E, "    if (xb & GMATH_SIGN_BIT) {\n      return gmath_invalid();", "    if (xb & GMATH_SIGN_BIT) {\n      return gmath_div_by_zero(GMATH_SIGN_BIT);")], "Elementary.LogSpecialValuesAndExceptions")
    sp("special/log(+inf) is NaN", [(E, "    if (xb == GMATH_INF_BITS) {\n      return x;\n    }", "    if (xb == GMATH_INF_BITS) {\n      return gmath_invalid();\n    }")], "Elementary.LogSpecialValuesAndExceptions")
    sp("special/pow(x, 0) is NaN for NaN", [(E, "  if (ay == 0 || xb == one) {\n    return 1.0;\n  }", "  if (ay == 0 && ax == GMATH_INF_BITS) {\n    return 1.0;\n  }\n  if (xb == one) {\n    return 1.0;\n  }")], "Elementary.PowSpecialValues")
    sp("special/pow(1, NaN) is NaN", [(E, "  if (ay == 0 || xb == one) {\n    return 1.0;\n  }", "  if (ay == 0) {\n    return 1.0;\n  }")], "Elementary.PowSpecialValues", ORACLE_TEST)
    sp("special/pow(-1, inf) is NaN", [(E, "    if (ax == one) {\n      return 1.0; /* pow(-1, +-inf) */\n    }", "    if (ax == one) {\n      return gmath_invalid();\n    }")], "Elementary.PowSpecialValues")
    sp("special/pow(0.5, inf) is inf", [(E, "    int below = ax < one;", "    int below = ax > one;")], "Elementary.PowSpecialValues")
    sp("special/pow(0, -inf) raises nothing", [(E, "      return ax == 0 ? gmath_div_by_zero(0) : gmath_double(GMATH_INF_BITS);", "      return gmath_double(GMATH_INF_BITS);")], "Elementary.PowSpecialValues", "Elementary.PowExceptions", ORACLE_TEST)
    sp("special/pow odd integer taken for even", [(E, "  return ((m >> sh) & 1) ? 1 : 2;", "  return ((m >> sh) & 1) ? 2 : 1;")], "Elementary.PowSpecialValues", ORACLE_TEST)
    sp("special/pow integer test misses 2^53 and up", [(E, "  if (e >= 1023 + 53) {\n    return 2;\n  }", "  if (e >= 1023 + 53) {\n    return 0;\n  }")], "Elementary.PowSpecialValues", ORACLE_TEST)
    sp("special/pow negative base, non-integer exponent, not NaN", [(E, "  if (xsign && yc == 0) {\n    return gmath_invalid();\n  }", "  if (xsign && yc == 0) {\n    return gmath_div_by_zero(0);\n  }")], "Elementary.PowSpecialValues", "Elementary.PowExceptions", ORACLE_TEST)
    sp("special/pow(-0, odd) loses the sign", [(E, "  uint64_t rsign = xsign & (0 - (uint64_t)(yc == 1));", "  uint64_t rsign = 0;")], "Elementary.PowSpecialValues", ORACLE_TEST)
    sp("special/pow(-inf, y) ignores y's sign", [(E, "    if (!ysign) {\n      return gmath_double(GMATH_INF_BITS | rsign);\n    }\n    return gmath_double(rsign);\n  }\n  if (ax == 0) {", "    if (ysign) {\n      return gmath_double(GMATH_INF_BITS | rsign);\n    }\n    return gmath_double(rsign);\n  }\n  if (ax == 0) {")], "Elementary.PowSpecialValues")
    sp("special/pow(+-0, y < 0) is not infinite", [(E, "    if (ysign) {\n      return gmath_div_by_zero(rsign);\n    }\n    return gmath_double(rsign);", "    if (ysign) {\n      return gmath_double(rsign);\n    }\n    return gmath_div_by_zero(rsign);")], "Elementary.PowSpecialValues", "Elementary.PowExceptions")
    sp("special/pow(-1, finite) is +1", [(E, "    return gmath_double(one | rsign); /* pow(-1, finite y) */", "    return gmath_double(one); /* pow(-1, finite y) */")], "Elementary.PowSpecialValues", ORACLE_TEST)
    sp("special/pow huge y raises a spurious exception", [(E, "  if (ay >= gmath_bits(0x1p64)) {", "  if (0) {")], "Elementary.PowExceptions")
    sp("special/pow overflow with the wrong sign for x > 1", [(E, "    return ((ax > one) == (ysign == 0)) ? gmath_overflow(rsign) : gmath_underflow(rsign);", "    return ((ax > one) != (ysign == 0)) ? gmath_overflow(rsign) : gmath_underflow(rsign);")], "Elementary.PowSpecialValues", ORACLE_TEST)
    sp("special/atan2(+-0, -0) is +-0", [(A, "    return gmath_double(xneg ? (gmath_bits(GMATH_PI_HI) | ys) : ys);\n  }\n  if (ax == 0) {", "    return gmath_double(ys);\n  }\n  if (ax == 0) {")], "Elementary.Atan2QuadrantsAndSignedZeros", ORACLE_TEST)
    sp("special/atan2(inf, -inf) is pi/4", [(A, "gmath_bits(xneg ? GMATH_3PIO4 : GMATH_PIO4)", "gmath_bits(GMATH_PIO4)")], "Elementary.Atan2QuadrantsAndSignedZeros", ORACLE_TEST)
    sp("special/atan2(y, +-0) is not +-pi/2", [(A, "    return gmath_double(gmath_bits(GMATH_PIO2_HI) | ys);\n  }\n  if (ay == GMATH_INF_BITS) {", "    return gmath_double(gmath_bits(GMATH_PIO4) | ys);\n  }\n  if (ay == GMATH_INF_BITS) {")], "Elementary.Atan2QuadrantsAndSignedZeros", ORACLE_TEST)
    sp("special/atan2(y, -inf) is 0", [(A, "  return gmath_double(xneg ? (gmath_bits(GMATH_PI_HI) | ys) : ys);\n}\n\ndouble gmath_atan2", "  return gmath_double(ys);\n}\n\ndouble gmath_atan2")], "Elementary.Atan2QuadrantsAndSignedZeros", ORACLE_TEST)
    sp("special/atan2(NaN, y) is not quiet", [(A, "    return gmath_nan_of(ax > GMATH_INF_BITS ? x : y);", "    return ax > GMATH_INF_BITS ? x : y;")], "Elementary.Atan2QuadrantsAndSignedZeros", "Elementary.NonFiniteArgumentsGiveTheSameQuietNan", ORACLE_TEST)
    sp("special/hypot(inf, NaN) is NaN", [(H, "    if (xb == GMATH_INF_BITS || yb == GMATH_INF_BITS) {\n      return gmath_double(GMATH_INF_BITS);\n    }\n", "")], "Elementary.HypotSpecialValues", ORACLE_TEST)
    sp("special/hypot(x, 0) loses x", [(H, "|| bbits == 0) {\n    return a;", "|| bbits == 0) {\n    return b;")], "Elementary.HypotSpecialValues", ORACLE_TEST)
    sp("special/hypot overflow is silent", [(H, "  return unscale == 1.0 ? h : h * unscale;", "  return unscale == 1.0 ? h : (h * unscale > 1.7976931348623157e308 ? 1.7976931348623157e308 : h * unscale);")], "Elementary.HypotSpecialValues", ORACLE_TEST)

    # ----- hash: one ulp of the coefficients the corpus has witnesses for -----
    for name, patches, fn, dist in hash_plants():
        expect_hash_fails("coefficient/" + name, patches)
    for name, patches, fn, dist in row_hash_plants(range(8, 65)):
        expect_hash_fails("table/" + name, patches)

    # ----- table: a table that no corpus input can show wrong -----
    TT = lambda name, patches, which: expect_table_test_fails(name, patches, "ElementaryTables." + which)
    ktc = table_variant("table-control", [])
    if ktc is not None:
        r = subprocess.run([str(ktc / "testElementaryTables"), "--gtest_brief=1"], capture_output=True, text=True, env=run_env())
        if r.returncode != 0:
            fail("control: testElementary_tables fails on the unplanted copy:\n%s" % r.stdout[-1500:])
        else:
            print("  ok   control: the unplanted copy passes testElementary_tables")
    TT("table/exp row 3 lo zeroed", [row_patch(ET, EXPTAB, 3, 1, "zero")], "ExpTableMatchesTwoToTheJOver128")
    TT("table/exp row 100 hi down one ulp", [row_patch(ET, EXPTAB, 100, 0, "down")], "ExpTableMatchesTwoToTheJOver128")
    TT("table/log row 40 t_lo up one ulp", [row_patch(ET, LOGROWS, 40, 2, "up")], "LogRowsAreMinusLogOfTheirMultiplier")
    TT("table/log row 10 c has 27 bits", [row_patch(ET, LOGROWS, 10, 0, "up")], "LogRowsAreMinusLogOfTheirMultiplier")
    TT("table/log row 74 c not 1", [row_patch(ET, LOGROWS, 74, 0, "up")], "LogRowsAreMinusLogOfTheirMultiplier")
    TT("table/atan2 row 30 lo zeroed", [row_patch(AT, AROWS, 30, 1, "zero")], "Atan2RowsAreTheTaylorSeriesOfArctangent")
    TT("table/atan2 row 3 hi up one ulp (unread)", [row_patch(AT, AROWS, 3, 0, "up")], "Atan2RowsAreTheTaylorSeriesOfArctangent")
    TT("table/atan2 row 100 differs from row 64", [row_patch(AT, AROWS, 100, 2, "up")], "Atan2RowsAreTheTaylorSeriesOfArctangent")
    TT("table/atan2 row 50 G6 doubled", [row_patch(AT, AROWS, 50, 7, "rel", 1.0)], "Atan2RowsAreTheTaylorSeriesOfArctangent")
    TT("table/hypot start row 5 off by 1%", [(HT, hypot_row(5)[0], hypot_row(5)[1])], "HypotReciprocalSquareRootStart")
    TT("table/hypot start row 300 off by 1%", [(HT, hypot_row(300)[0], hypot_row(300)[1])], "HypotReciprocalSquareRootStart")
    TT("table/exp poly c3 off by 2^-6 (the table test sees it)", [coef_patch(ET, "gmath_exp_poly", 3, "rel", rel(6))], "ExpPolynomialOverTheReducedRange")
    TT("table/log poly P5 off by 2^-4", [coef_patch(ET, "gmath_log_poly", 5, "rel", rel(4))], "LogPolynomialsOverTheirRange")
    TT("table/log dd poly R3 off by 2^-4", [coef_patch(ET, "gmath_log_dd_poly", 3, "rel", rel(4))], "LogPolynomialsOverTheirRange")
    TT("table/log2f Taylor quadratic wrong", [(E, "double p = z + (z * z) * (-0.5 + z *", "double p = z + (z * z) * (-0.25 + z *")], "Log2FloatKernelHasSubUlpReserve")
    TT("table/atan2 poly P5 off by 2^-4", [coef_patch(AT, "gmath_atan2_poly", 5, "rel", rel(4))], "Atan2DirectPolynomialOverItsRange")
    TT("table/L1 not 30 bits", [define_patch(ET, "GMATH_EXP_L1", "0x1.62e42fe800001p-8")], "ConstantsAreTheirDefinitions")
    TT("table/ln2 low part dropped", [define_patch(ET, "GMATH_LN2_LO", "0x0p+0")], "ConstantsAreTheirDefinitions")
    TT("table/log index not masked to the table", [(E, "uint64_t j = (tmp >> (52 - GMATH_LOG_ROW_BITS)) & ((1u << GMATH_LOG_ROW_BITS) - 1u);", "uint64_t j = (tmp >> (52 - GMATH_LOG_ROW_BITS)) & ((1u << (GMATH_LOG_ROW_BITS + 1)) - 1u);")], "IndicesAreInRangeForEveryArgument")

    # ----- corpus: the oracle's data is wrong or missing -----
    def corpus_variant(name, edit):
        d = work / name
        shutil.copytree(CORPUS, d)
        edit(d)
        return d

    @queued
    def expect_corpus_refused(name, edit):
        d = corpus_variant("corpus-" + name, edit)
        rc, failed, out = run_test(ctl, d)
        if rc == 0:
            fail("corpus/%s: testElementary passed on a damaged corpus" % name)
        elif ORACLE_TEST not in failed:
            fail("corpus/%s: testElementary failed (%s) but not the oracle test" % (name, failed))
        else:
            say("  ok   %-52s refused by %s" % ("corpus/" + name, ORACLE_TEST))

    def wrong_answer(fn):
        def edit(d):
            lines = (d / (fn + ".corpus")).read_text().split("\n")
            i = next(k for k, l in enumerate(lines) if not l.startswith("#") and l.strip() and k > 600)
            f = lines[i].split()
            f[-2] = "%016x" % (int(f[-2], 16) + 3)
            lines[i] = " ".join(f)
            (d / (fn + ".corpus")).write_text("\n".join(lines))
        return edit

    def short_file(fn):
        def edit(d):
            lines = (d / (fn + ".corpus")).read_text().split("\n")
            (d / (fn + ".corpus")).write_text("\n".join(lines[:200]) + "\n")
        return edit

    def missing_file(fn):
        def edit(d):
            (d / (fn + ".corpus")).unlink()
        return edit

    def empty_file(fn):
        def edit(d):
            (d / (fn + ".corpus")).write_text("# nothing\n")
        return edit

    def wrong_infinity(d):
        # an expected overflow that the library answers with a finite number: change r of the first 'inf' result of exp to DBL_MAX
        lines = (d / "exp.corpus").read_text().split("\n")
        for i, l in enumerate(lines):
            f = l.split()
            if len(f) == 3 and f[1] == "7ff0000000000000" and not l.startswith("#"):
                f[1] = "7fefffffffffffff"
                lines[i] = " ".join(f)
                break
        (d / "exp.corpus").write_text("\n".join(lines))

    if ctl is not None:
        d = corpus_variant("corpus-control", lambda d: None)
        rc, failed, out = run_test(ctl, d)
        if rc != 0:
            fail("corpus control: a copy of the committed corpus fails testElementary:\n%s" % out[-1500:])
        else:
            print("  ok   control: a copy of the committed corpus passes testElementary")
        for fn in ("atan2", "exp", "log", "pow", "hypot"):
            expect_corpus_refused("%s one wrong answer (3 ulp)" % fn, wrong_answer(fn))
            expect_corpus_refused("%s truncated file" % fn, short_file(fn))
            expect_corpus_refused("%s missing file" % fn, missing_file(fn))
            expect_corpus_refused("%s empty file" % fn, empty_file(fn))
        expect_corpus_refused("exp expected infinity answered finite", wrong_infinity)

        # The committed hash file: a changed hash, a changed count, a changed per-function line, an emptied file and a missing one.
        exe = work / "control" / "corpus-hash"
        real = (CORPUS / "trig.hash").read_text()
        real_count = re.search(r"^count (\d+)", real, re.M).group(1)
        fn_line = re.search(r"^fn pow (\w+) (\d+)", real, re.M)
        cases = (("changed hash", "hash 0000000000000000\ncount %s\n" % real_count),
                 ("changed count", re.sub(r"^count \d+", "count 1", real, flags=re.M)),
                 ("changed fn hash", real.replace("fn pow " + fn_line.group(1), "fn pow 0000000000000000")),
                 ("changed fn count", real.replace("fn pow %s %s" % (fn_line.group(1), fn_line.group(2)), "fn pow %s 1" % fn_line.group(1))),
                 ("no fn lines", re.sub(r"^fn .*\n", "", real, flags=re.M)),
                 ("emptied file", ""), ("missing file", False))
        for label, content in cases:
            hf = work / ("hash-" + label.replace(" ", "-"))
            if content is False:
                hf = work / "no-such-hash-file"
            else:
                hf.write_text(content)
            rc, out = hash_gate(exe, hf)
            if rc == 0:
                fail("hash file/%s: the gate passed" % label)
            else:
                say("  ok   %-52s refused by check-corpus-hash" % ("hash file/" + label))

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for fut in [pool.submit(t) for t in tasks]:
            fut.result()

    if failures:
        print("check-planted-elem: %d failure(s)" % len(failures), file=sys.stderr)
        sys.exit(1)
    print("check-planted-elem: every planted defect is caught, and the control passes")


def coef_define(fname, name, delta):
    """The patch that changes a #define'd hexadecimal constant by the relative amount delta."""
    text = (SRC / fname).read_text()
    m = re.search(r"^#define %s (\S+)$" % re.escape(name), text, re.M)
    if m is None:
        fail("%s is not in %s where the plant looks" % (name, fname))
        return (fname, "", "")
    v = float.fromhex(m.group(1))
    return (fname, m.group(0), "#define %s %s" % (name, hexf(v * (1.0 + delta))))


def hypot_row(i):
    """The patch text that changes row i of the hypot starting table by one per cent."""
    text = (SRC / HT).read_text()
    body = re.search(r"gmath_hypot_rsqrt\[[^\]]*\] = \{\n(.*)\};", text, re.S).group(1)
    toks = re.findall(r"-?0x[0-9a-fp.+-]+", body)
    old = toks[i]
    new = hexf(float.fromhex(old) * 1.01)
    return (old, new)


if __name__ == "__main__":
    main()
