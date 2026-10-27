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

- Exact native integer rounding: `gmath_lround`, `gmath_lroundf`,
  `gmath_llround` and `gmath_llroundf`. Ties go away from zero in every mode;
  valid calls add no flags, while NaNs/infinities/out-of-range rounded results
  return the destination minimum with invalid only. Native long may be
  signed32 or signed64; long long is signed64. Caller errno/mode/incoming
  flags are preserved. Consumers remain unmigrated. Validation and timing
  evidence follows.

- Binary32 unary arctangent: `gmath_atanf`, reusing the verified Float atan2
  kernel with exact abscissa one. One Float ULP under nearest rounding;
  exact tiny input bits in every mode, canonical raw NaNs, signed zeros and
  infinity constants, explicit IX/UF and preserved caller state. A dedicated
  13,114-row independent reference corpus covers unary midpoint/seam cases.
  Consumers remain unmigrated. Full validation and performance limits follow.

- Binary32 two-argument arctangent: `gmath_atan2f`, with a short Float-specific
  series/table kernel, signed-zero/quadrant constants and explicit raw NaN
  handling. The numerical target is one Float ULP under nearest rounding;
  tiny positive-x ratios have true nearest bits in every mode, including
  corrected quotient midpoints and after-round UF. All nonzero mathematical
  angles require IX. Independent committed/larger references cover
  35,309/229,222 pairs with conservative sampled bound 0.50000003 ULP;
  the mathematical bound is 0.501457908 ULP. General correct rounding is not
  claimed. Table/direct timing samples beat host libm, while common/wide
  ranges remain slower; no overall speed win is claimed.

- Binary32 hypotenuse: `gmath_hypotf`, correctly rounded nearest/ties-even in
  every mode with exact-result/no-new-flags behavior. Signaling NaNs have
  explicit priority; finite inexact results use tininess after rounding and
  deterministic overflow flags. Exact 96-bit integer rounding backs a guarded
  native approximation. Committed/larger independent samples have
  35,910/229,568 rows; strict midpoint-square certificates enforce target bits,
  with closed error-cell upper bound 0.50000003 ULP at an exact finite tie.
  Native admission improves the common sample about 2.1 times versus the
  integer baseline, but ordinary calls remain about three times host libm.
  No overall performance win is claimed.

- Binary32 base-ten logarithm: `gmath_log10f`, reusing the unchanged natural
  float kernel with one double base conversion. Exact representable decimal
  powers 10^0 through 10^10 return integers without new flags in every mode;
  all other positive finite inputs require inexact and give normal outputs.
  The float nearest 10^11 remains inexact despite rounding to integer 11.
  Committed/larger directed populations contain 19,888/310,331 rows, with
  conservative measured maxima 0.49999504/0.49999852 ULP. Independent bound
  below 0.500168 ULP leaves reserve under the one-ULP contract. Ordinary
  timing remains about 1.10–1.27 times host libm; near-one inputs are faster,
  subnormal arguments near parity and exact-power timing varies. No overall
  performance win is claimed.

- Binary32 natural logarithm: `gmath_logf`, with exact float reduction and a
  dedicated five-term series using the existing logarithm table. One returns
  positive zero without flags; all other positive finite arguments require
  inexact and produce normal outputs. Raw NaN/domain/zero handling and state
  preservation have explicit tests. Committed/larger directed samples contain
  19,120/309,591 rows; conservative maximum error is 0.49999999 ULP, below the
  0.51 cap. A separate derivation bounds nearest error below 0.500168 ULP.
  Ordinary scalar calls remain about 1.76 times slower than host libm; measured
  subnormal and binary-power arguments are faster. No overall win is claimed.

- Binary32 natural exponential: `gmath_expf`, reusing the existing natural
  reduction/table/polynomial with independently certified float cutoffs.
  Only zeros are exact finite cases; every other finite nonzero input has
  explicit inexact/underflow/overflow policy. Directed pinned references cover
  27,228 committed and 317,759 larger-sample rows, with conservative closed
  error-cell maximum 0.50000003 ULP. Full GCC14/GCC16 gates, 157 unit tests on
  GCC14/GCC16/Clang, nine focused ASan/UBSan tests, independent reviews and
  six-target probes pass. Normal ranges remain about twice as slow as host
  libm, subnormal timing is near parity and tiny inputs are faster in the
  measured paired sample. No overall speed win is claimed.

- Binary32 base-two exponential: `gmath_exp2f`, reusing exact base-two
  reduction and the existing generated exponential table. Integer powers
  -149 through 127 are exact without exceptions; NaNs, finite tails and
  inexact tiny outputs have explicit float/state contracts. Directed pinned
  references cover 26,220 committed and 316,779 larger-sample rows. A complete
  reference-payload checksum also runs without the oracle image. The closed
  error-cell upper bound is 0.50000003 ULP against a 0.51 regression cap.
  Full GCC14/GCC16 gates, 148 unit tests on GCC14/GCC16/Clang, nine focused
  ASan/UBSan tests, independent reviews and six-target probes pass. Normal
  ranges remain about twice as slow as host libm; subnormal-result timing is
  near parity and tiny inputs are faster in the measured paired sample.

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

- Binary32 trigonometry: `gmath_sinf`, `gmath_cosf`, `gmath_tanf`, with
  bounded Taylor paths for |x|<=1, a private 80-fraction-bit wide reducer at
  |x|>=2^30 and the existing double fallback for uncertain cases. Directed
  MPFR/mpmath certification covers 62,574 committed and 934,914 larger-sample
  results; maximum errors remain about 0.502127/0.500046/0.501626 ulp.
  A broad-admission prototype exhaustively preserved the old results for all
  2,147,483,646 signed finite float inputs above magnitude 1; the final
  activation range is a subset. All 46 committed result hashes remain intact.
  A dedicated wide probe checks 16,062 nearest records and 449,736 state cases,
  across modes and incoming flags; numeric/raw probes pass on six emulated
  architectures, default/portable and raw -O0/-O2. Independent reviews and
  staged numerical/branch mutations accompany the change. Native full build
  and sanitizer validation are recorded with the final verification below.
  Direct same-binary paired measurements improve large inputs about 3.2–3.3
  times versus the previous implementation, while remaining about 1.7–2.4
  times slower than host libm. Small-angle sine retains some measured overhead;
  there is no overall performance-win claim.

## Upcoming project-used gaps

1. Remaining project-used Float families beyond the completed exp/log, trig,
   hypotenuse and atan2 operations. Recheck current consumer usage before
   selecting the next API. Further trig tuning remains useful, especially
   small-path overhead and the residual wide-range libm gap. Float accuracy
   and exception handling remain separate targets.
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

The integer-rounding phase passes full final GCC14.2/GCC16.2 default gates,
198 unit tests in 25 binaries on GCC14/GCC16/Clang (Clang unit-only), and
four focused ASan/UBSan tests. Independent contract investigation and blind
review follow-ups are resolved. The new module is included in both legacy
mutation-harness object lists; initial incomplete-list failures were corrected
before the passing full runs. Thirteen native implementation/state plants,
four pinned oracle numerical faults, six payload checksum corruptions and
five actual probe-output field corruptions detect. Two signed32 post-rounding
range/sign defects detect on both i686 and powerpc32 emulation; LP64 default
runs skip those observationally equivalent mutations explicitly. Fresh guards
reject wrong metadata and ignored paths even with equal-sized fallback;
omission/corruption controls detect for all four new function hashes.

Committed full references contain 22,308 binary64 and 7,758 binary32 inputs,
each with exact signed32/signed64 answers and invalid classes. Six payloads,
including both native-width probe hashes, have mandatory complete-file SHA256
and LF protection. Pinned regeneration is byte-identical; three fresh samples
and a larger 224,060-input sample pass. The common valid signed32 subsets add
four portable result sets without folding native-width boundary differences
into a supposedly identical result hash:

| APIs | Common rows | Result hash |
| --- | ---: | --- |
| lround, llround | 12,886 each | `29062da116a95b78` |
| lroundf, llroundf | 5,792 each | `f55e957431a9f6ae` |

All 53 previous hashes and legacy aggregate `f5fa269eb60ee34f` remain unchanged.
Six emulated targets agree on all 57 sets in default/portable configurations.
Raw/full O0/O2 default/portable probes check 60,132 nearest public results and
51,408 selected all-mode/incoming-state calls per configuration. Native long32
uses nearest hash `f6b27ba135a01251`, all-mode hash `fc34d8bb72c277fd`;
long64 uses `11187661db241e79` and `8f0b8b6d02ea47e5`. The larger sample also
passes all six O2/default native-width probes, with 448,120 nearest results
and 313,992 selected-state calls each. These are emulated probes, not physical
hosts or full cross-target GoogleTest. Windows/LLP64 validation and native
32-bit timing remain unrun. Host pinned oracle controls pass; nested GCC16
optional controls skip explicitly, and required unavailable-oracle mode fails.

Two same-binary timing runs use 401 alternating pairs of 4,096 inputs per
range with clean and preseeded IX entry states. Every population first passes
untimed integer-result agreement, destination-bound and invalid checks.
The tool reports candidate/host median ns and paired ratio p10/p90. Across
both states/runs, common and half-tie double-input medians are about 1.14–1.22
of host libm, Float inputs 1.46–1.65; subnormal ranges are 0.75–0.87. Large
valid integral double inputs are 0.95–1.00, Float inputs about 1.41. Common
inputs use a small grid in [-4096,4096); these are controlled microbenchmarks,
not a project workload. Absolute timings vary between runs; call/loop/checksum
and timestamp overhead remain included. No overall/application speed win is
claimed. The initial capability phase favors exact deterministic contracts;
normal-range performance remains work to do.

The atanf phase passes full default GCC14.2/GCC16.2 gates and 194 unit tests
in 24 binaries on GCC14/GCC16/Clang (Clang's full gate set was not repeated).
Four focused ASan/UBSan tests pass. Independent numerical investigation and
blind review with two follow-ups are resolved. Seven wrapper/state plants
and five complete-payload checksum corruptions detect; publisher failure,
permissions and cleanup controls pass. Fresh selection rejects incorrect
metadata and ignored paths even with equal-sized fallback. Result-hash
omission/corruption controls also detect.

The committed 13,114-row corpus has SHA256
`9b5cf28ae9a2f394cad6d134ca3eaa227b454610434d73bc6c871c2435d05df6`.
Its result set 53 is `471e594171d32a6d`; all 52 previous function hashes and
legacy aggregate `f5fa269eb60ee34f` remain unchanged. A larger 107,903-row
sample and three fresh samples pass; the maximum conservative closed-cell
error is 0.50000002 ULP, under the 0.51 implementation regression cap.
General correct rounding remains unclaimed. Six emulated targets agree on
all 53 numeric sets in default/portable builds. Raw O0/O2 default/portable
probes agree on 42 fixtures, nearest hash `ba74d43d61e3eaf0` and all-mode
hash `97c05e26310d4b1c`; 1,176 calls separately assert flags, errno and mode
per configuration. These are emulated probes, not physical-host/full
cross-target GoogleTest claims. General directed accuracy remains unpromised.

Two successive same-binary benchmarks each use 401 alternating pairs of
4,096 inputs per range, with clean and preseeded UF/IX batch-entry controls.
Across those states/runs, median gmath/libm ratios are about 1.46–1.52 common,
1.68 table, 1.39–1.42 direct, 1.59–1.72 tiny normal, 0.18 subnormal and
1.99–2.09 wide finite. Integer timestamps and explicit entry-state checks
keep timing conversion from pre-raising IX. Entry-state controls amortize
first-exception costs across a batch; ratios include call/loop/checksum work.
The wrapper remains slower on most ranges; no overall or application speed
win is claimed. Unary specialization is a possible later optimization.

All four numerical budget certificates now reject optimized Python before
imports or proof work. `make check-budget-optimization` exercises -O, -OO and
PYTHONOPTIMIZE=1/2 on every certificate without requiring numerical dependencies,
then runs normal positive controls in the pinned image. The 16 negative probes
are mandatory; unavailable optional normal controls skip explicitly, and
required-oracle mode fails closed. This closes the earlier logf/log10f/hypotf
guard follow-up without changing runtime code, reference payloads or hashes.
Independent review also hardened required-script discovery, pre-import
rejection and image/version timeouts. Full GCC14.2/GCC16.2 default gates
pass, including 190 unit tests and all 52 committed result sets. The gate
itself passes under optimized Python; optional/required missing-image paths
and deliberately broken guards, imports, output and discovery are checked.
Normal pinned controls pass on the host and skip explicitly in the GCC16
image. No runtime change calls for new cross-target or performance claims.

The atan2f phase passes full default GCC14.2/GCC16.2 gates, 190 unit tests
on GCC14/GCC16/Clang and seven focused ASan/UBSan tests. Independent numerical
and blind reviews with follow-up are resolved. All 36 implementation/state
plants, 37 loader fixtures, four oracle faults, complete-payload/raw/output
hash corruptions, omitted entry and actual former-directory-typo checks pass.
The ordinary oracle gate verifies requested fresh metadata/population/path.
Its missing-directory probe leaves caller evidence untouched even on process
termination. The new certificate rejects optimized Python rather than printing
PASS with assertions disabled. Host pinned checks run; nested optional checks
skip explicitly in the GCC16 image. All 52 function result sets and the old
aggregate match on six emulated targets, with raw default/portable -O0/-O2
probes and 21,504 all-mode/incoming calls per run. The 229,222-row sample and
three fresh seeds pass; general all-input correct rounding, directed numerical
accuracy, physical-target timing and application performance remain unclaimed.

The hypotf phase passes full default GCC14.2/GCC16.2 gates, 183 unit tests
on GCC14/GCC16/Clang and seven focused ASan/UBSan tests. Independent numerical
and blind reviews with follow-up are resolved. Native mutation checks detect
42 implementation/state plants; forced-portable checks detect 31 and explicitly
skip 11 unavailable hardware plants. Both configurations pass 35 loader fixtures,
four oracle faults, strict target/reference integrity, raw/output hash and
actual former-directory-typo guards. Fresh metadata/population/path checks run
in the ordinary oracle gate too. The pinned certificate independently models
final flags and rejects five real-input flag-only deletions across all modes.
Host pinned checks run; optional nested oracles/certificates skip explicitly
in the GCC16 image. All 51 result sets and the old aggregate agree across six
emulated targets. Final 792-case raw probes pass default/portable at -O0/-O2;
22,176 calls per run separately assert all-mode/incoming state. Larger references
cover 229,568 pairs with strict nearest-target certificates and the same
0.50000003 conservative closed-cell bound. Physical-target timing, vector and
application performance remain unmeasured; directed libm semantics remain
outside this API's deterministic-nearest contract.

The log10f phase passes full default GCC14.2/GCC16.2 gates, 176 unit tests
on GCC14/GCC16/Clang and ten focused ASan/UBSan tests. Independent numerical
and blind reviews with follow-up are resolved. All 24 implementation/state
plants, 32 loader fixtures, four oracle faults, reference/raw/output hash
corruptions, omitted entry and actual former directory typo are detected.
The ordinary pinned-oracle gate now checks the source-linked numerical budget
and requested fresh metadata/population/path; staged coefficient/evaluation
drift and stale fresh metadata are rejected. Host pinned checks execute;
optional nested oracles/budget are explicitly skipped in the GCC16 image.
All 50 function result sets and the unchanged legacy aggregate agree on six
emulated targets; raw default/portable probes pass at -O0/-O2. The new raw
hash covers 778 nearest records, with 21,784 all-mode/incoming-state calls.
Four stratified fresh samples each supply 120 distinct inverse-midpoint
candidates and pass accuracy checks; committed data stays byte-identical.
These results do not claim all-input correct rounding, directed numerical
accuracy, physical-target coverage or an overall performance win.

The logf phase passes full default GCC14.2/GCC16.2 gates and 166 unit tests
on GCC14/GCC16/Clang, plus nine focused ASan/UBSan tests,
pinned reference regeneration, a 309,591-row direct-reference sample, and
independent review with follow-up. All 23 implementation/state plants, 28
loader fixtures, two parse-valid reference corruptions, four oracle faults,
raw/output hash corruptions, omitted-entry detection and the actual former
corpus-directory typo are detected on the host. Optional nested oracles are
explicitly skipped inside the GCC16 image and execute on the host. Fresh population and directory
selection are verified independently of row count. Six-target QEMU probes agree
on all 49 result sets; raw probes pass default/portable at -O0/-O2. The 668-row
raw logf hash covers nearest result/normalized flags; 18,704 calls separately
assert all-mode/incoming state. Native near-one scanning covers 524,288 calls.
These runs do not establish correctly rounded results for every input or
numerical accuracy in directed modes; physical-target and broader compatibility
coverage remain pending.

The expf phase passes full default GCC14.2/GCC16.2 gates and 157 unit tests
on GCC14/GCC16/Clang, plus nine focused ASan/UBSan tests. All 23 arithmetic/
state plants, 28 loader fixtures, two parse-valid reference corruptions, four
oracle faults and output/raw hash mutations are detected. Host pinned oracles
run; unavailable optional nested oracles are explicitly skipped in the GCC16
image. All 48 function result hashes agree on six emulated targets, with the
49-record raw expf probe passing default/portable -O0/-O2. Native all-mode
subnormal scanning covers 8,721,812 public/cast calls; deletion-only UF-force
sensitivity remains unverified and is not represented as public coverage.

The exp2f phase passes full default GCC14.2/GCC16.2 gates and 148 unit tests
on GCC14/GCC16/Clang, plus nine focused ASan/UBSan tests. All 23 arithmetic/
state plants, 28 loader fixtures, two parse-valid reference corruptions, four
oracle plants and output/raw hash mutations are detected. Optional nested
oracles are explicitly skipped inside the GCC16 image and executed on the host.
All 47 function hashes and the old aggregate agree on six emulated targets;
the 320-record raw exp2f probe also agrees at -O0/-O2, default/portable. A native
all-mode subnormal scan covers 6,815,648 public/cast calls; no force-only deletion
witness exists, so that narrow mutation claim remains explicitly unverified.

The wide-trig reduction phase passes full default `make test` gates on
GCC14.2 and GCC16.2, all 139 unit tests on GCC14/GCC16/Clang, and 14 focused
ASan/UBSan tests. All 34 implementation/branch/state plants, 66 loader fixtures,
three oracle mutations, three hash corruptions and three omissions are detected.
Pinned regeneration and fresh-reference checks execute on the host; optional
nested-oracle checks are explicitly skipped inside the GCC16 build image.
Independent numerical and blind reviews are resolved, including follow-up
review of the final dispatch and benchmark environment control.

The new exact APIs have independent committed reference corpora, fresh samples,
raw-bit NaN/zero/infinity tests, all four rounding modes, errno/exception-state
checks, mutation checks and supplemental result hashes. Existing hashes remain
unchanged. Build/test validation and independent reviews accompany each commit.

Math-only QEMU checks now match all 52 committed function hashes on i686,
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
