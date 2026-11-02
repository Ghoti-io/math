# Hyperbolic sine, cosine and tangent

`gmath_sinh`, `gmath_cosh`, `gmath_tanh`, `gmath_sinhf`, `gmath_coshf` and
`gmath_tanhf` form one Float/Double family. One new module retains compensated
high/low components through the exponential and hyperbolic calculations.
All previous runtime modules, helpers, tables and literal answers remain
unchanged. Consumers remain unchanged; this adds capability for later use.

## Contract

The numerical target is one result ULP under nearest rounding. General correct
rounding, directed numerical accuracy, long double and complete libm errno
semantics are outside this contract. Preserve errno, mode, incoming standard
flags and coherent nontrapping controls. Production never writes controls.

| Input | sinh | cosh | tanh | New flags |
| --- | --- | --- | --- | --- |
| Signed zero | Input bits | Exact +1 | Input bits | None |
| Quiet NaN | Canonical positive quiet NaN | Same | Same | None |
| Signaling NaN | Canonical positive quiet NaN | Same | Same | Invalid only |
| Signed infinity | Signed infinity | Positive infinity | Signed 1 | None |
| Other finite nonzero | Hyperbolic sine | Hyperbolic cosine | Hyperbolic tangent | Inexact; underflow only for subnormal sinh/tanh outputs |
| Finite sinh/cosh overflow | Signed infinity | Positive infinity | Signed 1 | Overflow/inexact for sinh/cosh, inexact for tanh |

Magnitudes below 2^-60 Double / 2^-26 Float return input bits for sinh/tanh,
and +1 for cosh, in every mode. Subnormal sinh/tanh inputs require underflow
and inexact; cosh requires inexact only. Tanh magnitudes >=20 Double / >=10
Float return signed 1 with inexact in every mode. Overflow also returns nearest
infinity in every mode. These are explicit deterministic special contracts;
ordinary numerical accuracy assumes nearest rounding. Raw dispatch precedes
widening or unsafe arithmetic.

## Independently derived calculation

For a=abs(x), use these identities with a compensated t=expm1(a):

```
sinh(a) = (t + t/(1+t))/2
cosh(a) = 1 + t*t/(2*(1+t))
tanh(a) = expm1(2*a)/(expm1(2*a)+2)
```

The first two serve the local a<=1/2 region. For 1/2<a<40, compute E=exp(a)
and its compensated reciprocal, then (E-1/E)/2 or (E+1/E)/2. For a>=40,
compute exp(a)/2 directly. Omitting the reciprocal costs relative error below
2^-79 using e>2, less than 2^-26 binary64 result ULP. This avoids introducing
tiny reciprocal underflow while returning a normal large value.

The exponential reduces a=n*ln2+r with compensated arithmetic, |r|<0.347,
then uses 25 Taylor terms. The exact rational coefficient generator reuses
our existing exponential/ln2 derivation: exponential relative tail below
2^-124, ln2 omitted tail below 2^-405. Its check mode verifies these bounds,
the complete emitted table and rational tanh saturation inequalities using
e>8/3. These analytic estimates are distinct from all C rounding errors;
focused measurements support the one-ULP target without a global proof.

For large sinh/cosh, scaling uses n-1. Near their overflow boundary n may be
1025, so scale exponent 1024 in two steps, 2^1023 then 2. Reconstructed huge
operands never enter Dekker splitting. The reciprocal and tanh divisions stay
below exp(40), with normal bounded split operands. Float retains the Double
calculation until one final narrowing; rare double-rounding remains possible.

Directed MPFR independently brackets the first overflowing positive inputs:
Double 0x408633ce8fb9f87e and Float 0x42b2d4fd, for both sinh and cosh.
Their immediate predecessors are independently certified <=MAX, protecting
the nonnearest flag checks against incidental intermediate overflow.

## References and focused verification

The literal `hyperbolic.corpus` stores width, raw input and three nearest
targets with flags and outward real-error intervals. `hyperbolic.sha256` pins
complete LF bytes; Git attributes preserve them with core.autocrlf=true.
The population includes both signs, raw and bounded seeded inputs, every single
NaN payload bit, zero/subnormal/normal transitions, local/tiny/large guards,
ln2 reduction boundaries and overflow neighbors. Sixteen global midpoint-focused positive inputs plus four in each of four
implementation regions per function/format are selected from an independent pinned
base search; duplicate magnitudes merge, and both signs and immediate neighbors
are retained. The selector ranks conservative closed-interval distances to
rounding midpoints using the actual spacing on either side of a binade.
This selects within that finite search, without a global closest-case claim.
Separate strata cover the
actual cosh-to-1 transitions near 2^-26 Double / sqrt(2)*2^-12 Float and
tanh-to-1 transitions near 27.5*ln2 Double / 13*ln2 Float.

The generator reads no candidate implementation or coefficient table. Directed
MPFR at 1200/2400 bits and independent higher-precision mpmath must agree on
nearest targets. Residuals are outward integer multiples of 2^-30 target ULP.
For huge tanh arguments, e>2 gives an analytic residual enclosure, avoiding
enormous exponent work. The numerical checker handles the half-spacing side
of normal binade boundaries and records each sampled maximum's input, target,
observed result and residual interval. Exact hexadecimal bounds are independent
of decimal-format rounding; diagnostics retain failure stage, incoming subset,
expected/observed flags, errno, mode and controls.

Run the native container-free family gate:

```sh
make check-hyperbolic
```

It checks complete SHA/population identity, exact coefficients, six public APIs,
nearest numerical cells, selected every-mode/every-incoming-flag state, errno,
controls, special values, symmetry, monotonicity and bounds across the complete
sorted corpus, including the large branch and overflow boundary. Ordinary
nonnearest results must retain finite/sign/range sanity without a directed ULP
promise. It also requires
actual malformed/reference/source defects to fail at the intended assertions;
crashes and compilation/infrastructure failures do not count as detections.
Numerical, state, reference, loader and sanity failure stages are distinguished.
Format-local state guards and individual public-result faults complement shared
arithmetic defects. Inherited GoogleTest filters/sharding are neutralized, and
the gate requires all five named family tests; only an unsupported alternate
control fixture may explicitly skip.
Both SSE flush-to-zero settings and supported denormals-are-zero combinations
are exercised, including exact adjacent-word checker controls. Integer ULP
distances avoid arithmetic on subnormal divisors in those settings. An object
check rejects
a compiled write-and-restore of the rounding mode. Temporary defect objects and
binaries are reclaimed while diagnostic logs remain. The raw `testHyperbolic`
row probe checks its loaded rows; complete population/SHA belongs to the family
gate or the explicit fresh wrapper below.

Reproduce complete bytes with the pinned instrument image:

```sh
make check-hyperbolic-oracle
```

This opt-in target fails when its instrument is unavailable and compares both
complete files without updating committed answers. Generate and verify a larger
independent seed through the public interfaces:

```sh
python3 tools/oracle/oracle.py hyperbolic --out build/hyperbolic-fresh --seed 20261106 --count 4096
make build/linux/release/apps/testHyperbolic
python3 tools/check-hyperbolic.py --fresh --seed 20261106 --count 4096 --test build/linux/release/apps/testHyperbolic --directory build/hyperbolic-fresh --work build/hyperbolic-fresh-check
```

The fresh wrapper requires the requested seed/count population, SHA, actual
loaded path and row count. Truncated fake fresh samples and executables that
ignore the requested directory are rejected. Ordinary target corruptions for
all six APIs calibrate the numerical checker.

`make prepare-corpora` remains the stable standalone/cross preparation name;
this literal family requires no reconstruction. The standalone hash client
retains its existing header-copy interface and adds no fenv/libm dependency.
All 95 previous function hashes and the legacy aggregate remain unchanged;
six new supplemental hashes bring the total to101.

Sampled bounds are measurements, not global maxima. Broader physical/cross-target,
Windows/LLP64, exhaustive input/environment and application coverage are unrun.
There is no new benchmark or Valgrind campaign; earlier failed partial Valgrind
scopes remain failed.

Reproduce the pinned base search and midpoint selection:

```sh
python3 tools/oracle/oracle.py hyperbolic --out build/hyperbolic-search --seed 20261106 --count 4096 --midpoint-search
python3 tools/select-hyperbolic-midpoints.py --directory build/hyperbolic-search --check --report build/hyperbolic-midpoint-report.json
```

The base search excludes the selected additions, so selection has no circular
population dependency. Complete base bytes, metadata, population and digest
must match the independently recorded source SHA before selection.

The final default population has 11,352 rows; the independent larger seed has
39,944. All five focused tests pass with GCC16, Clang and ASan/UBSan on both
populations, including both FTZ settings and supported DAZ combinations. The
GCC16 gate detects all 36 numerical/state source faults at their intended
assertion stage, plus the compiled restored-control fixture. All 95 previous
hashes and the legacy aggregate remain unchanged.

Default closed sampled bounds in exact hexadecimal form are:

| Function | Bound |
| --- | --- |
| sinh | `0x1.ffed9c8p-2` |
| cosh | `0x1.00000008p-1` |
| tanh | `0x1p-1` |
| sinhf | `0x1.fef216dp-2` |
| coshf | `0x1.ffffff3p-2` |
| tanhf | `0x1.ffffe23p-2` |

These witnesses are sampled bounds. A cosh input at 2^-26 returns the lower
neighbor of its nearest target while staying within the one-ULP contract;
correct rounding is not claimed.

One completed-family default GCC16 suite passes from a clean cold checkout:
106 gates, 39 main binaries, 269 tests: 268 pass and one expected native32-long
skip on LP64. All five hyperbolic tests pass. The full unmodified command exits
zero; tracked bytes/tree stay unchanged before/after the test and after verified
archive/cleanup. Only verification-summary Markdown changes follow that run.
Existing optional nested-oracle/x87-32 branches explicitly skip when their
instruments or runtime are unavailable. New-family required named MPFR/mpmath
regeneration and larger-reference checks pass separately; skips are not relabeled
as instrument passes.
