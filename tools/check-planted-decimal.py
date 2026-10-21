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
"""Show that the checks of the decimal conversions fail on planted defects.

The companion of check-planted-exact.py for src/decimal/ (gmath_decimal_parse,
gmath_decimal_to_double, gmath_decimal_shortest and the integers under them).
A test that has never been seen to fail may measure nothing.  For each defect
below, this builds a copy of those sources with one literal replacement
applied (the replacement must match exactly once and must change the file),
links testDecimal against the copy and requires the test named for it to fail;
for a defect the corpus test catches, the corpus hash gate must fail too,
since it is what the cross-target scripts compare.  The unplanted copy is the
control: it must pass both.

What is NOT planted, and why:

  - the estimate of L in the shortest search (78913 / 2^18 for log10 2): the
    loop that follows corrects any estimate within its three attempts, so an
    estimate off by one changes no result, only the time
  - the order in which the shortest search picks between two candidates
    equally near x (half to even): an exact tie needs x to be a decimal with
    more digits than its shortest spelling, ending in 5 at the cut, inside an
    interval that also holds both neighbours; no double has been found where
    it decides, and the exact search of the oracle would catch one in the
    corpus if it did
  - that the gap below the smallest normal number is not halved (its
    predecessor, the largest subnormal, is one unit below it, as every other
    neighbour is): halving it moves only the lower end of 2^-1022's interval,
    and the shortest spelling of 2^-1022 lies above it, so no result changes
  - the capacity of the integer (4,096 bits): the method's bounds keep every
    operand below 3,800 bits, so a smaller capacity that still holds them
    changes nothing, and one that does not is an ERR_INTERNAL the corpus test
    sees (planted below as a capacity of 64 limbs)

Run by `make check-planted-decimal` from the library directory, with the
build's compile and link flags in the PLANT_* environment variables.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path("src/decimal")
SOURCES = ("bignum.h", "decimal_internal.h", "parse.c", "shortest.c")
CORPUS = Path("tests/corpus")
PARSE = "DecimalCorpus.ParseEqualsTheOracleInBitsAndFlags"
TIERS = "DecimalCorpus.EveryParseTierEqualsTheGeneralTierAndIsTaken"
SHORT = "DecimalCorpus.ShortestEqualsTheOracleAndEveryTierAgrees"
INVERSE = "DecimalInverse.ShortestDigitsReadBackToTheSameDouble"
P, S, B = "parse.c", "shortest.c", "bignum.h"

# (name, file, old, new, the tests one of which must fail, whether the corpus hash must fail)
PLANTS = [
    # --- parse: the truncation of long inputs ---
    ("parse: 700 significant digits kept, not 800", P, "#define GMATH_DECIMAL_KEEP 800", "#define GMATH_DECIMAL_KEEP 700", (PARSE,), True),
    ("parse: the truncated rest stands for 0, not 5", P, "gmath_big_mul_add_u32(&num, 10u, 5u)", "gmath_big_mul_add_u32(&num, 10u, 0u)", (PARSE,), True),
    # Every digit kept: exact, so the corpus agrees, but a long input passes the capacity.
    ("parse: the truncated rest is ignored", P, "  bool sticky = significant > GMATH_DECIMAL_KEEP;", "  bool sticky = false;", ("DecimalToDouble.RoundsInputsLongerThanTheTruncationCorrectly",), False),
    # --- parse: the early decisions ---
    ("parse: infinity from 10^308", P, "  if (lead >= 309) {", "  if (lead >= 308) {", (PARSE,), True),
    ("parse: zero from 10^-324", P, "  if (lead <= -325) {", "  if (lead <= -324) {", (PARSE,), True),
    ("parse: the exponent of the leading digit one low", P, "gmath_decimal_add_saturating(exponent, (uint64_t) (total - 1 - first));", "gmath_decimal_add_saturating(exponent, (uint64_t) (total - 2 - first));", (PARSE,), True),
    ("parse: a zero loses its sign", P, "    bits = sign; /* a zero, of the sign given */", "    bits = 0; /* a zero, of the sign given */", (PARSE,), True),
    # --- parse: the rounding ---
    ("parse: ties away from zero", P, "    if (rem > half || (rem == half && (sticky || (mant & 1u) != 0))) {", "    if (rem >= half) {", (PARSE,), True),
    ("parse: ties to odd", P, "    if (rem > half || (rem == half && (sticky || (mant & 1u) != 0))) {", "    if (rem > half || (rem == half && (sticky || (mant & 1u) == 0))) {", (PARSE,), True),
    ("parse: a tie with a remainder below it rounds to even", P, "    if (rem > half || (rem == half && (sticky || (mant & 1u) != 0))) {", "    if (rem > half || (rem == half && (mant & 1u) != 0)) {", (PARSE,), True),
    ("parse: truncation instead of rounding", P, "    if (rem > half || (rem == half && (sticky || (mant & 1u) != 0))) {\n      mant++;\n    }", "    (void)half;", (PARSE,), True),
    ("parse: the subnormals one bit too precise", P, "  int64_t p = normal ? 53 : ue + 1075;", "  int64_t p = normal ? 53 : ue + 1076;", (PARSE,), True),
    ("parse: the subnormals one bit short", P, "  int64_t p = normal ? 53 : ue + 1075;", "  int64_t p = normal ? 53 : ue + 1074;", (PARSE,), True),
    ("parse: overflow one binade late", P, "  int64_t ue = bq - 1 + b; /* the exponent of the leading bit */\n  if (ue > 1023) {", "  int64_t ue = bq - 1 + b; /* the exponent of the leading bit */\n  if (ue > 1024) {", (PARSE,), True),
    ("parse: the carry into the next binade does not overflow", P, "    ue++;\n    if (ue > 1023) {", "    ue++;\n    if (ue > 1024) {", (PARSE,), True),
    ("parse: a carry keeps the significand at 2^53", P, "  if (mant == ((uint64_t) 1 << 53)) {\n    mant >>= 1;", "  if (mant == ((uint64_t) 1 << 54)) {\n    mant >>= 1;", (PARSE,), True),
    ("parse: underflow flagged for an exact subnormal", P, "  if (inexact) {\n    *flags |= GMATH_DECIMAL_INEXACT;\n    if (!normal) {\n      *flags |= GMATH_DECIMAL_UNDERFLOW;\n    }\n  }", "  if (!normal) {\n    *flags |= GMATH_DECIMAL_UNDERFLOW;\n  }\n  if (inexact) {\n    *flags |= GMATH_DECIMAL_INEXACT;\n  }", (PARSE,), True),
    ("parse: inexact never flagged", P, "  if (inexact) {\n    *flags |= GMATH_DECIMAL_INEXACT;", "  if (inexact) {\n    *flags |= 0;", (PARSE,), True),
    ("parse: q placed one bit low", P, "    int64_t k = 56 - la + lb; /* puts q in (2^55, 2^57) */", "    int64_t k = 55 - la + lb; /* puts q in (2^55, 2^57) */", (PARSE,), True),
    ("parse: a whole number's lost bits ignored", P, "      rest = gmath_big_low_bits_nonzero(&num, la - 57);", "      rest = false;", (PARSE,), True),
    ("parse: the short division's remainder ignored", P, "      rest = r != 0;\n      used = GMATH_DECIMAL_TIER_DIV32;", "      (void) r;\n      rest = false;\n      used = GMATH_DECIMAL_TIER_DIV32;", (PARSE, TIERS), True),
    ("parse: the restoring division's remainder ignored", P, "      rest = !gmath_big_is_zero(&num);\n      used = GMATH_DECIMAL_TIER_RESTORING;", "      rest = false;\n      used = GMATH_DECIMAL_TIER_RESTORING;", (PARSE, TIERS), True),
    # --- parse: the grammar ---
    ("parse: an incomplete exponent consumed", P, "    if (j < length && text[j] >= '0' && text[j] <= '9') {\n      while", "    i = j;\n    if (j < length && text[j] >= '0' && text[j] <= '9') {\n      while", ("DecimalParse.ReadsTheLongestNumberAndStopsBeforeAnIncompleteExponent",), False),
    ("parse: a bare point is a number", P, "  if (int_length == 0 && frac_length == 0) {\n    return GMATH_ERR_FORMAT;", "  if (int_length == 0 && frac_length == 0 && i == int_start) {\n    return GMATH_ERR_FORMAT;", ("DecimalParse.RefusesTextThatDoesNotStartWithANumberAndWritesNothing",), False),
    ("parse: the exponent's sign ignored", P, "      if (exp_negative) {\n        exp10 = -exp10;\n      }", "      (void)exp_negative;", (PARSE,), True),
    # --- shortest ---
    ("shortest: the ends excluded for an even significand", S, "  bool inclusive = (m & 1u) == 0;", "  bool inclusive = false;", (SHORT,), True),
    ("shortest: the ends included for an odd significand", S, "  bool inclusive = (m & 1u) == 0;", "  bool inclusive = true;", (SHORT, INVERSE), True),
    ("shortest: the gap below a power of two not halved", S, "  bool closer_below = frac == 0 && biased > 1;", "  bool closer_below = false;", (SHORT, INVERSE), True),
    ("shortest: the nearest candidate not taken", S, "    if (c < c_lo) {\n      c = c_lo;\n    } else if (c > c_hi) {\n      c = c_hi;\n    }", "    c = c_lo;", (SHORT,), True),
    ("shortest: x rounded down to the candidate", S, "    c += up ? 1u : 0u;", "    c += 0u * (up ? 1u : 0u);", (SHORT,), True),
    ("shortest: one digit fewer than the shortest tried first", S, "  for (int n = 1; n <= 17; ++n) {", "  for (int n = 2; n <= 17; ++n) {", (SHORT,), True),
    ("shortest: trailing zeros kept", S, "  while (c % 10u == 0) {\n    c /= 10u;\n    exponent++;\n  }", "  (void)0;", (SHORT,), True),
    ("shortest: the integer tier takes a fraction", S, "      (e == 0 || (m & (((uint64_t) 1 << -e) - 1u)) == 0)) {", "      true) {", (SHORT, INVERSE), True),
    ("shortest: the shift tier's remainder ignored", S, "    *rest = gmath_big_low_bits_nonzero(&num, k);", "    *rest = false;", (SHORT, INVERSE), True),
    ("shortest: the zero spelled with an exponent", S, "    d.digits[0] = '0';\n    d.length = 1;\n    d.exponent = 0;", "    d.digits[0] = '0';\n    d.length = 1;\n    d.exponent = 1;", (SHORT, "DecimalShortest.ZeroIsOneDigitWithTheSignOfX"), True),
    # --- the integers ---
    ("bignum: a carry lost in multiplication", B, "    a->limb[a->n++] = (uint32_t) carry;", "    (void)0;", (PARSE, SHORT), True),
    ("bignum: a borrow lost in subtraction", B, "    borrow = (t >> 32) & 1u;\n  }\n  for (; borrow", "    borrow = 0;\n  }\n  for (; borrow", (PARSE, SHORT), True),
    ("bignum: comparison by length only", B, "    if (a->limb[i] != b->limb[i]) {\n      return a->limb[i] < b->limb[i] ? -1 : 1;\n    }", "    (void)0;", (PARSE, SHORT), True),
    ("bignum: a shift by whole limbs drops the low limb", B, "    a->limb[words] = a->limb[0] << bits;", "    a->limb[words] = 0;", (PARSE, SHORT), True),
    ("bignum: a capacity of 64 limbs", B, "#define GMATH_BIG_LIMBS 128", "#define GMATH_BIG_LIMBS 64", (PARSE, SHORT), True),
]


def main():
    env = os.environ
    work = Path(env["PLANT_WORK"])
    cc = shlex.split(env["PLANT_CC"])
    cflags = shlex.split(env["PLANT_CFLAGS"])
    cxx = shlex.split(env["PLANT_CXX"])
    ldflags = shlex.split(env["PLANT_LDFLAGS"])
    test_obj = env["PLANT_TEST_OBJ"]
    probe_cflags = shlex.split(env["PLANT_PROBE_CFLAGS"])
    others = shlex.split(env["PLANT_OTHER_OBJS"])
    ld_path = env["PLANT_LD_PATH"]
    failures = []

    def fail(msg):
        failures.append(msg)
        sys.stderr.write("check-planted-decimal: FAIL: %s\n" % msg)

    def run_env():
        e = dict(env)
        e["LD_LIBRARY_PATH"] = ld_path + (":" + e["LD_LIBRARY_PATH"] if e.get("LD_LIBRARY_PATH") else "")
        e.pop("GMATH_TRIG_CORPUS_DIR", None)
        e["GMATH_DECIMAL_SOAK"] = "20000"
        return e

    def stage(name, patch):
        d = work / re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        d.mkdir(parents=True)
        for f in SOURCES:
            shutil.copy(SRC / f, d / f)
        if patch is not None:
            fname, old, new = patch
            text = (d / fname).read_text()
            if text.count(old) != 1:
                fail("%s: the text matches %d times in %s, not once; the plant has rotted" % (name, text.count(old), fname))
                return None
            (d / fname).write_text(text.replace(old, new))
        objs = []
        for c in ("parse", "shortest"):
            r = subprocess.run(cc + cflags + ["-I", str(d), "-c", str(d / (c + ".c")), "-o", str(d / (c + ".o"))],
                               capture_output=True, text=True)
            if r.returncode != 0:
                fail("%s: the planted copy does not compile:\n%s" % (name, r.stderr))
                return None
            objs.append(str(d / (c + ".o")))
        r = subprocess.run(cxx + ["-o", str(d / "testDecimal"), test_obj] + objs + others + ldflags,
                           capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the planted test does not link:\n%s%s" % (name, r.stdout, r.stderr))
            return None
        r = subprocess.run(cc + probe_cflags + ["tools/corpus-hash.c"] + objs + others + ["-o", str(d / "corpus-hash"), "-lm"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the planted probe does not build:\n%s" % (name, r.stderr))
            return None
        return d

    def run(d):
        r = subprocess.run([str(d / "testDecimal"), "--gtest_brief=1"], capture_output=True, text=True, env=run_env())
        failed = sorted(set(re.findall(r"\[\s*FAILED\s*\]\s+(\w+\.\w+)", r.stdout)))
        h = subprocess.run(["tools/check-corpus-hash.sh", str(d / "corpus-hash"), str(CORPUS), str(CORPUS / "trig.hash")],
                           capture_output=True, text=True, env=run_env())
        return r.returncode, failed, h.returncode, r.stdout

    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    print("check-planted-decimal")
    d = stage("control", None)
    if d is not None:
        rc, failed, hrc, out = run(d)
        if rc != 0 or hrc != 0:
            fail("control: the unplanted copy fails (%s, hash gate %d):\n%s" % (failed, hrc, out[-1500:]))
        else:
            print("  ok   %-66s passes" % "control")
    for name, fname, old, new, wanted, want_hash in PLANTS:
        d = stage(name, (fname, old, new))
        if d is None:
            continue
        rc, failed, hrc, out = run(d)
        if rc == 0:
            fail("%s: testDecimal passed with the defect planted" % name)
            continue
        if rc < 0 or rc >= 128:
            # Killed by a signal (a division by a zero limb): seen, though no
            # test could report it by name.
            print("  ok   %-66s caught: testDecimal died of signal %d" % (name, -rc if rc < 0 else rc - 128))
            continue
        if not any(w in failed for w in wanted):
            fail("%s: testDecimal failed (%s) but not %s" % (name, ", ".join(failed), " or ".join(wanted)))
            continue
        if want_hash and hrc == 0:
            fail("%s: the corpus hash gate passed although the corpus test failed" % name)
            continue
        print("  ok   %-66s caught by %s%s" % (name, ", ".join(failed), " and the corpus hash" if want_hash else ""))
    if failures:
        sys.stderr.write("check-planted-decimal: %d of %d plants not seen\n" % (len(failures), len(PLANTS) + 1))
        return 1
    print("check-planted-decimal: all %d plants seen, control passes" % len(PLANTS))
    return 0


sys.exit(main())
