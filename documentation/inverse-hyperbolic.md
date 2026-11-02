# Inverse hyperbolic functions

`gmath_asinh`, `gmath_acosh`, `gmath_atanh` and their `f` forms are one
Float/Double family. A private module shares compensated logarithms and a
square-root residual correction. Earlier runtime modules, helpers, tables and
literal answers remain unchanged. Consumers remain unchanged.

## Contract

The numerical target is one result ULP under nearest rounding. General correct
rounding, directed numerical accuracy, long double and complete libm errno
semantics are outside this contract. Preserve errno, rounding mode, incoming
standard flags and coherent nontrapping controls. Production never writes
controls.

| Input | asinh | acosh | atanh |
| --- | --- | --- | --- |
| Signed zero | Input bits, no new flags | Quiet NaN, invalid | Input bits, no new flags |
| Quiet NaN | Canonical positive quiet NaN, no new flags | Same | Same |
| Signaling NaN | Canonical positive quiet NaN, invalid only | Same | Same |
| Positive infinity | Exact positive infinity | Exact positive infinity | Quiet NaN, invalid |
| Negative infinity | Exact negative infinity | Quiet NaN, invalid | Quiet NaN, invalid |
| +1 | Inexact finite value | Exact +0 | Positive infinity, divide-by-zero only |
| -1 | Inexact finite value | Quiet NaN, invalid | Negative infinity, divide-by-zero only |
| Other finite input outside domain | No such input | x<1: quiet NaN, invalid | abs(x)>1: quiet NaN, invalid |

Other finite valid nonzero results require inexact, with underflow only for
subnormal asinh/atanh results. Valid finite inputs never overflow. Magnitudes
below 2^-60 Double / 2^-26 Float return asinh/atanh input bits in every mode;
subnormal inputs add underflow/inexact, other nonzero inputs add inexact only.
These deterministic tiny/special contracts precede widening or unsafe
arithmetic. Ordinary numerical accuracy assumes nearest rounding.

## Independent derivation

For a=abs(x), use compensated versions of these identities:

```
asinh(a) = log1p(a + a*a/(1+sqrt(1+a*a)))    for a<=1
asinh(a) = log(a+sqrt(1+a*a))               for larger a
acosh(a) = log1p(t+sqrt(t*(t+2))), t=a-1
atanh(a) = log1p(2*a/(1-a))/2
```

TwoSum retains the acosh subtraction and atanh denominator. The square-root
starts with our existing sqrt of the high component, then corrects its
compensated squared residual divided by twice the root. Log1p uses
2*atanh(u/(2+u)) locally through u=1/2; general logarithms normalize the high
component into [1,2), then add the low/high first-order correction and a
compensated exponent times ln2. Forty odd-series terms and rationally generated
ln2 parts reuse our own log1p/expm1 coefficient derivation. Exact rational
checks bound the omitted series tail below 2^-132 and ln2 tail below 2^-405.
These are analytic truncation estimates, separate from C rounding errors.

At a>=2^60, asinh/acosh use log(a)+ln2. The omitted absolute correction has
magnitude below 1/(2*a*a), hence below 2^-121 at that guard. No square, double
of a huge argument or tiny reciprocal is formed. Below the guard all product
and split operands are bounded safely below overflow. Float retains Double
compensated intermediates and narrows once. Measurements support the one-ULP
target without a global rounding proof.

## References and gates

The LF/SHA-pinned literal `inverse-hyperbolic.corpus` stores raw inputs and
three nearest targets with flags and outward integer residual intervals in
units of 2^-30 target ULP. Directed MPFR at 1200/2400 bits and independent
higher-precision mpmath must agree. The generator reads no implementation or
coefficient table. Raw NaN/domain/pole contracts are explicit.

The population includes both signs, seeded raw and bounded samples, every
single NaN payload bit, zero/subnormal/normal boundaries, tiny and huge guards,
near-one acosh and atanh pole neighbors. Rational log-switch strata include
5/12, 13/12 and 1/5; inverse images of logarithm-argument powers cover internal
normalization seams. Sixteen global midpoint cases plus four from each of four implementation
regions per function/format, and their immediate neighbors, supplement the
population. The selector ranks conservative distances
of complete closed intervals to actual binade midpoints; it makes no global
closest-case claim.

```sh
make check-inverse-hyperbolic
make check-inverse-hyperbolic-oracle
```

The native family gate checks an independent canonical payload SHA as well as
the adjacent digest, complete population and exact coefficient identity,
all six public APIs, nearest numerical cells, selected every-mode and all
incoming-flag subsets, errno, controls, exact special values, symmetry,
monotonicity and bounds. Ordinary nonnearest results require finite/sign/domain
sanity, without a directed ULP promise. Both FTZ settings and supported DAZ
combinations run, including integer-only adjacent-word checker calibrations.
An object check rejects an actual compiled write-and-restore of rounding mode.
Two compiled low-part controls and uncompensated faults independently verify
the actual acosh subtraction and atanh denominator reductions. Losing their
low components may remain within the public one-ULP allowance; these are
representation checks, separate from numerical defect detection.
Malformed references, ordinary target errors, format-local source faults and
shared arithmetic defects must fail at intended assertion stages; compilation
failures and crashes do not count. Filtering/sharding cannot omit required
family tests. Temporary defect objects are reclaimed, retaining diagnostic logs.

Generate and verify an independent larger sample through public interfaces:

```sh
python3 tools/oracle/oracle.py inverse_hyperbolic --out build/inverse-hyperbolic-fresh --seed 20261108 --count 4096
make build/linux/release/apps/testInverse_hyperbolic
python3 tools/check-inverse-hyperbolic.py --fresh --seed 20261108 --count 4096 --test build/linux/release/apps/testInverse_hyperbolic --directory build/inverse-hyperbolic-fresh --work build/inverse-hyperbolic-fresh-check
```

The fresh wrapper authenticates requested seed/count, complete population/SHA,
actual loaded path and row count, and all five named tests. It rejects truncated
fake samples and executables that ignore the requested directory. Only the
unsupported alternate-control fixture may explicitly skip.

Reproduce the independently pinned base search and selected midpoint literals:

```sh
python3 tools/oracle/oracle.py inverse_hyperbolic --out build/inverse-hyperbolic-search --seed 20261108 --count 4096 --midpoint-search
python3 tools/select-inverse-hyperbolic-midpoints.py --directory build/inverse-hyperbolic-search --check --report build/inverse-hyperbolic-midpoint-report.json
```

The required opt-in oracle gate also regenerates this pinned base search and
checks the selected literals automatically. The base excludes the selected
additions, avoiding circular population selection.
`make prepare-corpora` remains the stable standalone/cross preparation target;
this literal family needs no reconstruction. The standalone hash client retains
its header-copy interface and adds no fenv/libm dependency. Preserve all 101
previous function hashes and the legacy aggregate; six supplemental hashes
bring the total to 107.

Broader physical/cross-target, Windows/LLP64, exhaustive input/environment and
application coverage are unrun. No new benchmark or Valgrind campaign is
claimed; earlier failed partial Valgrind scopes remain failed.

Default closed sampled bounds are recorded below. Each includes the entire
outward residual interval; these measurements are not global maxima or a
correct-rounding proof.

| Function | Raw input witness | Closed bound in result ULP |
| --- | --- | --- |
| asinh | `3fe7414f849f555c` | `0x1.fffc7f5p-2` |
| acosh | `76b7ee643283d158` | `0x1.ffdb19p-2` |
| atanh | `3fee72e80af35ede` | `0x1.ffe9466p-2` |
| asinhf | `000000003f5fb2a6` | `0x1.fff9ba4p-2` |
| acoshf | `000000003f800024` | `0x1.fffedc7p-2` |
| atanhf | `000000003ebd2524` | `0x1.ffe8dcbp-2` |

The completed focused checks use GCC 16.2.0 and Clang 19.1.7. All five family
tests pass on the 15,052-row default population and 57,878-row independent larger
seed with both compilers and with ASan/UBSan. The GCC gate detects all 40
numerical/state source faults at their intended assertion stages, both isolated
compensated low-part faults, the restored-control-write fixture and the
loader/reference/population/path/integrity controls. All 101 earlier hashes and
the legacy aggregate remain unchanged; six supplemental sets are pinned.
Complete failure diagnostics retain the raw input/target/result, error interval,
assertion stage, incoming flag subset, expected/observed flags, errno, mode and
controls. Exact hexadecimal bounds avoid decimal-format rounding ambiguity.

The required public oracle target exits zero with MPFR 4.2.2, gmpy2 2.3.2,
mpmath 1.4.1 and Python 3.14.7: both complete default files match, both MPFR
precisions certify identical target/flag/closed-cell tuples, and the pinned
57,496-row base search reproduces the selected midpoint literals. Instrument
unavailability fails this opt-in target; it is not relabeled as a pass.

One completed-family default GCC16 suite passes from an isolated clean cold
checkout: 107 gates, 40 main binaries, 274 tests: 273 pass and one expected
native32-long skip on LP64. All five inverse hyperbolic tests pass. The full
unmodified command exits zero; tracked bytes/tree remain unchanged before and
after testing and after verified archive/cleanup. Only verification-summary
Markdown changes follow that run. Existing optional nested-oracle/x87-32
branches explicitly skip when their instruments or runtime are unavailable;
required new-family oracle and larger-reference checks pass separately.
Diagnostic records are archived and CRC/inventory verified before temporary
build trees are reclaimed. Skips are not relabeled as instrument passes.
