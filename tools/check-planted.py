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
applied (the replacement must match exactly once and must change the file), links the
copy with testTrig's object, and requires testTrig to fail on the oracle
corpus, naming Trig.CorpusIsWithinOneUlp.  The unplanted copy is the control:
it must pass, which is what makes a failure mean the defect and not the build.

Three families:

  oracle   a defect in the library that the accuracy check must catch:
           a coefficient perturbed, a reduction branch skipped or shortened,
           a quadrant or sign wrong, a fast path taken too far
  hash     a defect too small for the 1 ulp contract to see (a coefficient
           perturbed by one unit in its last place) that the committed corpus
           hash must still catch, because a different bit on one target is
           what the cross-target gate exists for
  corpus   a defect in the oracle's data, not the library: a wrong answer, a
           truncated file and a missing file, which testTrig must refuse
           (the oracle test fails, it does not skip)

Run by `make check-planted` from the library directory, with the build's
compile and link flags in the PLANT_* environment variables.
"""

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
test_obj = env["PLANT_TEST_OBJ"]
probe_cflags = shlex.split(env["PLANT_PROBE_CFLAGS"])
ld_path = env["PLANT_LD_PATH"]
SRC = Path("src/elementary")
CORPUS = Path("tests/corpus")
ORACLE_TEST = "Trig.CorpusIsWithinOneUlp"

failures = []


def fail(msg):
    failures.append(msg)
    print("check-planted: FAIL: %s" % msg, file=sys.stderr)


def variant(name, patches):
    """Copy the sources, apply (file, old, new) patches, build, return the directory."""
    d = work / name
    d.mkdir(parents=True)
    for f in ("trig.c", "trig_tables.h"):
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
    r = subprocess.run(cc + probe_cflags + list(extra) + ["tools/corpus-hash.c", str(d / "trig.o"), "-o", str(exe), "-lm"],
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
C = "trig.c"
expect_oracle_fails("coefficient/sin S0 off by 2^-32", [(T, "0x1.1111111111111p-7", "0x1.1111111211111p-7")])
expect_oracle_fails("coefficient/cos C0 off by 2^-36", [(T, "-0x1.6c16c16c16c15p-10", "-0x1.6c16c16d16c15p-10")])
expect_oracle_fails("coefficient/-1/6 up one ulp", [(T, "#define GMATH_M1_6_HI -0x1.5555555555555p-3", "#define GMATH_M1_6_HI -0x1.5555555555556p-3")])
expect_oracle_fails("reduction/skipped (sin, cos, tan)", [(C, "#define GMATH_PIO4 0x1.921fb54442d18p-1", "#define GMATH_PIO4 0x1p20")])
expect_oracle_fails("reduction/no reflection past 1/2", [(C, "if (f[7] & 0x80000000u) {", "if (0 && (f[7] & 0x80000000u)) {")])
expect_oracle_fails("reduction/window of 160 bits not 256", [(C, "a[i] = gmath_two_over_pi[j0 + 2 + 7 - i]; /* least significant first */", "a[i] = i < 3 ? 0u : gmath_two_over_pi[j0 + 2 + 7 - i];")])
expect_oracle_fails("reduction/pi/2 low word dropped", [(C, "hi * GMATH_PIO2_LO + lo * GMATH_PIO2_HI", "lo * GMATH_PIO2_HI")])
expect_oracle_fails("reduction/remainder tail dropped", [(C, "s.lo + (u.lo + (tail + rl))", "s.lo + (u.lo + tail)")])
expect_oracle_fails("quadrant/cos sign", [(C, "((n + 1) & 2) ? SIGN_BIT : 0", "(n & 2) ? SIGN_BIT : 0")])
expect_oracle_fails("quadrant/sin sign", [(C, "(n & 2) ? sign ^ SIGN_BIT : sign", "sign")])
expect_oracle_fails("quadrant/tan sign", [(C, "(n & 1) ? sign ^ SIGN_BIT : sign", "sign")])
expect_oracle_fails("fast path/sin returns x up to 2^-20", [(C, "if (ax < 0x1p-28) {\n    return x;\n  }\n  double rh = ax;\n  double rl = 0.0;\n  int n = 0;\n  if (ax > GMATH_PIO4) {\n    n = reduce_any(ax, &rh, &rl);\n  }\n  gmath_dd r = (n & 1) ? kernel_cos(rh, rl) : kernel_sin(rh, rl);", "if (ax < 0x1p-20) {\n    return x;\n  }\n  double rh = ax;\n  double rl = 0.0;\n  int n = 0;\n  if (ax > GMATH_PIO4) {\n    n = reduce_any(ax, &rh, &rl);\n  }\n  gmath_dd r = (n & 1) ? kernel_cos(rh, rl) : kernel_sin(rh, rl);")])

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

# Hash-class defects: below the contract, above the committed bits.
expect_hash_fails("coefficient/sin S0 up one ulp", [(T, "0x1.1111111111111p-7", "0x1.1111111111112p-7")])
expect_hash_fails("coefficient/cos 1/24 up one ulp", [(T, "#define GMATH_1_24_HI 0x1.5555555555555p-5", "#define GMATH_1_24_HI 0x1.5555555555556p-5")])

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
    real_count = re.search(r"count (\d+)", (CORPUS / "trig.hash").read_text()).group(1)
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
