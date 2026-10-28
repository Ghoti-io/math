# Current-mode integer conversion performance investigation

**Status:** implemented and verified; final measurements pass the predeclared
admission rules. No new API. The exact integer fallback and public current-mode
contracts from commit 68e71f73a26360700f529db886d332def2dc0f41 remain unchanged.
All 84 function result sets and the legacy `f5fa269eb60ee34f` aggregate over
292711 results remain unchanged. Other runtime modules, the mode reader and
committed reference payloads are byte-identical.

## Valid-domain native conversion

The candidate retains the exact integer fallback and admits only normal inputs
whose rounded result fits in every standard direction. A signed32 destination
uses |x| < 2^30. Its largest possible upward magnitude is at most 2^30, safely
inside signed32. A signed64 destination uses |x| < 2^63. Binary32 inputs with
unbiased exponent at least 23, and binary64 inputs with exponent at least 52,
are integral; thus inputs near 2^63 cannot round across that boundary. Remaining
fractional inputs have magnitude below 2^52 (binary64) or 2^23 (binary32), with
ample destination headroom. The same argument applies to negative magnitudes
under downward rounding. Exact negative MIN and other boundary cases keep the
fallback.

Raw magnitude encodings increase with positive value. Subtracting the
minimum-normal encoding and comparing unsigned against the upper-minus-lower
interval accepts exactly this half-open normal range. Unsigned wrap rejects
zero and subnormals. Nonfinite encodings exceed the upper bound. No floating
classification or speculative conversion is needed before admission.

GNU-compatible SSE2 x86 builds use legacy CVTSD2SI/CVTSS2SI for native long.
Signed64 conversions require 64-bit instruction mode; i686 long long retains
the fallback. Explicit fenv-query configurations and GMATH_CURRENTINT_PORTABLE
also retain the fallback. Assembly operand alternatives support AT&T and Intel
GNU assembler dialects. Production code never writes caller controls.

Intel documents these conversions as observing MXCSR rounding direction, with
invalid and precision exceptions. Admission proves invalid cannot occur, so
this candidate needs no assumption about masked invalid versus precision
priority. Exact inputs add no flag; a nonintegral valid conversion adds precision
(inexact). Sticky flags and control bits remain intact. See the instruction
entries in [Intel Volume 2A](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf),
CVTSD2SI/CVTSS2SI, and the MXCSR/exception discussion in
[Intel Volume 1](https://www.intel.com/content/dam/support/us/en/documents/processors/pentium4/sb/25366521.pdf),
sections 10.2.3 and 11.5.2.2.

DAZ can change subnormal source values and their inexact behavior. Excluding
subnormals preserves the prior integer decoding path even when DAZ is enabled.
FTZ concerns floating underflow, which an integer destination cannot produce.
The bounded test fixtures toggle only supported DAZ/FTZ bits, discovered through
an initialized FXSAVE area and its MXCSR mask. They restore the caller environment.
This is bounded compatibility evidence; it does not expand the public promise
for arbitrary inconsistent or trapping hardware controls.

## Controlled own-project baseline

`make build-currentint-baseline` rebuilds the prior public module from the
explicit pinned revision using the actual library compiler arguments. It checks
that the two reused helper files equal that revision, then renames only the four
public symbols, preserving ABI leading underscores. It does not read another
math implementation. Default builds do not need this optional Git-based tool.

Set CURRENTINT_REFERENCE_OBJECT to the resulting prior.o for
`make check-currentint-prior` or `make bench-currentint-prior`. The probe target
runs the supported DAZ/FTZ fixtures and the committed raw/state corpus with both
implementations. The benchmark calls the prior functions directly. Explicit
objects, metadata and expected revision are checked on each forced relink.

Metadata binds declared revision, object bytes, selected compiler executable
and its invocation, and exact library arguments. It is not source authentication
for arbitrary supplied objects, nor a digest of every indirect toolchain
component. Compiler wrappers are unsupported; multiword commands and recognized
resolved ccache/sccache/distcc/icecc masquerading executables are rejected.
The separately rebuilt source/helper checks provide the controlled provenance
for this investigation. Windows/Darwin runtime validation is pending.

## Validation and limits

Sequential full GCC14.2 and GCC16.2 commands each return actual status zero.
Each main sequence invokes 243 tests in 34 binaries: 242 pass and one native32
case skips on LP64. Clang passes those counts unit-only. Six focused ASan/UBSan
tests invoke five passes and the same skip. Explicit-query and forced portable
targeted gates and units pass. Independent primary-architecture and blind
reviews, including follow-ups, resolve the reported implementation findings.

Six emulated targets match all 84 function sets in default and portable builds.
Thirty-six paired raw profiles cover O0/O2 and native/query/portable conversion
configurations on i686, AArch64, s390x, PowerPC64, PowerPC32 and SPARC64 Linux.
Each profile checks 1,145,696 logical API/state observations, making two physical
calls with the actual-prior hooks. Nearest digests are sampled within these
observations, not additional calls. Actual flags, errno, rounding direction and
promised controls are checked separately; requested incoming subsets can merge.
The width-specific hashes in `tests/corpus/currentint-special.hash` remain
unchanged. Six i686 profiles additionally pass 49,152 paired DAZ/FTZ observations
each. The final i686 O0 raw argument construction has no fldl/flds loads.
Twelve native clients actually link and run without libm.

Cross comparison translation units use exactly the same target compiler/library
arguments; the prior source and reused helpers were checked against Git. Target
compiler/image/object context is manually bound by host orchestration. This is
not a claim that the Python-based optional Make validator ran in the cross
compiler environment, nor source authentication for arbitrary supplied objects.
These are emulated probes, not physical-host or full cross-target GoogleTest
coverage. Native32 equality, narrowing and premature-IX defects detect on both
i686 and PowerPC32; the last fails Double while leaving Float passing. Actual
host-Python controllers validate both new paired native32 probes; replacing
compiled-width selection with the host64 assumption is rejected on each.

Three retained independent fresh populations and the retained larger population
pass complete population, targets, widening, directory selection, actual C++
unit selection, all-84-set overlays and actual-prior raw/state comparisons on
both native compilers. They were generated independently during the preceding
API phase; these are new executions against retained data, not newly generated
samples. Larger populations contain 72,184 Double and 45,041 Float rows and
check 3,335,824 logical API/state observations per native context, doubled in
physical calls by the prior hooks. No new larger cross-target run is claimed.

The portable kernel's 18 shared and four format/range source plants still detect
in C17/C++; native, portable and query controls pass. Native truncation, IX loss,
control-bit corruption and subnormal admission faults detect. The last requires
advertised DAZ support and fails the DAZ fixtures while ordinary corpus calls
remain passing. The portable force-only IX deletion witness at minimum
subnormals remains verified. All existing oracle/checksum/loader controls pass;
nested optional numerical engines skip explicitly in GCC16, while mandatory
payload and recording controls still run. Recording controls are accounting,
not numerical oracle evidence.

Ten baseline byte/context/schema/wrapper faults and header publication controls
pass. Actual native14/16 Make invocations reject wrong revision, library flags,
compiler identity, object digest and stale object bytes. Forced relinks are
observed. An intentionally altered prior module with deleted IX forcing is
rejected through real paired state calls, then the genuine tools are restored.
This deliberately supplied false provenance illustrates why metadata is not
source authentication. Reduced forwarding benchmark controls check prior value,
invalid/errno and batch-only timed-state defects at their intended guard.

An exploratory four-mode result-only comparison matches 527,080 Float result
pairs in 52 intervals with overlapping boundary windows. It is compatibility
only, not independent accuracy or exhaustive flags/input coverage. The primary
valid-domain proof and independent exact corpus targets provide separate
correctness evidence.

Two mutant-only unused-local compile failures were corrected before their final
passing controls. An initial Intel-assembly-dialect compile failed; the operand
alternatives fix compiles successfully. Neither is a relabelled numerical pass.
A waiting orchestration process was stopped before dependent stages to remove
an inappropriate nested aggregate memory cap; all actual final builds retain
their recorded statuses. Numerical source and the runtime comparison/benchmark
harness stayed frozen through full validation and final timing. A later calibration-only correction
keeps default gates usable with a configured compiler wrapper while explicitly
rejecting that wrapper for optional baseline construction. The affected gate
passes direct and wrapped command configurations on both native compilers;
full-suite invocations preceded this control-only correction.

Valgrind was not rerun for this optimization. The preceding failed partial scope
remains failed: missing instrumented IX/IV, with independent plain arithmetic
reproducers, zero reported memory errors/leaks but early-stop partial coverage.
No assertion was weakened and the new DAZ test has no new Valgrind claim. Earlier
expf/exp2f/atanf/cbrtf force-only IX deletion witnesses remain unverified and their
production forces remain. Windows/LLP64, Darwin, RISC-V, numerical soft-float,
physical cross-target hosts, exhaustive environments and application timing are
unrun. The Windows-compatible compiler predicate is not runtime verification.

## Predeclared timing admission

Before exploratory timing, the investigation fixed these final limits: normal
and half-tie current/prior paired median ratios at most 0.75 in every native64
case; other admitted normal ranges at most 1.05. Fallback-heavy ranges require
ratio at most 1.20 or a difference of separate median call times at most 2 ns.
That latter quantity is not a paired time difference. All final cases pass.

Two final runs per compiler and comparison retain 2,816 records in
[current-integer-performance-timings.json](current-integer-performance-timings.json).
Each run uses eight paired warmups, 401 alternating pairs of 4,096 equal inputs,
integer timestamps, timed checksums and untimed per-input value/state/errno
checks. Call/loop/checksum/timestamp overhead and amortized first-exception costs
are included. Fixed logical affinity provides no CPU isolation or governor
control. No failed admission was replaced by selected timing or changed limits.
The preliminary exploratory run remains separate.

Ordinary current/prior median ratios span 0.106–0.221 on GCC14 and 0.104–0.161 on
GCC16, about 4.5–9.6 times faster in these scalar measurements. Ordinary current/
host ratios remain 1.297–1.502 and 1.132–1.334 respectively. Subnormals remain
6.472–10.871 times host. No overall, application or cross-platform win is claimed.

Retain the measured regressions: GCC14 subnormal ratios reach 1.296, with a
maximum difference of separate medians of 1.814 ns/call; finite-overflow ratios
reach 1.740 on GCC14 and 1.839 on GCC16, with maximum median differences of
1.658 and 1.608 ns. Some special/zero paths also regress. These pass the declared
absolute fallback allowance; they do not establish general nonregression or a
net workload gain.

## Complete timing envelopes

Each row combines both final runs, four modes and two entry states for one API
and range: 16 records. Times are ranges of separate median amortized ns/call;
paired p10/median/p90 columns give the minimum–maximum quantile across those
records. The full JSON preserves each individual case.

### GCC14 / actual prior

| API | Range | Current ns/call | Other ns/call | Paired p10 | Paired median | Paired p90 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| lrint | normal | 1.193–2.676 | 7.503–15.305 | 0.120–0.206 | 0.121–0.221 | 0.123–0.232 |
| lrint | half-ties | 1.192–2.683 | 8.182–13.419 | 0.134–0.196 | 0.137–0.203 | 0.139–0.210 |
| lrint | subnormal | 7.183–8.014 | 5.833–7.148 | 1.042–1.253 | 1.072–1.296 | 1.099–1.337 |
| lrint | large-integral | 1.083–1.255 | 6.515–7.372 | 0.161–0.169 | 0.164–0.173 | 0.167–0.176 |
| lrint | zero | 2.051–2.507 | 1.850–2.261 | 1.105–1.106 | 1.108–1.121 | 1.111–1.127 |
| lrint | infinity | 2.571–2.790 | 2.146–2.328 | 1.108–1.191 | 1.197–1.199 | 1.202–1.221 |
| lrint | qNaN | 2.571–2.789 | 2.146–2.327 | 1.109–1.195 | 1.197–1.199 | 1.202–1.221 |
| lrint | sNaN | 2.573–2.787 | 2.148–2.440 | 1.108–1.196 | 1.114–1.199 | 1.202–1.222 |
| lrint | wide-integral | 1.321–1.427 | 5.962–6.512 | 0.213–0.222 | 0.218–0.225 | 0.223–0.231 |
| lrint | finite-overflow | 2.998–3.366 | 2.155–2.888 | 0.937–1.207 | 1.199–1.391 | 1.368–1.637 |
| lrint | boundary32 | 1.162–1.288 | 6.609–9.561 | 0.131–0.174 | 0.133–0.177 | 0.134–0.179 |
| llrint | normal | 1.033–1.118 | 7.646–10.327 | 0.104–0.135 | 0.106–0.138 | 0.108–0.140 |
| llrint | half-ties | 0.961–1.091 | 7.650–8.966 | 0.118–0.125 | 0.120–0.127 | 0.122–0.130 |
| llrint | subnormal | 6.623–7.533 | 5.883–7.055 | 1.023–1.142 | 1.048–1.177 | 1.068–1.221 |
| llrint | large-integral | 0.960–1.081 | 6.575–7.446 | 0.141–0.145 | 0.144–0.149 | 0.147–0.256 |
| llrint | zero | 1.872–2.361 | 1.639–2.068 | 1.069–1.139 | 1.074–1.143 | 1.144–1.148 |
| llrint | infinity | 2.249–2.510 | 1.888–2.447 | 0.890–1.196 | 0.947–1.199 | 1.004–1.202 |
| llrint | qNaN | 2.155–2.375 | 1.835–2.263 | 0.878–1.185 | 0.946–1.198 | 1.003–1.202 |
| llrint | sNaN | 2.086–2.583 | 1.841–2.298 | 0.920–1.184 | 1.000–1.199 | 1.074–1.208 |
| llrint | wide-integral | 1.120–1.316 | 7.193–8.424 | 0.151–0.154 | 0.155–0.158 | 0.160–0.164 |
| llrint | finite-overflow | 3.085–3.802 | 2.027–2.200 | 1.454–1.644 | 1.519–1.740 | 1.528–1.819 |
| llrint | boundary32 | 0.982–1.122 | 6.797–9.421 | 0.116–0.147 | 0.118–0.151 | 0.119–0.153 |
| lrintf | normal | 1.108–1.160 | 7.644–10.730 | 0.103–0.144 | 0.106–0.146 | 0.108–0.148 |
| lrintf | half-ties | 0.977–2.420 | 7.644–14.393 | 0.007–0.159 | 0.123–0.168 | 0.125–0.175 |
| lrintf | subnormal | 7.000–8.417 | 5.951–7.696 | 1.051–1.147 | 1.080–1.178 | 1.105–1.203 |
| lrintf | large-integral | 1.005–1.121 | 7.204–8.047 | 0.134–0.137 | 0.137–0.140 | 0.140–0.144 |
| lrintf | zero | 2.044–2.552 | 1.931–2.352 | 0.867–1.078 | 1.072–1.083 | 1.084–1.092 |
| lrintf | infinity | 2.318–2.655 | 1.979–2.266 | 1.107–1.169 | 1.170–1.172 | 1.174–1.175 |
| lrintf | qNaN | 2.258–2.662 | 1.927–2.299 | 1.122–1.169 | 1.168–1.172 | 1.174–1.175 |
| lrintf | sNaN | 2.321–2.655 | 1.981–2.268 | 1.105–1.169 | 1.168–1.172 | 1.174–1.175 |
| lrintf | wide-integral | 1.162–1.346 | 7.544–8.573 | 0.151–0.156 | 0.156–0.160 | 0.161–0.168 |
| lrintf | finite-overflow | 2.993–3.803 | 2.125–2.252 | 1.277–1.526 | 1.403–1.575 | 1.487–1.745 |
| lrintf | boundary32 | 0.920–1.154 | 6.716–8.479 | 0.008–0.135 | 0.136–0.139 | 0.139–0.143 |
| llrintf | normal | 1.185–1.325 | 7.275–11.179 | 0.115–0.160 | 0.117–0.164 | 0.119–0.166 |
| llrintf | half-ties | 1.158–1.325 | 7.937–9.311 | 0.135–0.145 | 0.139–0.150 | 0.143–0.154 |
| llrintf | subnormal | 6.873–8.455 | 6.336–7.927 | 1.012–1.075 | 1.039–1.118 | 1.070–1.145 |
| llrintf | large-integral | 1.158–1.323 | 7.329–8.289 | 0.152–0.157 | 0.158–0.164 | 0.162–0.167 |
| llrintf | zero | 2.161–2.510 | 2.057–2.302 | 0.852–1.060 | 1.062–1.066 | 1.067–1.374 |
| llrintf | infinity | 2.315–2.586 | 2.190–2.443 | 0.998–1.056 | 1.001–1.059 | 1.017–1.173 |
| llrintf | qNaN | 2.264–2.583 | 2.189–2.508 | 0.998–1.056 | 1.003–1.059 | 1.061–1.063 |
| llrintf | sNaN | 2.318–2.587 | 2.190–2.507 | 0.998–1.056 | 1.003–1.059 | 1.061–1.067 |
| llrintf | wide-integral | 1.298–1.445 | 7.488–8.265 | 0.147–0.172 | 0.172–0.178 | 0.177–0.184 |
| llrintf | finite-overflow | 2.831–3.524 | 2.153–2.488 | 1.034–1.230 | 1.211–1.468 | 1.319–1.518 |
| llrintf | boundary32 | 1.190–1.361 | 7.608–8.655 | 0.147–0.155 | 0.155–0.160 | 0.159–0.166 |

### GCC14 / host libm

| API | Range | Current ns/call | Other ns/call | Paired p10 | Paired median | Paired p90 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| lrint | normal | 1.137–1.293 | 0.885–0.992 | 1.281–1.301 | 1.302–1.304 | 1.305–1.319 |
| lrint | half-ties | 1.164–2.407 | 0.892–1.889 | 1.112–1.301 | 1.286–1.305 | 1.307–1.517 |
| lrint | subnormal | 6.801–10.000 | 0.915–1.551 | 5.534–7.851 | 6.472–8.015 | 7.452–8.207 |
| lrint | large-integral | 1.134–1.290 | 0.871–0.990 | 1.287–1.301 | 1.302–1.304 | 1.305–1.321 |
| lrint | zero | 2.260–2.444 | 0.892–0.964 | 2.385–2.531 | 2.488–2.536 | 2.540–2.561 |
| lrint | infinity | 2.330–2.724 | 0.871–0.994 | 2.667–2.674 | 2.671–2.812 | 2.680–2.829 |
| lrint | qNaN | 2.331–2.728 | 0.872–1.018 | 2.637–2.808 | 2.676–2.816 | 2.684–2.834 |
| lrint | sNaN | 2.390–2.810 | 0.894–1.047 | 2.592–2.808 | 2.675–2.815 | 2.681–2.834 |
| lrint | wide-integral | 1.239–1.410 | 0.870–0.991 | 1.374–1.401 | 1.401–1.421 | 1.408–1.443 |
| lrint | finite-overflow | 2.443–3.078 | 0.872–0.963 | 2.497–2.801 | 2.609–3.280 | 3.099–3.297 |
| lrint | boundary32 | 1.079–1.254 | 0.828–0.963 | 1.278–1.301 | 1.302–1.305 | 1.305–1.324 |
| llrint | normal | 0.938–1.089 | 0.644–0.818 | 1.306–1.352 | 1.331–1.494 | 1.333–1.518 |
| llrint | half-ties | 0.937–1.183 | 0.644–0.889 | 1.294–1.491 | 1.330–1.494 | 1.332–1.513 |
| llrint | subnormal | 6.949–7.845 | 0.693–0.839 | 8.671–9.957 | 8.890–10.871 | 9.126–11.189 |
| llrint | large-integral | 0.961–1.117 | 0.720–0.818 | 1.306–1.329 | 1.330–1.376 | 1.333–1.498 |
| llrint | zero | 1.917–2.434 | 0.720–0.892 | 2.492–2.650 | 2.653–2.711 | 2.687–2.992 |
| llrint | infinity | 2.219–2.538 | 0.693–0.842 | 2.821–3.254 | 2.985–3.348 | 3.020–3.384 |
| llrint | qNaN | 2.261–2.656 | 0.693–0.843 | 2.819–2.981 | 2.986–3.345 | 3.344–3.375 |
| llrint | sNaN | 2.255–2.578 | 0.693–0.818 | 2.975–3.266 | 2.986–3.348 | 3.347–3.369 |
| llrint | wide-integral | 1.164–1.824 | 0.691–1.241 | 1.269–1.699 | 1.515–1.705 | 1.702–1.733 |
| llrint | finite-overflow | 2.988–3.569 | 0.693–0.778 | 3.634–4.325 | 4.125–4.757 | 4.464–5.097 |
| llrint | boundary32 | 1.034–1.091 | 0.694–0.819 | 1.328–1.490 | 1.330–1.494 | 1.333–1.497 |
| lrintf | normal | 1.013–1.131 | 0.765–0.851 | 1.316–1.323 | 1.327–1.329 | 1.337–1.350 |
| lrintf | half-ties | 1.014–1.122 | 0.767–0.851 | 1.309–1.316 | 1.317–1.321 | 1.327–1.337 |
| lrintf | subnormal | 6.550–7.194 | 0.784–0.826 | 8.120–8.729 | 8.301–8.909 | 8.427–9.135 |
| lrintf | large-integral | 1.020–1.098 | 0.767–0.829 | 1.310–1.316 | 1.318–1.320 | 1.328–1.340 |
| lrintf | zero | 2.047–2.186 | 0.767–0.828 | 2.630–2.641 | 2.637–2.669 | 2.643–2.676 |
| lrintf | infinity | 2.135–2.311 | 0.767–0.829 | 2.780–2.782 | 2.787–2.792 | 2.793–2.956 |
| lrintf | qNaN | 2.084–2.328 | 0.748–0.830 | 2.725–2.783 | 2.786–2.946 | 2.792–2.956 |
| lrintf | sNaN | 2.082–2.323 | 0.748–0.830 | 2.780–2.782 | 2.787–2.792 | 2.792–2.955 |
| lrintf | wide-integral | 1.162–1.214 | 0.785–0.807 | 1.473–1.486 | 1.479–1.502 | 1.496–1.510 |
| lrintf | finite-overflow | 2.511–3.158 | 0.767–0.827 | 2.940–3.809 | 3.258–3.819 | 3.285–3.829 |
| lrintf | boundary32 | 1.035–1.091 | 0.785–0.827 | 1.314–1.316 | 1.318–1.321 | 1.328–1.337 |
| llrintf | normal | 1.188–3.071 | 0.915–2.028 | 1.172–1.298 | 1.297–1.502 | 1.300–1.554 |
| llrintf | half-ties | 1.188–1.284 | 0.916–0.989 | 1.271–1.296 | 1.298–1.299 | 1.300–1.315 |
| llrintf | subnormal | 6.897–7.559 | 0.917–0.941 | 7.379–7.934 | 7.491–8.061 | 7.612–8.232 |
| llrintf | large-integral | 1.189–1.253 | 0.917–0.965 | 1.251–1.295 | 1.298–1.298 | 1.301–1.302 |
| llrintf | zero | 2.191–2.312 | 0.914–0.965 | 2.387–2.391 | 2.394–2.397 | 2.401–2.416 |
| llrintf | infinity | 2.316–2.510 | 0.915–0.992 | 2.499–2.527 | 2.530–2.533 | 2.536–2.557 |
| llrintf | qNaN | 2.263–2.578 | 0.895–1.018 | 2.525–2.527 | 2.531–2.533 | 2.536–2.550 |
| llrintf | sNaN | 2.316–2.510 | 0.915–0.992 | 2.476–2.526 | 2.531–2.533 | 2.536–2.560 |
| llrintf | wide-integral | 1.304–1.375 | 0.915–0.965 | 1.419–1.423 | 1.425–1.428 | 1.429–1.445 |
| llrintf | finite-overflow | 2.750–3.368 | 0.915–0.965 | 2.660–3.271 | 3.010–3.551 | 3.277–3.747 |
| llrintf | boundary32 | 1.218–2.569 | 0.940–2.052 | 1.081–1.295 | 1.250–1.298 | 1.301–1.365 |

### GCC16 / actual prior

| API | Range | Current ns/call | Other ns/call | Paired p10 | Paired median | Paired p90 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| lrint | normal | 1.189–1.251 | 7.421–10.143 | 0.117–0.159 | 0.120–0.161 | 0.121–0.164 |
| lrint | half-ties | 1.187–1.251 | 8.166–8.808 | 0.138–0.146 | 0.143–0.148 | 0.144–0.151 |
| lrint | subnormal | 7.353–7.966 | 6.592–7.448 | 0.995–1.096 | 1.036–1.133 | 1.077–1.171 |
| lrint | large-integral | 1.188–1.250 | 6.976–7.316 | 0.166–0.169 | 0.169–0.173 | 0.171–0.180 |
| lrint | zero | 2.206–2.334 | 2.070–2.184 | 0.953–1.064 | 1.066–1.069 | 1.069–1.078 |
| lrint | infinity | 2.319–2.444 | 2.068–2.272 | 1.063–1.091 | 1.072–1.120 | 1.095–1.126 |
| lrint | qNaN | 2.321–4.838 | 2.123–4.271 | 0.987–1.091 | 1.073–1.123 | 1.096–1.361 |
| lrint | sNaN | 2.314–2.444 | 2.067–2.276 | 1.063–1.080 | 1.074–1.120 | 1.094–1.127 |
| lrint | wide-integral | 1.302–1.355 | 6.067–6.339 | 0.207–0.212 | 0.212–0.219 | 0.215–0.221 |
| lrint | finite-overflow | 2.561–3.158 | 2.167–2.346 | 1.056–1.148 | 1.183–1.363 | 1.191–1.390 |
| lrint | boundary32 | 1.186–1.251 | 6.600–9.322 | 0.129–0.180 | 0.133–0.183 | 0.134–0.186 |
| llrint | normal | 1.033–1.062 | 7.440–10.155 | 0.095–0.138 | 0.104–0.141 | 0.107–0.143 |
| llrint | half-ties | 0.975–1.090 | 8.047–8.662 | 0.112–0.129 | 0.121–0.131 | 0.125–0.134 |
| llrint | subnormal | 7.202–7.996 | 6.981–7.555 | 0.972–1.030 | 1.006–1.068 | 1.040–1.103 |
| llrint | large-integral | 0.960–1.150 | 6.401–7.578 | 0.138–0.149 | 0.150–0.152 | 0.152–0.187 |
| llrint | zero | 1.805–2.100 | 1.682–1.957 | 1.067–1.071 | 1.072–1.074 | 1.075–1.150 |
| llrint | infinity | 2.010–2.232 | 1.818–2.019 | 1.099–1.103 | 1.104–1.106 | 1.108–1.111 |
| llrint | qNaN | 2.064–2.233 | 1.869–2.021 | 1.099–1.103 | 1.104–1.106 | 1.108–1.108 |
| llrint | sNaN | 2.013–2.233 | 1.822–2.021 | 1.098–1.103 | 1.103–1.106 | 1.108–1.126 |
| llrint | wide-integral | 1.170–1.255 | 7.389–7.925 | 0.152–0.157 | 0.157–0.164 | 0.160–0.171 |
| llrint | finite-overflow | 2.834–3.597 | 1.857–2.020 | 1.084–1.489 | 1.487–1.839 | 1.533–1.858 |
| llrint | boundary32 | 0.973–1.117 | 6.849–9.520 | 0.105–0.150 | 0.111–0.152 | 0.116–0.172 |
| lrintf | normal | 0.991–1.123 | 7.103–10.144 | 0.103–0.141 | 0.105–0.143 | 0.107–0.146 |
| lrintf | half-ties | 1.012–1.092 | 7.959–9.404 | 0.008–0.127 | 0.115–0.130 | 0.116–0.132 |
| lrintf | subnormal | 6.912–7.796 | 6.893–7.635 | 0.959–1.003 | 0.996–1.039 | 1.029–1.077 |
| lrintf | large-integral | 0.984–1.119 | 7.263–8.155 | 0.132–0.134 | 0.136–0.139 | 0.139–0.144 |
| lrintf | zero | 2.001–2.322 | 1.760–2.044 | 1.126–1.128 | 1.130–1.135 | 1.133–1.331 |
| lrintf | infinity | 2.144–2.567 | 1.850–2.098 | 1.117–1.122 | 1.121–1.286 | 1.132–1.465 |
| lrintf | qNaN | 2.141–2.485 | 1.897–2.219 | 1.116–1.119 | 1.121–1.131 | 1.133–1.379 |
| lrintf | sNaN | 2.094–2.423 | 1.854–2.158 | 1.116–1.119 | 1.120–1.134 | 1.123–1.294 |
| lrintf | wide-integral | 1.176–1.283 | 7.561–8.205 | 0.151–0.155 | 0.154–0.158 | 0.158–0.165 |
| lrintf | finite-overflow | 2.282–3.344 | 1.965–2.234 | 1.105–1.573 | 1.127–1.581 | 1.346–1.666 |
| lrintf | boundary32 | 1.033–1.088 | 7.497–8.065 | 0.010–0.135 | 0.134–0.138 | 0.138–0.182 |
| llrintf | normal | 1.184–1.247 | 7.675–10.569 | 0.114–0.156 | 0.116–0.157 | 0.117–0.159 |
| llrintf | half-ties | 1.181–1.248 | 8.211–8.949 | 0.135–0.143 | 0.137–0.145 | 0.139–0.148 |
| llrintf | subnormal | 7.221–7.883 | 7.024–7.584 | 0.965–1.016 | 1.008–1.055 | 1.042–1.177 |
| llrintf | large-integral | 1.183–1.281 | 7.567–8.361 | 0.148–0.155 | 0.153–0.158 | 0.158–0.164 |
| llrintf | zero | 2.333–2.527 | 2.085–2.256 | 1.114–1.117 | 1.119–1.124 | 1.122–1.129 |
| llrintf | infinity | 2.407–2.605 | 2.129–2.304 | 1.113–1.128 | 1.129–1.131 | 1.134–1.146 |
| llrintf | qNaN | 2.348–2.602 | 2.106–2.300 | 1.112–1.128 | 1.129–1.131 | 1.134–1.146 |
| llrintf | sNaN | 2.402–2.606 | 2.123–2.304 | 1.113–1.128 | 1.128–1.131 | 1.134–1.164 |
| llrintf | wide-integral | 1.302–1.410 | 7.436–8.072 | 0.011–0.173 | 0.174–0.178 | 0.178–0.185 |
| llrintf | finite-overflow | 2.834–3.699 | 2.152–2.340 | 1.147–1.296 | 1.301–1.613 | 1.389–1.633 |
| llrintf | boundary32 | 1.183–1.281 | 7.479–8.292 | 0.148–0.156 | 0.153–0.158 | 0.158–0.163 |

### GCC16 / host libm

| API | Range | Current ns/call | Other ns/call | Paired p10 | Paired median | Paired p90 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| lrint | normal | 1.156–1.287 | 1.018–1.131 | 1.113–1.130 | 1.132–1.140 | 1.138–1.152 |
| lrint | half-ties | 1.176–1.315 | 1.042–1.162 | 1.116–1.127 | 1.129–1.137 | 1.140–1.143 |
| lrint | subnormal | 6.841–7.460 | 1.043–1.118 | 6.357–6.843 | 6.526–6.998 | 6.640–7.164 |
| lrint | large-integral | 1.154–1.284 | 1.017–1.130 | 1.116–1.129 | 1.129–1.136 | 1.140–1.143 |
| lrint | zero | 2.207–2.389 | 1.043–1.127 | 2.094–2.118 | 2.117–2.123 | 2.126–2.136 |
| lrint | infinity | 2.094–2.380 | 0.969–1.099 | 2.157–2.158 | 2.162–2.208 | 2.166–2.248 |
| lrint | qNaN | 2.059–2.314 | 0.946–1.070 | 2.157–2.167 | 2.162–2.223 | 2.166–2.228 |
| lrint | sNaN | 2.094–2.317 | 0.968–1.072 | 2.157–2.160 | 2.162–2.220 | 2.166–2.228 |
| lrint | wide-integral | 1.191–1.368 | 0.969–1.101 | 1.221–1.227 | 1.225–1.253 | 1.232–1.257 |
| lrint | finite-overflow | 2.553–5.207 | 0.968–2.087 | 2.313–2.634 | 2.523–2.800 | 2.727–2.904 |
| lrint | boundary32 | 1.100–2.890 | 0.970–2.299 | 1.105–1.193 | 1.128–1.252 | 1.139–1.347 |
| llrint | normal | 0.960–2.328 | 0.728–1.749 | 1.208–1.316 | 1.211–1.334 | 1.212–1.466 |
| llrint | half-ties | 0.904–1.120 | 0.729–0.898 | 1.190–1.317 | 1.210–1.319 | 1.232–1.321 |
| llrint | subnormal | 6.393–7.792 | 0.710–0.849 | 8.396–9.205 | 8.675–9.330 | 8.794–9.881 |
| llrint | large-integral | 0.924–1.089 | 0.764–0.848 | 1.208–1.316 | 1.210–1.319 | 1.212–1.322 |
| llrint | zero | 1.896–1.992 | 0.767–0.804 | 2.470–2.472 | 2.476–2.477 | 2.482–2.483 |
| llrint | infinity | 2.007–2.361 | 0.763–0.897 | 2.579–2.626 | 2.629–2.632 | 2.635–2.652 |
| llrint | qNaN | 1.866–2.294 | 0.709–0.872 | 2.624–2.626 | 2.630–2.632 | 2.636–2.648 |
| llrint | sNaN | 2.010–2.299 | 0.764–0.874 | 2.623–2.626 | 2.630–2.632 | 2.636–2.649 |
| llrint | wide-integral | 1.106–1.285 | 0.763–0.874 | 1.374–1.450 | 1.379–1.475 | 1.451–1.484 |
| llrint | finite-overflow | 2.063–2.895 | 0.765–0.872 | 2.625–2.630 | 2.631–3.498 | 2.638–3.511 |
| llrint | boundary32 | 0.903–1.219 | 0.746–0.925 | 1.208–1.316 | 1.211–1.318 | 1.213–1.321 |
| lrintf | normal | 0.987–1.121 | 0.871–0.990 | 1.130–1.132 | 1.133–1.135 | 1.135–1.151 |
| lrintf | half-ties | 1.008–1.119 | 0.893–0.992 | 1.126–1.128 | 1.128–1.131 | 1.130–1.133 |
| lrintf | subnormal | 6.266–7.550 | 0.872–0.964 | 7.031–7.683 | 7.166–7.974 | 7.267–8.309 |
| lrintf | large-integral | 1.031–1.121 | 0.914–0.993 | 1.126–1.127 | 1.128–1.129 | 1.130–1.132 |
| lrintf | zero | 2.188–2.326 | 0.914–0.967 | 2.385–2.402 | 2.392–2.409 | 2.397–2.417 |
| lrintf | infinity | 2.199–2.440 | 0.893–0.991 | 2.455–2.457 | 2.460–2.463 | 2.465–2.469 |
| lrintf | qNaN | 2.254–2.440 | 0.916–0.991 | 2.455–2.457 | 2.461–2.463 | 2.466–2.471 |
| lrintf | sNaN | 2.201–2.443 | 0.894–0.992 | 2.455–2.457 | 2.461–2.463 | 2.466–2.469 |
| lrintf | wide-integral | 1.154–1.222 | 0.916–0.966 | 1.246–1.257 | 1.252–1.265 | 1.265–1.282 |
| lrintf | finite-overflow | 2.314–2.556 | 0.915–0.991 | 2.480–2.525 | 2.526–2.721 | 2.532–3.288 |
| lrintf | boundary32 | 1.008–1.090 | 0.893–0.966 | 1.126–1.127 | 1.128–1.129 | 1.130–1.132 |
| llrintf | normal | 1.152–1.314 | 1.018–1.162 | 1.128–1.129 | 1.132–1.133 | 1.135–1.136 |
| llrintf | half-ties | 1.155–1.317 | 1.020–1.164 | 1.125–1.129 | 1.132–1.133 | 1.135–1.137 |
| llrintf | subnormal | 7.075–7.853 | 1.045–1.101 | 6.504–7.246 | 6.768–7.338 | 6.883–7.410 |
| llrintf | large-integral | 1.182–1.246 | 1.044–1.101 | 1.126–1.129 | 1.132–1.132 | 1.135–1.137 |
| llrintf | zero | 2.328–2.460 | 1.045–1.102 | 2.195–2.227 | 2.224–2.232 | 2.231–2.246 |
| llrintf | infinity | 2.346–2.602 | 1.020–1.131 | 2.295–2.297 | 2.300–2.302 | 2.306–2.316 |
| llrintf | qNaN | 2.346–2.603 | 1.020–1.131 | 2.295–2.297 | 2.300–2.302 | 2.306–2.307 |
| llrintf | sNaN | 2.403–2.600 | 1.044–1.129 | 2.295–2.297 | 2.300–2.303 | 2.306–2.308 |
| llrintf | wide-integral | 1.254–1.353 | 1.020–1.103 | 1.212–1.221 | 1.217–1.229 | 1.222–1.235 |
| llrintf | finite-overflow | 2.454–2.744 | 1.044–1.102 | 2.342–2.345 | 2.347–2.620 | 2.354–2.643 |
| llrintf | boundary32 | 1.183–1.215 | 1.045–1.073 | 1.129–1.130 | 1.132–1.133 | 1.135–1.136 |
