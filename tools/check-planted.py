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
"""Show that the sin/cos/tan checks fail on planted defects (CAP-1).

A test that has never been seen to fail may measure nothing.  For each defect
below, this builds a copy of src/elementary with one literal replacement
applied (the replacement must match exactly once and must change the file),
links the copy with testTrig's object, and requires testTrig to fail on the
oracle corpus, naming Trig.CorpusIsWithinOneUlp.  The unplanted copy is the
control: it must pass, which is what makes a failure mean the defect and not
the build.

Four families:

  oracle   a defect in the library that the accuracy check must catch:
           a coefficient or table entry wrong by more than rounding, a
           reduction branch skipped or shortened, a quadrant or sign wrong, a
           fast path taken too far, a kernel term dropped
  hash     a defect too small for the accuracy bounds to see (a coefficient
           perturbed by one unit in its last place) that the committed corpus
           hash must still catch, because a different bit on one target is
           what the cross-target gate exists for
  kernel   a defect in the kernel's table that no corpus input can show, caught
           by testTrig_kernel, which checks every row against an independent
           series (built here from the planted copy of trig.c)
  corpus   a defect in the oracle's data, not the library: a wrong answer, a
           truncated file and a missing file, which testTrig must refuse
           (the oracle test fails, it does not skip)

What is NOT planted, and why (story 3a).  Every defect that moves a result
by less than a rounding for all but a vanishing share of inputs is invisible
to any test that runs the function, however many inputs it has, and is
accepted:

  - one ulp of a polynomial tail coefficient S2, S3, C2, C3, T2 .. T6: the
    term is at most z^2 .. z^6 (z <= 2^-8) times the coefficient's own
    weight, so one ulp of it moves a result by under 2^-89 of itself (2^-103
    for S3, C3), and changes a correctly rounded result for about one argument
    in 2^36 or fewer.  Measured: 3e6 random arguments per direction in each of four ranges
    (the table region, the direct region log-uniform and uniform, and the
    reduced range 0.8 .. 1000) changed no result of sin, cos or tan for any of
    these coefficients in either direction, while S0, C0 and T0 change about
    one in 2^10 of the direct range and S1, C1 and T1 one in 2^22 or 2^20
  - one ulp of a "lo" column (sin_lo, cos_lo) or of d0 or e0: each is a
    rounding correction of about 2^-54 of the value it corrects, so one ulp
    of it is 2^-107; testTrig_kernel checks d0 and e0 exactly against the
    table's own definition (a one-ulp change is seen there) and the lo
    columns to 2^-100 (a zeroed one is seen by the corpus and by that test, a
    one-ulp change of one is not)
  - rows 229 to 255 of the table, which no reduced argument reaches (a >
    pi/4); testTrig_kernel checks them against the series, the corpus cannot

Visible only through the corpus hash, by design: one ulp of S0, C0, T0
(about one argument in 2^10 of the direct range), and of S1, C1 and T1 (one in
2^22), for which gen_corpus.py carries 18 witnesses found by search.

Since story 4 the corpus hash covers eight functions: the probe the hash plants
build links the planted trig.o with the library's own objects for the other five
(PLANT_OTHER_OBJS), and the committed hash file has a line per function.
tools/check-planted-elem.py does the same for atan2, exp, log, pow and hypot.

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
from pathlib import Path

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
other_objs = shlex.split(env["PLANT_OTHER_OBJS"])
SRC = Path("src/elementary")
CORPUS = Path("tests/corpus")
ORACLE_TEST = "Trig.CorpusIsWithinOneUlp"
SOURCES = ("trig.c", "trig_tables.h", "trig_kernel_table.h")

failures = []


def fail(msg):
    failures.append(msg)
    print("check-planted: FAIL: %s" % msg, file=sys.stderr)


def stage(name, patches):
    """Copy the sources, apply (file, old, new) patches, return the directory (or None)."""
    d = work / name
    d.mkdir(parents=True)
    for f in SOURCES:
        shutil.copy(SRC / f, d / f)
    for fname, old, new in patches:
        text = (d / fname).read_text()
        if text.count(old) != 1:
            fail("%s: '%s' matches %d times in %s, not once; the plant has rotted" %
                 (name, old, text.count(old), fname))
            return None
        (d / fname).write_text(text.replace(old, new))
        if (d / fname).read_text() == (SRC / fname).read_text():
            fail("%s: the replacement changed nothing" % name)
            return None
    return d


def variant(name, patches):
    """stage(), then build the library copy and link it with testTrig's object."""
    d = stage(name, patches)
    if d is None:
        return None
    r = subprocess.run(cc + cflags + ["-c", str(d / "trig.c"), "-o", str(d / "trig.o")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail("%s: the planted library does not compile:\n%s" % (name, r.stderr))
        return None
    r = subprocess.run(cxx + ["-o", str(d / "testTrig"), test_obj, str(d / "trig.o")] + ldflags,
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail("%s: the planted test does not link:\n%s%s" % (name, r.stdout, r.stderr))
        return None
    return d


def kernel_variant(name, patches):
    """stage(), then build tests/unit/test_trig_kernel.cpp against the planted trig.c."""
    d = stage(name, patches)
    if d is None:
        return None
    text = Path("tests/unit/test_trig_kernel.cpp").read_text()
    inc = '#include "../../src/elementary/trig.c"'
    if text.count(inc) != 1:
        fail("%s: test_trig_kernel.cpp no longer includes trig.c by that name" % name)
        return None
    (d / "test_trig_kernel.cpp").write_text(text.replace(inc, '#include "%s"' % (d / "trig.c").resolve()))
    r = subprocess.run(cxx + cxx_include + ["-c", str(d / "test_trig_kernel.cpp"), "-o", str(d / "test_trig_kernel.o")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail("%s: the planted kernel test does not compile:\n%s" % (name, r.stderr))
        return None
    r = subprocess.run(cxx + ["-o", str(d / "testTrigKernel"), str(d / "test_trig_kernel.o")] + ldflags,
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail("%s: the planted kernel test does not link:\n%s%s" % (name, r.stdout, r.stderr))
        return None
    return d


def run_test(d, corpus_dir=None):
    e = dict(env)
    e["LD_LIBRARY_PATH"] = ld_path + (":" + e["LD_LIBRARY_PATH"] if e.get("LD_LIBRARY_PATH") else "")
    if corpus_dir is not None:
        e["GMATH_TRIG_CORPUS_DIR"] = str(corpus_dir)
    r = subprocess.run([str(d / "testTrig"), "--gtest_brief=1"], capture_output=True, text=True, env=e)
    failed = sorted(set(re.findall(r"\[\s*FAILED\s*\]\s+(Trig\.\w+)", r.stdout)))
    return r.returncode, failed, r.stdout


def expect_oracle_fails(name, patches):
    d = variant(name, patches)
    if d is None:
        return
    rc, failed, out = run_test(d)
    if rc == 0:
        fail("%s: testTrig passed with the defect planted" % name)
    elif ORACLE_TEST not in failed:
        fail("%s: testTrig failed (%s) but not the oracle test:\n%s" % (name, failed, out[-1500:]))
    else:
        print("  ok   %-34s caught by %s" % (name, ", ".join(failed)))


def build_probe(d, extra=()):
    exe = d / "corpus-hash"
    r = subprocess.run(cc + probe_cflags + list(extra) + ["tools/corpus-hash.c", str(d / "trig.o")] + other_objs + ["-o", str(exe), "-lm"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail("%s: the probe does not build:\n%s" % (d.name, r.stderr))
        return None
    return exe


def hash_gate(exe, hash_file=CORPUS / "trig.hash"):
    r = subprocess.run(["tools/check-corpus-hash.sh", str(exe), str(CORPUS), str(hash_file)],
                       capture_output=True, text=True)
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
        print("  ok   %-34s caught by the corpus hash" % name)


def run_kernel_test(d):
    e = dict(env)
    e["LD_LIBRARY_PATH"] = ld_path + (":" + e["LD_LIBRARY_PATH"] if e.get("LD_LIBRARY_PATH") else "")
    r = subprocess.run([str(d / "testTrigKernel"), "--gtest_brief=1"], capture_output=True, text=True, env=e)
    failed = sorted(set(re.findall(r"\[\s*FAILED\s*\]\s+(TrigKernel\.\w+)", r.stdout)))
    return r.returncode, failed, r.stdout


def expect_kernel_test_fails(name, patches, want):
    d = kernel_variant(name, patches)
    if d is None:
        return
    rc, failed, out = run_kernel_test(d)
    if rc == 0:
        fail("%s: testTrig_kernel passed with the defect planted" % name)
    elif want not in failed:
        fail("%s: testTrig_kernel failed (%s) but not %s:\n%s" % (name, failed, want, out[-1500:]))
    else:
        print("  ok   %-34s caught by %s" % (name, want))


COLUMNS = ("sin_hi", "sin_lo", "cos_hi", "cos_lo", "tan", "d0", "cot", "e0")


def row_patch(k, col, how):
    """A (file, old, new) patch of table row k: column col one ulp up, or zero."""
    text = (SRC / "trig_kernel_table.h").read_text()
    m = re.search(r"^  /\* *%d \*/ \{(.*)\},$" % k, text, re.M)
    if m is None:
        fail("row %d of the table is not where the plant looks" % k)
        return ("trig_kernel_table.h", "", "")
    vals = [v.strip() for v in m.group(1).split(",")]
    i = COLUMNS.index(col)
    v = float.fromhex(vals[i])
    if how == "zero":
        vals[i] = "0x0.0p+0"
    elif how == "up":
        vals[i] = math.nextafter(v, math.inf).hex()
    else:
        vals[i] = math.nextafter(v, -math.inf).hex()
    return ("trig_kernel_table.h", m.group(0), "  /* %3d */ {%s}," % (k, ", ".join(vals)))


shutil.rmtree(work, ignore_errors=True)
work.mkdir(parents=True)

print("check-planted")

# The control: the unplanted copy builds the same way, passes the oracle test
# and has the committed hash.
ctl = variant("control", [])
if ctl is not None:
    rc, failed, out = run_test(ctl)
    if rc != 0:
        fail("control: testTrig fails on the unplanted copy:\n%s" % out[-1500:])
    else:
        print("  ok   control: the unplanted copy passes testTrig")
    exe = build_probe(ctl)
    if exe is not None:
        rc, out = hash_gate(exe)
        if rc != 0:
            fail("control: the hash gate fails on the unplanted copy:\n%s" % out)
        else:
            print("  ok   control: the unplanted copy has the committed hash")

# Oracle-class defects.
T = "trig_tables.h"
K = "trig_kernel_table.h"
C = "trig.c"
# A coefficient wrong in its 9th or 11th hexadecimal digit (2^-36, 2^-44 of itself).
expect_oracle_fails("coefficient/sin S0 off by 2^-36", [(K, "gmath_trig_sin_tail[GMATH_TRIG_SIN_DEGREE + 1] = {-0x1.5555555555555p-3", "gmath_trig_sin_tail[GMATH_TRIG_SIN_DEGREE + 1] = {-0x1.5555555655555p-3")])
expect_oracle_fails("coefficient/sin S0 off by 2^-44", [(K, "gmath_trig_sin_tail[GMATH_TRIG_SIN_DEGREE + 1] = {-0x1.5555555555555p-3", "gmath_trig_sin_tail[GMATH_TRIG_SIN_DEGREE + 1] = {-0x1.5555555555655p-3")])
expect_oracle_fails("coefficient/cos C0 off by 2^-36", [(K, "gmath_trig_cos_tail[GMATH_TRIG_COS_DEGREE + 1] = {-0x1.0000000000000p-1", "gmath_trig_cos_tail[GMATH_TRIG_COS_DEGREE + 1] = {-0x1.0000000100000p-1")])
expect_oracle_fails("coefficient/tan T0 off by 2^-36", [(K, "gmath_trig_tan_tail[GMATH_TRIG_TAN_DEGREE + 1] = {0x1.5555555555555p-2", "gmath_trig_tan_tail[GMATH_TRIG_TAN_DEGREE + 1] = {0x1.5555555655555p-2")])
expect_oracle_fails("coefficient/tan T1 off by 2^-24", [(K, "0x1.1111111111111p-3, 0x1.ba1ba1ba1ba4ep-5", "0x1.1111121111111p-3, 0x1.ba1ba1ba1ba4ep-5")])
expect_oracle_fails("coefficient/sin S1 off by 2^-24", [(K, "0x1.1111111110ea6p-7", "0x1.1111121110ea6p-7")])
expect_oracle_fails("coefficient/cos C1 off by 2^-24", [(K, "0x1.5555555554eaep-5", "0x1.5555565554eaep-5")])
expect_oracle_fails("reduction/skipped (sin, cos, tan)", [(C, "#define GMATH_PIO4 0x1.921fb54442d18p-1", "#define GMATH_PIO4 0x1p20")])
expect_oracle_fails("reduction/no reflection past 1/2", [(C, "if (f[7] & 0x80000000u) {", "if (0 && (f[7] & 0x80000000u)) {")])
expect_oracle_fails("reduction/window of 160 bits not 256", [(C, "a[i] = gmath_two_over_pi[j0 + 2 + 7 - i]; /* least significant first */", "a[i] = i < 3 ? 0u : gmath_two_over_pi[j0 + 2 + 7 - i];")])
expect_oracle_fails("reduction/pi/2 low word dropped", [(C, "hi * GMATH_PIO2_LO + lo * GMATH_PIO2_HI", "lo * GMATH_PIO2_HI")])
expect_oracle_fails("reduction/remainder tail dropped", [(C, "double r = ((pl + qh * l) + qh * ups) + (ph * cosm1 + ql * b);", "double r = ((pl + qh * (l * 0.0)) + qh * ups) + (ph * cosm1 + ql * b);")])
expect_oracle_fails("quadrant/cos sign", [(C, "((n + 1) & 2) ? sg ^ SIGN_BIT : sg", "(n & 2) ? sg ^ SIGN_BIT : sg")])
expect_oracle_fails("quadrant/sin sign", [(C, "(n & 2) ? sign ^ sg ^ SIGN_BIT : sign ^ sg", "sign ^ sg")])
expect_oracle_fails("quadrant/tan sign", [(C, "(n & 1) ? sign ^ rs ^ SIGN_BIT : sign ^ rs", "sign ^ rs")])
expect_oracle_fails("quadrant/sin loses the remainder's sign", [(C, "uint64_t sg = (n & 1) ? 0 : rs;", "uint64_t sg = 0;")])
expect_oracle_fails("fast path/sin returns x up to 2^-20", [(C, "if (ax < 0x1p-28) {\n    return x;\n  }\n  double rh = ax, rl = 0.0, h, l;\n  uint64_t rs;\n  int n = 0;\n  if (ax > GMATH_PIO4) {\n    n = reduce_any(ax, &rh, &rl);\n  }\n  unpack_remainder(rh, rl, &h, &l, &rs);\n  /* Even quadrants", "if (ax < 0x1p-20) {\n    return x;\n  }\n  double rh = ax, rl = 0.0, h, l;\n  uint64_t rs;\n  int n = 0;\n  if (ax > GMATH_PIO4) {\n    n = reduce_any(ax, &rh, &rl);\n  }\n  unpack_remainder(rh, rl, &h, &l, &rs);\n  /* Even quadrants")])

# The kernel (kernel_front and the formulas): each is a defect of the table-driven
# method, not of a number.
expect_oracle_fails("kernel/slice index off by one", [(C, "- GMATH_TRIG_INDEX_BASE) &", "- GMATH_TRIG_INDEX_BASE + 1) &")])
expect_oracle_fails("kernel/b is h rounded to 5 bits too", [(C, "*b = h - double_of(hb & ~((1ull << GMATH_TRIG_SLICE_SHIFT) - 1));", "*b = h - double_of(hb & ~((1ull << (GMATH_TRIG_SLICE_SHIFT + 1)) - 1));")])
expect_oracle_fails("kernel/direct path taken up to 2^-3", [(C, "#define GMATH_TRIG_DIRECT 0x1p-4", "#define GMATH_TRIG_DIRECT 0x1p-3")])
expect_oracle_fails("kernel/cos correction sign of sin", [(C, "e[GMATH_TRIG_COS_LO], -e[GMATH_TRIG_SIN_HI],\n      -e[GMATH_TRIG_SIN_LO], b, l, ups, cosm1);\n  return e[GMATH_TRIG_COS_HI] + corr;", "e[GMATH_TRIG_COS_LO], e[GMATH_TRIG_SIN_HI],\n      e[GMATH_TRIG_SIN_LO], b, l, ups, cosm1);\n  return e[GMATH_TRIG_COS_HI] + corr;")])
expect_oracle_fails("kernel/sin tail ups dropped", [(C, "*ups = u * (((s[3] * z + s[2]) * z + s[1]) * z + s[0]);", "*ups = (u * (((s[3] * z + s[2]) * z + s[1]) * z + s[0])) * 0.0;")])
expect_oracle_fails("kernel/cos tail cosm1 dropped", [(C, "*cosm1 = z * (((c[3] * z + c[2]) * z + c[1]) * z + c[0]);", "*cosm1 = (z * (((c[3] * z + c[2]) * z + c[1]) * z + c[0])) * 0.0;")])
expect_oracle_fails("kernel/tan d0 dropped", [(C, "((cs - th * cc) + e[GMATH_TRIG_TAN_D0])", "((cs - th * cc) + 0.0)")])
expect_oracle_fails("kernel/cot e0 dropped", [(C, "((cc - kh * cs) + e[GMATH_TRIG_COT_E0])", "((cc - kh * cs) + 0.0)")])
expect_oracle_fails("kernel/tan divides by cos_hi only", [(C, "/ (ch + cc);", "/ ch;")])
expect_oracle_fails("kernel/cot refinement dropped", [(C, "return q1 + rem * q1;", "return q1 + rem * 0.0;")])
expect_oracle_fails("kernel/tan direct tail dropped", [(C, "double rest = l + (h * z) * poly;", "double rest = l;")])

# Table entries wrong by one ulp in a column that is more than a rounding
# correction, in the first, a middle and the last reachable row, and in the
# direct row.
for k, col in ((0, "sin_hi"), (37, "cos_hi"), (100, "tan"), (150, "cot"), (228, "sin_hi"), (64, "cos_hi"), (255 - 27, "tan")):
    expect_oracle_fails("table/row %d %s up one ulp" % (k, col), [row_patch(k, col, "up")])
expect_oracle_fails("table/row 256 (a = 0) cos_hi up one ulp", [row_patch(256, "cos_hi", "up")])
# A rounding correction dropped altogether (a zeroed entry is the "wrong entry"
# the one-ulp plants above cannot reach in these columns).
for k, col in ((100, "d0"), (37, "e0"), (150, "sin_lo"), (200, "cos_lo")):
    expect_oracle_fails("table/row %d %s zeroed" % (k, col), [row_patch(k, col, "zero")])

# The fast reduction (reduce_fast): a wrong constant, a limit set too high and
# the last part of pi/2 dropped.  (The 2^-55 floor under which it hands over to
# the exact reduction is not planted: no double below the limit is closer than
# 2^-60 to a multiple of pi/2, so removing the floor changes no result by more
# than about 2^-21 ulp, and a plant that nothing can see is not one.)  Each
# plant here is a result that is wrong only for some of the arguments the fast path takes, which is why the
# corpus has the edges of its range (gen_corpus.py, cw_inputs).
expect_oracle_fails("fast/P1 wrong in its last bit", [(T, "#define GMATH_CW_P1 0x1.921fb54400000p+0", "#define GMATH_CW_P1 0x1.921fb54480000p+0")])
expect_oracle_fails("fast/P2 wrong in its last bit", [(T, "#define GMATH_CW_P2 0x1.0b4611a600000p-34", "#define GMATH_CW_P2 0x1.0b4611a640000p-34")])
expect_oracle_fails("fast/P3 wrong in its 8th hex digit", [(T, "#define GMATH_CW_P3 0x1.3198a2e000000p-69", "#define GMATH_CW_P3 0x1.3198a2f000000p-69")])
expect_oracle_fails("fast/P4 dropped", [(T, "#define GMATH_CW_P4 0x1.b839a252049c1p-104", "#define GMATH_CW_P4 0x0p+0")])
expect_oracle_fails("fast/limit 2^24 not 2^20", [(C, "#define GMATH_CW_LIMIT 0x1p20", "#define GMATH_CW_LIMIT 0x1p24")])
expect_oracle_fails("fast/limit 2^40 not 2^20", [(C, "#define GMATH_CW_LIMIT 0x1p20", "#define GMATH_CW_LIMIT 0x1p40")])
expect_oracle_fails("fast/tail t4 dropped from lo", [(C, "double lo = (a.lo + b.lo) - nd * GMATH_CW_P4;", "double lo = a.lo + b.lo;")])

# The wide fast reduction (reduce_fast_wide, 2^20 <= x < 2^30): the same kinds of
# defect, all seen (the corpus has cw2_inputs of gen_corpus.py there: the
# doubles either side of 2^29 and 2^30, the worst cancellations of every
# binade, and multiples of pi/2 spread over the range).  Accepted as invisible,
# and so not planted: Q6 dropped or wrong, which moves the remainder by
# n * Q6 < 2^-91 against |r| >= 2^-55 (2^-36 of r, under 2^-35 ulp of a
# result); and the last rounding of lo, 2^-104 |r| + 2^-142.
expect_oracle_fails("wide/Q1 wrong in its last bit", [(T, "#define GMATH_CW2_Q1 0x1.921fb40000000p+0", "#define GMATH_CW2_Q1 0x1.921fb00000000p+0")])
expect_oracle_fails("wide/Q2 wrong in its last bit", [(T, "#define GMATH_CW2_Q2 0x1.4442d00000000p-24", "#define GMATH_CW2_Q2 0x1.4442c00000000p-24")])
expect_oracle_fails("wide/Q3 wrong in its last bit", [(T, "#define GMATH_CW2_Q3 0x1.8469880000000p-48", "#define GMATH_CW2_Q3 0x1.8469800000000p-48")])
expect_oracle_fails("wide/Q4 wrong in its last bit", [(T, "#define GMATH_CW2_Q4 0x1.8cc5180000000p-72", "#define GMATH_CW2_Q4 0x1.8cc5100000000p-72")])
expect_oracle_fails("wide/Q5 dropped", [(T, "#define GMATH_CW2_Q5 -0x1.fc8f8c0000000p-97", "#define GMATH_CW2_Q5 0x0p+0")])
expect_oracle_fails("wide/limit 2^34 not 2^30", [(C, "#define GMATH_CW2_LIMIT 0x1p30", "#define GMATH_CW2_LIMIT 0x1p34")])
expect_oracle_fails("wide/limit 2^50 not 2^30", [(C, "#define GMATH_CW2_LIMIT 0x1p30", "#define GMATH_CW2_LIMIT 0x1p50")])
expect_oracle_fails("wide/step Q2 dropped", [(C, "double s2 = d - nd * GMATH_CW2_Q2;", "double s2 = d;")])
expect_oracle_fails("wide/tail e dropped from lo", [(C, "double lo = (a.lo + b.lo) + (c.lo - nd * GMATH_CW2_Q6);", "double lo = 0.0;")])

# Hash-class defects: below the contract, above the committed bits.  One ulp
# of S0, C0 and T0 changes about one argument in 2^10 of the direct range, and
# one ulp of S1, C1 and T1 about one in 2^22, for which the corpus has the
# witnesses of gen_corpus.py (KERNEL_WITNESSES).
SIN_TAIL = "gmath_trig_sin_tail[GMATH_TRIG_SIN_DEGREE + 1] = {"
COS_TAIL = "gmath_trig_cos_tail[GMATH_TRIG_COS_DEGREE + 1] = {"
TAN_TAIL = "gmath_trig_tan_tail[GMATH_TRIG_TAN_DEGREE + 1] = {"
expect_hash_fails("coefficient/sin S0 up one ulp", [(K, SIN_TAIL + "-0x1.5555555555555p-3", SIN_TAIL + "-0x1.5555555555556p-3")])
expect_hash_fails("coefficient/cos C0 up one ulp", [(K, COS_TAIL + "-0x1.0000000000000p-1", COS_TAIL + "-0x1.fffffffffffffp-2")])
expect_hash_fails("coefficient/tan T0 up one ulp", [(K, TAN_TAIL + "0x1.5555555555555p-2", TAN_TAIL + "0x1.5555555555556p-2")])
expect_hash_fails("coefficient/sin S1 up one ulp", [(K, "0x1.1111111110ea6p-7", "0x1.1111111110ea7p-7")])
expect_hash_fails("coefficient/sin S1 down one ulp", [(K, "0x1.1111111110ea6p-7", "0x1.1111111110ea5p-7")])
expect_hash_fails("coefficient/cos C1 up one ulp", [(K, "0x1.5555555554eaep-5", "0x1.5555555554eafp-5")])
expect_hash_fails("coefficient/cos C1 down one ulp", [(K, "0x1.5555555554eaep-5", "0x1.5555555554eadp-5")])
expect_hash_fails("coefficient/tan T1 up one ulp", [(K, "0x1.1111111111111p-3, 0x1.ba1ba1ba1ba4ep-5", "0x1.1111111111112p-3, 0x1.ba1ba1ba1ba4ep-5")])
expect_hash_fails("coefficient/tan T1 down one ulp", [(K, "0x1.1111111111111p-3, 0x1.ba1ba1ba1ba4ep-5", "0x1.1111111111110p-3, 0x1.ba1ba1ba1ba4ep-5")])

# Kernel-class defects: wrong table entries that no input of the corpus can
# show (rounding corrections, rows no argument reaches), seen by testTrig_kernel.
KT = "TrigKernel.TableRowsMatchAnIndependentSeries"
ktc = kernel_variant("kernel-control", [])
if ktc is not None:
    rc, failed, out = run_kernel_test(ktc)
    if rc != 0:
        fail("control: testTrig_kernel fails on the unplanted copy:\n%s" % out[-1500:])
    else:
        print("  ok   control: the unplanted copy passes testTrig_kernel")
expect_kernel_test_fails("table/row 100 d0 up one ulp", [row_patch(100, "d0", "up")], KT)
expect_kernel_test_fails("table/row 37 e0 down one ulp", [row_patch(37, "e0", "down")], KT)
expect_kernel_test_fails("table/row 240 cos_hi up one ulp (unreachable)", [row_patch(240, "cos_hi", "up")], KT)
expect_kernel_test_fails("table/row 5 sin_lo zeroed", [row_patch(5, "sin_lo", "zero")], KT)
expect_kernel_test_fails("table/row 128 cot up one ulp", [row_patch(128, "cot", "up")], KT)
expect_kernel_test_fails("ktest/slice index not masked", [(C, ") & (GMATH_TRIG_ROWS - 1);", ");")], "TrigKernel.TheRowIndexIsInRangeForEveryReducedArgument")
expect_kernel_test_fails("ktest/slice index off by one", [(C, "- GMATH_TRIG_INDEX_BASE) &", "- GMATH_TRIG_INDEX_BASE + 1) &")], "TrigKernel.TheRowIndexIsInRangeForEveryReducedArgument")

# Corpus-class defects: the oracle's data is wrong or missing.
def corpus_variant(name, edit):
    d = work / name
    shutil.copytree(CORPUS, d)
    edit(d)
    return d

def expect_corpus_refused(name, edit):
    d = corpus_variant("corpus-" + name, edit)
    rc, failed, out = run_test(ctl, d)
    if rc == 0:
        fail("corpus/%s: testTrig passed on a damaged corpus" % name)
    elif ORACLE_TEST not in failed:
        fail("corpus/%s: testTrig failed (%s) but not the oracle test" % (name, failed))
    else:
        print("  ok   %-34s refused by %s" % ("corpus/" + name, ORACLE_TEST))

def wrong_answer(d):
    lines = (d / "sin.corpus").read_text().split("\n")
    i = next(k for k, l in enumerate(lines) if not l.startswith("#") and l.strip() and k > 600)
    f = lines[i].split()
    f[1] = "%016x" % (int(f[1], 16) + 3)
    lines[i] = " ".join(f)
    (d / "sin.corpus").write_text("\n".join(lines))

def short_file(d):
    lines = (d / "cos.corpus").read_text().split("\n")
    (d / "cos.corpus").write_text("\n".join(lines[:200]) + "\n")

def missing_file(d):
    (d / "tan.corpus").unlink()

def empty_file(d):
    (d / "sin.corpus").write_text("# nothing\n")

if ctl is not None:
    # The control for these: the unplanted corpus, copied, passes.
    d = corpus_variant("corpus-control", lambda d: None)
    rc, failed, out = run_test(ctl, d)
    if rc != 0:
        fail("corpus control: a copy of the committed corpus fails testTrig:\n%s" % out[-1500:])
    else:
        print("  ok   control: a copy of the committed corpus passes testTrig")
    expect_corpus_refused("one wrong answer (3 ulp)", wrong_answer)
    expect_corpus_refused("truncated file", short_file)
    expect_corpus_refused("missing file", missing_file)
    expect_corpus_refused("empty file", empty_file)

    # The committed hash file: a changed hash, an emptied file and a missing one.
    exe = work / "control" / "corpus-hash"
    real_count = re.search(r"^count (\d+)", (CORPUS / "trig.hash").read_text(), re.M).group(1)
    for label, content in (("changed hash", "hash 0000000000000000\ncount %s\n" % real_count),
                           ("changed count", None),
                           ("emptied file", ""), ("missing file", False)):
        hf = work / ("hash-" + label.replace(" ", "-"))
        if content is False:
            hf = work / "no-such-hash-file"
        elif content is None:
            real = (CORPUS / "trig.hash").read_text()
            hf.write_text(re.sub(r"count \d+", "count 1", real))
        else:
            hf.write_text(content)
        rc, out = hash_gate(exe, hf)
        if rc == 0:
            fail("hash file/%s: the gate passed" % label)
        else:
            print("  ok   %-34s refused by check-corpus-hash" % ("hash file/" + label))

# The skip rule of the fresh-sample check: with no container engine it skips
# loudly (exit 3), and GHOTI_ORACLE_REQUIRED=1 makes the same situation a
# failure (exit 1).  Never a quiet pass.
for required, want_rc, label in (("", 3, "skips loudly without the engine"),
                                 ("1", 1, "fails when the oracle is required")):
    e = dict(env)
    e["GHOTI_CONTAINER_ENGINE"] = "/nonexistent/engine"
    e.pop("GHOTI_ORACLE_REQUIRED", None)
    if required:
        e["GHOTI_ORACLE_REQUIRED"] = required
    r = subprocess.run([sys.executable, "tools/oracle/oracle.py", "fresh", "--out",
                        str(work / "fresh-never"), "--seed", "1"], capture_output=True, text=True, env=e)
    if r.returncode != want_rc or ("SKIPPED" not in r.stderr if want_rc == 3 else "UNAVAILABLE" not in r.stderr):
        fail("oracle fresh sample %s: exit %d (want %d): %s" % (label, r.returncode, want_rc, r.stderr.strip()))
    else:
        print("  ok   %-34s oracle.py fresh %s" % ("oracle/" + ("required" if required else "optional"), label))

if failures:
    print("check-planted: %d failure(s)" % len(failures), file=sys.stderr)
    sys.exit(1)
print("check-planted: every planted defect is caught, and the control passes")
