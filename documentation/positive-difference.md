# Positive difference

The binary64 and binary32 APIs and verification tooling are verified. Independent
mathematical, blind and final evidence reviews are resolved. Existing runtime modules,
all 84 earlier function result sets and the legacy aggregate remain unchanged.

## Contract

`gmath_fdim(x,y)` and `gmath_fdimf(x,y)` provide positive difference. Ordered
x<=y returns positive zero, including both signed-zero orders and equal
infinities. Ordered x>y returns the difference, with an infinite operand giving
positive infinity without new flags. Both NaNs are classified first: either
NaN yields the canonical positive quiet NaN; invalid is added only if either
input signals. A quiet first NaN must not hide a signaling second NaN.

The branch definition comes from [WG14 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf),
7.12.12.1 and F.10.9.1. The explicit project choices are nearest/ties-even finite
bits in every standard rounding mode, canonical NaNs, signaling-NaN invalid,
and errno preservation. Exact finite results add no flags, other finite results
add inexact, and rounded overflow returns positive infinity with overflow and
inexact. Full directed numerical, errno or long-double libm parity is not
promised. Caller mode and incoming standard flags are preserved; production
code never writes controls.

No underflow is needed: every finite input is an integer multiple of the
minimum subnormal delta. Their exact difference is also on that lattice.
A positive result below minimum normal has fewer than P significant lattice
bits, so it is exactly representable. Distinct ordered finite inputs cannot
produce a positive difference rounded to zero.

## Integer derivation

Let p be fraction width (52 or 23), P=p+1 the precision, and normalize nonzero
finite magnitudes as m*2^(E-p), with 2^p<=m<2^(p+1). Raw ordering identifies the
larger magnitude A and smaller B. Opposite input signs require addition of
magnitudes; equal input signs require subtraction. Nonpositive ordered results,
zero operands and nonfinite arguments are already dispatched.

For leading-exponent gap d, exact alignment forms
N=(m_A<<d) plus or minus m_B, with unit exponent E_B-p. If d<=p+2 (54 or 25),
two uint64 limbs suffice: the largest intermediate uses 107 bits. Low-word
unsigned comparisons detect carry/borrow. In subtraction the magnitude order
ensures N>0; addition is also positive, so top-bit counting never sees zero.

For larger gaps, B<2^(E_A-d+1). The smallest midpoint distance adjacent to A is
2^(E_A-P-1), at the predecessor side of an exact power of two. Thus d>=P+2,
equivalently d>=p+3 (55 or 26), puts B strictly below either midpoint. The
rounded result is A with inexact, since nonzero B cannot give an exact P-bit
result at that spacing.

The preceding gap is essential. For A=1 and B=0x1.fffffffffffffp-54, the exact
subtraction rounds to the predecessor of one. An early planning proposal used
the ordinary-binade midpoint and was off by one; this counterexample corrected
the bound before implementation. The binary32 analogue is covered too.

For exact N, let h be its leading-bit index. Its leading exponent is E_B-p+h.
If h>p, retain N>>(h-p), compare the exact low remainder against half, and round
on retained parity. The cut is at most 54, so all discarded bits lie in the low
limb and every mask/complementary shift is defined. If h<=p, left alignment is
exact. A rounded carry renormalizes before exponent classification.

A rounded exponent beyond maximum yields infinity and OF/IX, including exact
unrepresentable sums. An exact value slightly above maximum finite can instead
round back to maximum with IX only. The nearest overflow midpoint is
2^1024-2^970 for binary64 and 2^128-2^103 for binary32; both sides and the tie
are explicit fixtures. For subnormal output, the lattice proof makes all
otherwise-discarded bits zero, and the final exact right shift is at most p.

All classification, ordering, normalization and packing use integers. An
explicit arithmetic witness raises only the needed standard exceptions;
there is no subtraction of floating inputs, subnormal arithmetic or signaling
input widening. Bit-count intrinsics have an actual width/nonzero guard and a
forced-loop configuration.

## Verification and provenance

Implementation was derived from the mathematical argument above, the primary
C specification and own-project code. No other math implementation source was
read or copied. Exact Fraction output construction and independently decoded
MPFR 4.2.2/gmpy2 2.3.2 target-precision subtraction agree. Exception classes
come from the explicit contract, not MPFR instrumentation. Mathematical and
context-free blind reviews were followed by fixes and review follow-up; no
numerical kernel change was needed after the final source freeze.

Five complete-file SHA256 gates and LF checkout attributes protect references.
Pinned regeneration is byte-identical. Committed raw data contains 105,206
Double and 18,958 Float pairs; only 526 signaling-input Float pairs are excluded
from generic widening. Generic result sets are `fdim 4ff6f2935654a000 / 105206`
and `fdimf 60205999f715c947 / 18432`. All 86 sets and legacy
`f5fa269eb60ee34f / 292711` pass. Raw result/flag-class digests are
`eada26cf51e49e4d` and `915bea242449eb94`; ordered digests are
`4d4d5116e3b61365` and `2e3f473749a9f00d`.

Each raw profile checks 124,164 nearest observations and 1,900,248 selected
all-mode/caller-state calls, 2,024,412 calls total. Results, actual flags, errno,
mode and promised controls are checked inline; ordered digests also bind mode,
requested incoming subset and errno seed. Requested subsets can merge on real
hardware. Seven focused unit tests add 9,728 literal calls to that corpus scope.
Valid tiny differences, predecessor midpoint seams, both signaling operands,
rounded finite maximum and overflow are explicit fixtures.

Sequential GCC14.2/GCC16.2 full `make test` runs return zero. Each main sequence
invokes 250 tests in 35 binaries: 249 pass and one pre-existing native32-only
unit skips on LP64. Clang passes the same unit-only sequence, not all Clang
gates. Seven focused ASan/UBSan tests pass; forced-loop targeted gates and units
pass. All 29 frozen implementation/reference/control file digests stay unchanged.
Six emulated targets agree on 86 numerical sets in default/portable builds and
24 raw O0/O2/default/forced-loop profiles. Twelve standalone clients link and
run without libm. The i686 O0 caller constructs raw arguments without fldl/flds
loads. A separate no-SSE reader fixture verifies x87 control snapshots only;
it is not a numerical x87-only ABI claim. These are emulated probes, not
physical-host/full cross-target GoogleTest runs.

Three newly generated independent fresh populations and a larger sample pass
complete metadata/population/target/widening/path selection, raw-state probes,
unit selection and all-86-set numeric overlays on both native compilers.
The larger sample has 159,206 Double and 72,958 Float raw pairs, 232,164 nearest
observations and 3,012,000 state calls per compiler. Its raw digests are
`c9e997fac2f452b9` / `0dcd6043c474ae8c`, ordered digests
`89dc5e6b7d612ee5` / `e29317e4d225973d`. No larger cross-target run is claimed.

Source/state defects detect in C17/C++ with intrinsic and loop configurations.
Double-only high-word carry/borrow defects retain passing Float controls:
Float's exact alignment fits 49 bits, so those variants are equivalent there.
Deleting the actual IX-generating arithmetic leaves integer result bits intact
and loses IX; this family's force-only witness is verified. Earlier expf,
exp2f, atanf and cbrtf force-only witness gaps remain unverified.
Six actual supplemental hash/count/omission corruptions detect. A real former-
family environment-variable typo falls back to an equally sized committed
population and is rejected by the fresh unit path/metadata check.
Loader/schema/value/SHA/process faults, real restoration failures, wrapper
omissions and actual independent-oracle faults are calibrated at their intended
failure layers. Recording engines and cached-positive parser controls are
accounting evidence, not numerical oracle evidence. The five-file publisher
rolls back ordinary exceptions; it is not crash-atomic.

Initial controller and mutation-compilation failures were corrected before
acceptance, with failed logs retained. These include an equivalent Float
high-word plant, a misspelled checker path, strict benchmark compile errors and
a cross-controller expected-output suffix omission. The last failure occurred
after correct i686 raw hashes: the corrected controller includes complete
seed/count/fresh metadata and the final complete cross run passes.

Valgrind 3.24 invokes all seven focused tests and exits 1: two pass and five
fail fenv assertions. The corpus probes stop at the first signaling-NaN invalid
mismatch; result bits agree while the instrumenter omits flags. It reports zero
memory errors/leaks, but early stops mean partial memory coverage. Independent
no-gmath reproductions from preceding phases establish missing IV/IX/UF
instrumentation for those operations; attributing every discrepancy to that
model remains inference. This is a failed scope, never a passing Valgrind suite.
No assertion was weakened.

Windows/LLP64, Darwin, RISC-V, numerical soft-float, physical cross-target hosts,
exhaustive input/environment space and application timing remain unrun.

## Paired performance baseline

Two predeclared runs per native compiler retain all 160 case records in
[positive-difference-timings.json](positive-difference-timings.json). The required
Make runner independently certifies all 81,920 emitted input/target/flag rows
before timing, records binary/archive/compiler/declared arguments and runtime
loader/libm context privately, and refuses to overwrite evidence. These are
caller-declared build identities, not arbitrary source authentication.

Eight paired warmups precede 401 alternating same-input pairs of 4,096 values.
Timing uses integer timestamps, real checked checksums and untimed per-input
value/class/state/errno/control guards. The ten named ranges independently
certify their semantics, including actual tie neighbors and both signs of
cancellation. Host NaN payloads, errno and extra flags may differ. All timing is
nearest-only. Logical affinity does not establish CPU isolation or governor
control; call/loop/checksum/timestamp overhead and amortized first-exception
costs are included. No overall, application or platform speed win is claimed.
Ordinary own/host medians are 3.397–3.479 Double / 2.816–2.843 Float on GCC14,
and 2.741–2.783 / 2.845–2.876 on GCC16: ordinary cases remain slower.

Reproduce with the command below, using a fresh evidence directory and building
and running separately for each compiler.

```sh
make bench-positive-difference POSITIVE_DIFFERENCE_BENCH_RUNS=2 \
  POSITIVE_DIFFERENCE_BENCH_OUT=build/fdim-timing
```
The table gives the range across the two retained runs for absolute median
ns/call and each paired quantile. Ratio is gmath/host; below one is faster.

| Compiler | API | Range | Entry | Own ns | Host ns | Ratio p10 | Ratio median | Ratio p90 |
|---|---|---|---|---:|---:|---:|---:|---:|
| gcc14 | fdim | cancellation | UF/IX | 16.346–16.411 | 3.336–3.368 | 4.806–4.811 | 4.880–4.895 | 4.944–4.951 |
| gcc14 | fdim | cancellation | clean | 16.411–16.446 | 3.340–3.359 | 4.841–4.851 | 4.889–4.909 | 4.931–4.976 |
| gcc14 | fdim | far-gap | UF/IX | 20.092–20.474 | 3.261–3.352 | 6.032–6.087 | 6.110–6.151 | 6.198–6.229 |
| gcc14 | fdim | far-gap | clean | 20.581–21.042 | 3.331–3.356 | 6.063–6.259 | 6.127–6.346 | 6.372–6.517 |
| gcc14 | fdim | infinity | UF/IX | 8.960–9.033 | 3.282–3.305 | 2.581–2.588 | 2.723–2.729 | 2.767–2.780 |
| gcc14 | fdim | infinity | clean | 9.065–9.066 | 3.293–3.364 | 2.550–2.579 | 2.725–2.740 | 2.783–2.785 |
| gcc14 | fdim | ordered-zero | UF/IX | 8.419–8.473 | 3.347–3.349 | 2.450–2.467 | 2.519–2.535 | 2.549–2.550 |
| gcc14 | fdim | ordered-zero | clean | 7.264–8.443 | 2.881–3.355 | 2.419–2.456 | 2.498–2.523 | 2.540–2.719 |
| gcc14 | fdim | ordinary | UF/IX | 18.577–18.584 | 5.447–5.491 | 3.304–3.330 | 3.397–3.404 | 3.485–3.503 |
| gcc14 | fdim | ordinary | clean | 18.451–19.017 | 5.370–5.424 | 3.369–3.376 | 3.430–3.479 | 3.509–3.572 |
| gcc14 | fdim | overflow | UF/IX | 19.461–19.582 | 3.184–3.209 | 6.021–6.028 | 6.091–6.093 | 6.173–6.177 |
| gcc14 | fdim | overflow | clean | 19.267–19.651 | 3.161–3.217 | 6.004–6.029 | 6.098–6.102 | 6.183–6.216 |
| gcc14 | fdim | qNaN | UF/IX | 9.698–10.023 | 3.314–3.376 | 2.680–2.706 | 2.935–2.971 | 3.022–3.042 |
| gcc14 | fdim | qNaN | clean | 9.629–9.749 | 3.298–3.353 | 2.668–2.718 | 2.861–2.963 | 2.992–3.028 |
| gcc14 | fdim | sNaN | UF/IX | 8.158–8.388 | 3.349–3.410 | 2.417–2.419 | 2.436–2.440 | 2.453–2.483 |
| gcc14 | fdim | sNaN | clean | 8.193–8.389 | 3.359–3.411 | 2.415–2.423 | 2.437–2.444 | 2.456–2.482 |
| gcc14 | fdim | subnormal | UF/IX | 22.424–22.432 | 4.439–4.468 | 4.950–4.978 | 5.020–5.053 | 5.122–5.216 |
| gcc14 | fdim | subnormal | clean | 21.845–22.600 | 4.397–4.476 | 4.900–4.972 | 4.982–5.039 | 5.129–5.184 |
| gcc14 | fdim | tie-neighbors | UF/IX | 18.516–18.572 | 3.348–3.354 | 5.464–5.481 | 5.532–5.533 | 5.578–5.615 |
| gcc14 | fdim | tie-neighbors | clean | 18.471–18.522 | 3.348–3.356 | 5.412–5.441 | 5.520–5.525 | 5.562–5.611 |
| gcc14 | fdimf | cancellation | UF/IX | 16.407–16.644 | 3.811–3.899 | 4.200–4.204 | 4.263–4.274 | 4.868–4.989 |
| gcc14 | fdimf | cancellation | clean | 16.440–16.636 | 3.809–3.898 | 4.175–4.213 | 4.269–4.272 | 4.862–4.956 |
| gcc14 | fdimf | far-gap | UF/IX | 21.318–21.437 | 3.898–3.916 | 5.388 | 5.461–5.465 | 5.565–5.615 |
| gcc14 | fdimf | far-gap | clean | 21.061–21.641 | 3.789–3.838 | 5.434–5.516 | 5.533–5.580 | 6.250–6.298 |
| gcc14 | fdimf | infinity | UF/IX | 8.661–8.760 | 3.735–3.790 | 2.219–2.269 | 2.325–2.332 | 2.379–2.390 |
| gcc14 | fdimf | infinity | clean | 8.766–8.855 | 3.789–3.797 | 2.234–2.312 | 2.311–2.337 | 2.359–2.364 |
| gcc14 | fdimf | ordered-zero | UF/IX | 8.299–8.315 | 3.351–3.367 | 2.443–2.446 | 2.471 | 2.561–2.864 |
| gcc14 | fdimf | ordered-zero | clean | 8.267–8.441 | 3.349–3.380 | 2.438–2.441 | 2.470–2.472 | 2.592–2.666 |
| gcc14 | fdimf | ordinary | UF/IX | 19.965–20.118 | 7.077–7.093 | 2.740–2.761 | 2.816–2.836 | 2.899–2.928 |
| gcc14 | fdimf | ordinary | clean | 19.381–19.729 | 6.736–6.954 | 2.755–2.758 | 2.831–2.843 | 2.921–3.041 |
| gcc14 | fdimf | overflow | UF/IX | 19.728–19.807 | 3.583–3.915 | 4.979–5.460 | 5.035–5.519 | 5.098–5.574 |
| gcc14 | fdimf | overflow | clean | 19.731–19.914 | 3.608–3.926 | 4.948–5.452 | 5.021–5.530 | 5.091–5.582 |
| gcc14 | fdimf | qNaN | UF/IX | 9.531–9.553 | 3.894–3.896 | 2.150–2.192 | 2.459–2.470 | 2.847–2.890 |
| gcc14 | fdimf | qNaN | clean | 9.314–9.533 | 3.871–3.901 | 2.122–2.144 | 2.443–2.450 | 2.585–2.846 |
| gcc14 | fdimf | sNaN | UF/IX | 8.416–8.519 | 3.899–4.007 | 2.106–2.112 | 2.126–2.147 | 2.447–2.505 |
| gcc14 | fdimf | sNaN | clean | 8.478–8.534 | 3.893–3.909 | 2.113–2.114 | 2.133–2.159 | 2.462–2.481 |
| gcc14 | fdimf | subnormal | UF/IX | 22.337–23.160 | 4.774–4.939 | 4.586–4.599 | 4.666–4.696 | 4.792–4.800 |
| gcc14 | fdimf | subnormal | clean | 22.545–23.235 | 4.763–4.896 | 4.605–4.649 | 4.720–4.747 | 4.835–4.867 |
| gcc14 | fdimf | tie-neighbors | UF/IX | 18.736–19.270 | 3.900–4.010 | 4.748–4.768 | 4.801–4.810 | 4.845–4.856 |
| gcc14 | fdimf | tie-neighbors | clean | 18.364–18.738 | 3.685–3.789 | 4.767–4.784 | 4.829–4.830 | 5.577–7.546 |
| gcc16 | fdim | cancellation | UF/IX | 17.270–17.283 | 3.820–3.823 | 4.482–4.483 | 4.519–4.524 | 4.691–4.848 |
| gcc16 | fdim | cancellation | clean | 17.310–17.693 | 3.824–3.919 | 4.459–4.487 | 4.523–4.526 | 4.571–4.658 |
| gcc16 | fdim | far-gap | UF/IX | 20.492–20.628 | 3.823–3.827 | 5.300–5.345 | 5.347–5.394 | 5.469–5.485 |
| gcc16 | fdim | far-gap | clean | 20.763–21.145 | 3.821 | 5.317–5.453 | 5.472–5.546 | 5.756–5.764 |
| gcc16 | fdim | infinity | UF/IX | 9.060–9.092 | 3.812–3.840 | 2.161–2.287 | 2.364–2.374 | 2.713–2.724 |
| gcc16 | fdim | infinity | clean | 9.064–9.284 | 3.831–3.832 | 2.169–2.285 | 2.372–2.385 | 2.689–2.737 |
| gcc16 | fdim | ordered-zero | UF/IX | 8.762–8.783 | 3.819–3.828 | 2.177–2.256 | 2.283–2.298 | 2.308–2.318 |
| gcc16 | fdim | ordered-zero | clean | 8.195–8.765 | 3.533–3.815 | 2.152–2.243 | 2.298–2.301 | 2.312–10.125 |
| gcc16 | fdim | ordinary | UF/IX | 19.225–19.384 | 6.987–7.032 | 2.650–2.664 | 2.741–2.755 | 2.817–2.848 |
| gcc16 | fdim | ordinary | clean | 19.474–19.488 | 6.988–7.021 | 2.684–2.686 | 2.777–2.783 | 2.855–2.868 |
| gcc16 | fdim | overflow | UF/IX | 19.744–19.873 | 3.675–3.685 | 4.903–5.024 | 5.395–5.464 | 5.553–5.579 |
| gcc16 | fdim | overflow | clean | 19.824–19.838 | 3.665–3.679 | 4.928–5.153 | 5.441–5.450 | 5.579–5.586 |
| gcc16 | fdim | qNaN | UF/IX | 9.440–9.485 | 3.813–3.825 | 2.083–2.433 | 2.467–2.484 | 2.535–2.747 |
| gcc16 | fdim | qNaN | clean | 9.475–9.497 | 3.819–3.823 | 2.054–2.313 | 2.475–2.486 | 2.500–2.672 |
| gcc16 | fdim | sNaN | UF/IX | 7.111–7.934 | 3.443–3.850 | 2.037–2.044 | 2.061–2.063 | 2.086–2.322 |
| gcc16 | fdim | sNaN | clean | 7.874–7.885 | 3.821–3.828 | 2.037–2.039 | 2.062 | 2.079–2.279 |
| gcc16 | fdim | subnormal | UF/IX | 22.009–22.033 | 4.991–5.030 | 4.122–4.198 | 4.373–4.407 | 4.502–4.534 |
| gcc16 | fdim | subnormal | clean | 22.391–22.470 | 4.973–5.079 | 4.181–4.285 | 4.438–4.491 | 4.562–4.603 |
| gcc16 | fdim | tie-neighbors | UF/IX | 18.813–18.911 | 3.824–3.827 | 4.847–4.876 | 4.921–4.928 | 4.967–5.052 |
| gcc16 | fdim | tie-neighbors | clean | 18.890–18.908 | 3.828–3.831 | 4.885–4.894 | 4.930–4.933 | 5.105–5.143 |
| gcc16 | fdimf | cancellation | UF/IX | 17.287–17.297 | 4.237–4.353 | 3.937–3.955 | 3.978–4.054 | 4.390–4.533 |
| gcc16 | fdimf | cancellation | clean | 17.274–17.321 | 4.350 | 3.934–3.952 | 3.979–3.985 | 4.490–4.513 |
| gcc16 | fdimf | far-gap | UF/IX | 21.303–21.699 | 4.335–4.364 | 4.853–4.902 | 4.902–4.963 | 5.145–5.318 |
| gcc16 | fdimf | far-gap | clean | 20.946–22.167 | 4.239–4.381 | 4.867–4.936 | 4.921–4.996 | 5.484–5.502 |
| gcc16 | fdimf | infinity | UF/IX | 8.572–8.771 | 4.259–4.518 | 1.889–1.899 | 1.944–1.995 | 1.983–2.039 |
| gcc16 | fdimf | infinity | clean | 8.552–8.797 | 4.250–4.373 | 1.895–1.953 | 1.992–2.012 | 2.043–2.045 |
| gcc16 | fdimf | ordered-zero | UF/IX | 8.297–8.314 | 3.823–3.825 | 2.150–2.160 | 2.170–2.173 | 2.265–2.267 |
| gcc16 | fdimf | ordered-zero | clean | 8.289–8.296 | 3.822–3.824 | 2.153–2.155 | 2.169 | 2.182–2.206 |
| gcc16 | fdimf | ordinary | UF/IX | 19.118–19.281 | 6.710–6.740 | 2.771–2.789 | 2.845–2.868 | 2.953–2.971 |
| gcc16 | fdimf | ordinary | clean | 19.280–19.349 | 6.710–6.739 | 2.798–2.802 | 2.855–2.876 | 2.959–2.968 |
| gcc16 | fdimf | overflow | UF/IX | 19.994–20.468 | 4.373–4.469 | 4.510–4.537 | 4.579–4.580 | 4.617–4.636 |
| gcc16 | fdimf | overflow | clean | 19.955–20.497 | 4.354–4.471 | 4.520–4.535 | 4.586–4.588 | 4.627–4.628 |
| gcc16 | fdimf | qNaN | UF/IX | 9.228–9.404 | 4.348–4.479 | 2.040–2.082 | 2.100–2.124 | 2.390–2.416 |
| gcc16 | fdimf | qNaN | clean | 9.198–9.483 | 4.353–4.490 | 1.812–1.813 | 2.100–2.115 | 2.184–2.329 |
| gcc16 | fdimf | sNaN | UF/IX | 7.911–8.329 | 4.350–4.486 | 1.802–1.804 | 1.815–1.820 | 2.029–2.077 |
| gcc16 | fdimf | sNaN | clean | 7.912–8.298 | 4.352–4.369 | 1.797–1.805 | 1.816–1.875 | 2.051–2.062 |
| gcc16 | fdimf | subnormal | UF/IX | 21.953–22.591 | 5.533–5.781 | 3.776–3.803 | 3.879–4.006 | 4.096–4.114 |
| gcc16 | fdimf | subnormal | clean | 22.003–22.712 | 5.520–5.749 | 3.784–3.806 | 3.932–3.991 | 4.113–4.134 |
| gcc16 | fdimf | tie-neighbors | UF/IX | 19.080–19.632 | 4.337–4.475 | 4.321–4.366 | 4.384–4.397 | 4.417–4.671 |
| gcc16 | fdimf | tie-neighbors | clean | 18.376–19.706 | 4.016–4.458 | 4.361–4.374 | 4.406–4.416 | 4.970–28.888 |
