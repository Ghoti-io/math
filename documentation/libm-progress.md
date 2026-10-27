# Libm gap closure

Implementation stays within math while independent work proceeds in the other
libraries. New APIs prepare later migrations; no consumer is migrated here.
The deterministic contracts in the public headers remain authoritative.

## Completed capabilities

- Exact binary64/binary32 remainder: `gmath_fmod` and `gmath_fmodf`, added in
  commit `39424c29c1caacca54d44122ee69069ae2004dfc`.
- Exact binary64/binary32 extrema: `gmath_fmin`, `gmath_fmax`, `gmath_fminf`
  and `gmath_fmaxf`. Numeric results preserve input bits; minimum orders -0
  below +0. One quiet NaN yields the other number; signaling NaNs yield the
  canonical NaN and raise invalid.
- Base logarithms: `gmath_log2`, `gmath_log10`, `gmath_log2f`, with independent
  MPFR/mpmath reference values, exact binary-power cases and a dedicated float
  table/series path. The public numerical contract is one ulp, with nearest
  rounding assumed and canonical special-value handling.
- Binary exponential: `gmath_exp2`, with exact integer powers including
  subnormals, direct base-two table reduction, a one-ulp numerical target,
  and explicit finite overflow/inexact-underflow behavior. GCC and Clang each
  pass all 108 unit tests; full GCC gates, pinned regeneration/fresh oracles,
  ASan/UBSan and independent review pass. A 111,631-input sample measures
  maximum error 0.505040 ulp normal and 0.749648 ulp subnormal. Common small
  inputs remain slower than host libm; wide ranges and exact integer powers
  are faster on the measured host (see design notes).

- Real cube root: `gmath_cbrt`, with integer normalization, generated midpoint
  seeds and a compensated Newton correction. GCC14.2, GCC16.2 and Clang each
  pass 118 unit tests; full GCC14/GCC16 gates pass (nested optional oracles
  skipped in the build image, executed on the host). Ten cube-root tests,
  ASan/UBSan, 21 arithmetic/table/state plants and independent review pass.
  A 116,075-input independently certified reference sample measures at most
  0.49999902 ulp. Ordinary calls are approximately tied with host libm, wide
  exponents slightly slower, subnormal arguments about twice as fast and exact
  binary cube powers about five times as fast on the measured host.

- Binary32 basic operations: `gmath_sqrtf`, `gmath_floorf`, `gmath_ceilf`,
  `gmath_truncf`, `gmath_roundf`, `gmath_rintf`, `gmath_fabsf`,
  `gmath_copysignf`. Integer rounding/sign results are exact in every mode;
  sqrt is correctly rounded under nearest. Independent pinned references
  cover 66,200 committed and 840,560 larger-sample results. Raw special-value
  probes cover NaNs, sign-only operands and state preservation. GCC14.2,
  GCC16.2 and Clang pass all 125 unit tests; full GCC gates, seven-test
  ASan/UBSan and independent reviews pass. Some rounding
  paths remain slower than host libm; normal sqrt/sign paths are approximately
  tied, while the measured subnormal sqrt path is substantially faster.

## Upcoming project-used gaps

1. Remaining float trig and elementary operations used by WebAssembly, model
   and CJelly, including sin/cos/tan and float exp/log/hypot/atan2 families.
   Float elementary accuracy and exception handling remain separate targets.
2. Broader real-function coverage: inverse trig, hyperbolic functions,
   cancellation-safe `log1p`/`expm1`, remainder families, adjacent values and
   integer conversions, followed by special functions as justified.

## Notes for the next numerical phase

Base logarithms now retain the precision reserve in `log_dd` with generated
split reciprocals. Their ordinary scalar-call paths remain slower than host
libm; direct base-specific tables remain a later optimization opportunity.

Exp2 now uses exact reduction by multiples of 1/128 and the existing table and
reconstruction polynomial, with explicit -1075/-1074/-1022/1024 boundary tests.
Future float elementary operations must use binary32 rounding and ulp spacing
in their reference data, not a binary64 corpus tolerance.

## Verification and remaining limits

The new exact APIs have independent committed reference corpora, fresh samples,
raw-bit NaN/zero/infinity tests, all four rounding modes, errno/exception-state
checks, mutation checks and supplemental result hashes. Existing hashes remain
unchanged. Build/test validation and independent reviews accompany each commit.

Math-only QEMU checks now match all 43 committed function hashes on i686,
AArch64, s390x, PowerPC64, PowerPC32 and SPARC64 Linux, with both default and
forced-portable square root. Raw binary32 special-value/exception probes also
pass on those emulated targets at both `-O0` and `-O2`. These are probe executions, not physical-host or full GoogleTest
results. Other targets and broader exception/state validation remain pending.

The suite's automatic cross-target scripts still compare only the legacy
aggregate. Integrating supplemental entries and raw probes into that pipeline
remains separate work while consumer/suite edits are deferred.

Scalar call benchmarks compare against host libm on identical input ranges.
Extrema are approximately tied on the measured host. Base logarithms have
mixed performance as described above. Remainder is faster in
some float/subnormal cases and slower in some double ranges; there is no claim
of an overall libm performance win. Compiler-inlined, shared-library, vector,
and application workloads still need separate measurements.

Standard C types and semantics also need an explicit compatibility boundary:
long double, complex arithmetic, full fenv/errno compatibility and FMA are not
covered by the current library. Existing `gmath_rint` deliberately uses ties to
even regardless of the host rounding mode.
