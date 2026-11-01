# Cancellation-safe logarithm and exponential

`gmath_log1p`, `gmath_log1pf`, `gmath_expm1` and `gmath_expm1f` are one family.
They evaluate log(1+x) and exp(x)-1 while retaining small corrections near zero.
No old runtime module, helper or table changes. Consumers remain unchanged;
this adds capability without claiming current production use or libm parity.

## Contract

The numerical target is one result ULP under nearest rounding. General correct
rounding, directed numerical accuracy, full libm errno semantics and long-double
behavior are outside this contract. Preserve errno, mode, incoming standard
flags and coherent nontrapping controls; never write rounding controls.

| Inputs | log1p | expm1 | New flags |
| --- | --- | --- | --- |
| Signed zero | Input bits | Input bits | None |
| Quiet NaN | Canonical positive quiet NaN | Same | None |
| Signaling NaN | Canonical positive quiet NaN | Same | Invalid only |
| +Infinity | +Infinity | +Infinity | None |
| -Infinity | Canonical NaN | -1 | Invalid for log1p; none for expm1 |
| -1 | -Infinity | Ordinary finite result | Divide-by-zero only for log1p; inexact for expm1 |
| Finite x below -1 | Canonical NaN | Valid finite result | Invalid for log1p; inexact for expm1 |
| Other valid finite nonzero | Principal real logarithm | Exponential minus one | Inexact; underflow only for subnormal rounded outputs |
| Finite positive expm1 overflow | Valid logarithm | +Infinity | Overflow and inexact for expm1 |

Magnitudes below 2^-60 (Double) or 2^-26 (Float) return input bits in every
standard mode, with inexact and underflow exactly for subnormal outputs.
Finite expm1 inputs <=-40 (Double) / <=-20 (Float) return nearest -1, with
inexact and no underflow. Overflow returns nearest +Infinity in every mode.
These guards are deterministic special contracts, not general directed libm
rounding. Raw dispatch precedes widening or unsafe arithmetic.

## Independently derived calculation

For local logarithms, use the identity

```
z = x/(2+x)
log(1+x) = 2*z*(1 + z*z/3 + z^4/5 + ...)
```

For |x|<=1/2, |z|<=1/3. Keep the denominator's addition and the quotient
residual in double-double arithmetic. Forty odd terms leave a relative tail
below 2^-132. For other valid inputs, TwoSum retains exact 1+x; normalize the
high component into [1,2), evaluate the same odd series, and add the exponent
times a split ln2. The low component contributes `sum.lo/sum.hi`; the omitted
quadratic correction is far below an output ULP outside the local region.

For x>=2^60, normalize x directly and omit the unit correction, whose absolute
contribution is below 2^-60, at most 2^-13 output ULP. This avoids overflow in
1+DBL_MAX under upward rounding and avoids a subnormal reciprocal correction
that could spuriously raise underflow while returning a normal logarithm.

For the exponential, reduce `x=n*ln2+r` in double-double arithmetic. Integer
selection keeps |r| below 0.347, including a generous rounding allowance. A
25-term Taylor series evaluates expm1(r); its conservative relative remainder
is below 2^-124. Return that series directly for n=0. Otherwise reconstruct
`2^n*(1+expm1(r))-1` with compensated addition. Powers of two scale the
components exactly in their bounded normal ranges. The n=1024 case scales
in two steps; huge reconstructed operands never enter Dekker splitting.

`gen-log1p-expm1-coefficients.py` derives rational Taylor coefficients and a
bounded rational atanh(1/3) sum for ln2. Its check mode verifies the three analytic
tail inequalities and complete coefficient text. These tail bounds are distinct
from the rounding errors of all C operations. Independent measurements support
the one-ULP contract; no mechanically established all-input rounding bound or
exhaustive correct-rounding proof is claimed. Float evaluates the same bounded
Double calculation and narrows once; rare double-rounding remains possible.

## Independent references and focused checks

The compact `log1p-expm1.corpus` stores raw inputs, both nearest targets, flags
and outward real-error intervals. `log1p-expm1.sha256` pins complete LF bytes;
Git attributes preserve them even with core.autocrlf=true. Literal seeded
answers remain committed. No large deterministic caches or raw benchmark JSON
files are added. `make prepare-corpora` remains the stable standalone/cross
preparation entry point; this literal payload needs no reconstruction step.

The generator reads no candidate implementation or table. Directed MPFR at
1200 bits, escalating to 2400 if necessary, encloses each result; mpmath at
higher precision independently agrees. Exact rational packing requires identical
nearest targets. Adjacent Double inputs 0x40862e42fefa39ef/39f0 and Float inputs
0x42b17217/18 independently bracket the nearest expm1 overflow boundary.
For x<=-1280, e>2 gives an analytic saturation residual below 2^-30 of either
output spacing, avoiding enormous exponent work in the instruments.

The population includes both signs, subnormal/normal boundaries, tiny paths,
log domain/pole and local/general seams, huge-log and exp saturation/overflow
cutoffs, ln2 reduction seams, near-zero quadratic midpoints and literal near-
midpoint cases selected from independent larger-reference outputs. Seed20261103
uses 512 iterations per format with both raw and bounded draws; all resulting
answers are retained. Real-error cells use outward integer multiples of 2^-30 ULP.
The checker handles the half-spacing side of normal binade boundaries.

Run the focused native, container-free family gate:

```sh
make check-log1p-expm1
```

It checks SHA/population identity, coefficient/tail regeneration, all four public
APIs, ordinary numerical targets, selected every-mode/every-incoming-flag state,
errno and control preservation, analytic special cases, monotonicity and convexity,
and actual malformed/reference/source defects. Crashes and infrastructure failures
are not counted as intended assertion detections. Temporary defect binaries and
objects are reclaimed; diagnostic logs remain. The main unit is `testLog1p_expm1`. Its raw row probe is not a complete
population verifier; use the family gate or the explicit fresh wrapper below.
Native SSE checks also exercise flush-to-zero control preservation. A scoped
object check rejects control-writing operations, including a compiled fixture
that writes and restores the mode before returning.
All 91 old result hashes and the legacy aggregate remain unchanged; four new
supplemental hashes bring the total to95. The standalone hash client adds no
fenv/libm runtime dependency.

Reproduce independent complete-byte regeneration with the pinned oracle image:

```sh
make check-log1p-expm1-oracle
```

This opt-in target fails when the instrument is unavailable, generates into the
build directory and compares both complete files. It does not update committed
answers. A separate larger sample can be generated and checked with:

```sh
python3 tools/oracle/oracle.py log1p_expm1 --out build/log1p-expm1-fresh --seed 20261104 --count 4096
make build/linux/release/apps/testLog1p_expm1
python3 tools/check-log1p-expm1.py --fresh --seed 20261104 --count 4096 --test build/linux/release/apps/testLog1p_expm1 --directory build/log1p-expm1-fresh --work build/log1p-expm1-fresh-check
```

The fresh wrapper requires the exact requested seed/count population, complete
SHA and actual loaded directory/row count. A two-zero-row substitute and an
executable that ignores the requested directory are rejected. Ordinary-result
corruptions in each precision calibrate the numerical error-cell checker.
Each sampled maximum prints its input, target, observed result and residual
interval, including the binade-spacing correction.

Reproduce the independently selected midpoint inputs:

```sh
python3 tools/oracle/oracle.py log1p_expm1 --out build/log1p-expm1-search --seed 20261104 --count 4096 --midpoint-search
python3 tools/select-log1p-expm1-midpoints.py --directory build/log1p-expm1-search --check --report build/log1p-expm1-midpoint-report.json
```

This base search excludes the later adversarial additions. The selector checks
its population/digest and ranks the sixteen greatest absolute target-relative
residual sums per function/format, then deduplicates magnitudes and retains both
signs. This is a selection heuristic; the optional report records each score
and closed distance to the relevant rounding midpoint. The final population also explicitly includes the actual transitions to
nearest -1 around -54*ln2 (Double) and -25*ln2 (Float), and all single payload-bit
quiet/signaling NaNs with both signs.

Numerical results are sampled measurements, not global maxima. Broader physical/
cross-target, Windows/LLP64, exhaustive input/environment and application coverage
are unrun. No new performance or Valgrind campaign is part of this family;
earlier failed partial Valgrind scopes remain failed.

The checked default population has 11,766 rows; the independent larger seed has
40,376. GCC16 and Clang pass all five focused tests, including the alternate SSE
control matrix, and the public wrapper validates the complete larger population.
Focused ASan/UBSan checks pass both populations. Sampled closed ULP bounds for
log1p, expm1, log1pf and expm1f respectively are 0.5, 0.50000000093132257,
0.4999999813735485 and 0.49999999068677425 on the default data with both compilers.
The expm1 witness at input 0x3cb0000000000000 differs from the nearest target
by one raw word while remaining inside the one-ULP contract; this is not a
correct-rounding claim.

The completed-family default GCC16 suite passes in one clean cold checkout:
105 gates, 38 main binaries, 264 tests: 263 pass and one expected native32-long
skip on LP64. The full command exits zero; tracked bytes/tree stay unchanged
before and after verified diagnostic archiving and temporary-build cleanup.
Existing optional nested-oracle branches explicitly skip without their pinned
image. The new family's required named oracle and larger-reference checks pass
separately; these skips are not relabeled as oracle passes.
