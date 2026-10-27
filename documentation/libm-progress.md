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

## Upcoming project-used gaps

1. Binary exponential support (`exp2`).
2. Cube root (`cbrt`).
3. Float rounding, square root and trig operations used by WebAssembly, model,
   and CJelly. Simple wrappers require proof that narrowing remains exact or
   correctly rounded; float elementary accuracy is a separate target.
4. Broader real-function coverage: inverse trig, hyperbolic functions,
   cancellation-safe `log1p`/`expm1`, remainder families, adjacent values and
   integer conversions, followed by special functions as justified.

## Notes for the next numerical phase

Base logarithms now retain the precision reserve in `log_dd` with generated
split reciprocals. Their ordinary scalar-call paths remain slower than host
libm; direct base-specific tables remain a later optimization opportunity.

For exp2, a dedicated reduction by exact multiples of 1/128 can reuse the
existing exponential table and reconstruction polynomial. Converting only the
small residual with split ln(2) avoids introducing large-argument error through
`exp(x * rounded_ln2)`. Exact powers of two and the -1075/-1074/-1022/1024
boundaries need explicit handling and exception tests. Float log2 verification
must use binary32 rounding and ulp spacing, not a binary64 corpus tolerance.

## Verification and remaining limits

The new exact APIs have independent committed reference corpora, fresh samples,
raw-bit NaN/zero/infinity tests, all four rounding modes, errno/exception-state
checks, mutation checks and supplemental result hashes. Existing hashes remain
unchanged. Build/test validation and independent reviews accompany each commit.

The suite's cross-target scripts compare the legacy aggregate and do not yet
enforce these supplemental entries. Cross-target validation of the new APIs
remains pending; host verification must not be represented as cross-platform
execution evidence. Integrating that gate requires permission to edit suite.

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
