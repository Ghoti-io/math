# Rejected wide Double remainder experiment

The common-factor prototype is **not admitted**. It preserves every checked
numerical/state result and makes the measured Double wide-gap range about 4.4 times
faster, but fails the predeclared ordinary-call admission ceiling of 1.05 times
the prior median. Nine of 144 ordinary observations exceed the ceiling; the worst
is 1.086. Selected special cases also regress, up to 1.477 times prior. All runtime,
public headers, tests, tools and Makefile have been restored to the verified
`860e771e93a8c75c03514ba34cbf92afdac1364d` implementation. This investigation adds
no API, shipped optimization or shipped test coverage. No timing retries were
used to replace the final predeclared runs.

## Candidate and integer argument

The candidate kept the ordinary core and Float strategy unchanged, dispatching
Double magnitudes by `ax >= ay + (512 << 52)` to a source-coupled cold copy.
Magnitudes are below 2^63, so adding 2^61 cannot wrap uint64_t. For finite inputs,
the test implies a normalized exponent gap of at least 512; normalizing a subnormal
divisor only increases the gap. A subnormal dividend cannot qualify. Qualifying
nonfinite/domain inputs execute an identical copied special prefix.

For nonzero residual and normalized divisor with at least 16 trailing zero bits,
let k=ctz(my),16<=k<=52. Advance exactly k quotient positions with the old divisor
in chunks of at most 11. Since r<my<2^53, each shifted intermediate fits uint64_t.
Early zero retains the old final advancement of all remaining quotient zeros.
Otherwise write my=d*2^k with odd d. Euclidean uniqueness gives
`(r_old*2^k) mod (d*2^k) = (r_old mod d)*2^k`, so residual and divisor divide
exactly by 2^k. Increasing the unit exponent e by k preserves the physical residual.
A surviving nonzero residual implies d>1; k = 52 cannot survive.

The reduced divisor's top bit is p-k, allowing subsequent chunks of
`63-(p-k)=11+k`, at most 62 in a surviving state. The unsigned shifted residual
fits 64 bits. Quotient digits are below2^s; unsigned quotient shifts preserve all
needed low-seven bits because 128 divides 2^64, and the following digit fits the s
vacant low bits. Packing normalization has at least k positions; the original
input dyadic lattice ensures every discarded subnormal encoding bit is zero.
These arguments and independent exact targets supported correctness, not speed.

Several private layouts were rejected before final measurement. A shared inline
version and a completion helper regressed ordinary paths. The selected cold copy
passed exploratory admission runs, but its final complete experiment failed the
same gate. Its GCC14 GNU size text tally also grew from 1,199 to 2,079 bytes. Float
source equality did not establish unchanged performance.

## Candidate validation, before restoration

The candidate's final GCC14.2 and GCC16.2 default `make test` commands return zero
with actual child-status records: 234 main tests/32 binaries each. Clang passes
those counts unit-only, and ten focused ASan/UBSan tests pass. The first GCC14 full
attempt failed after a reviewed generator portability repair changed the fixture
header after its C probe was built. A complete frozen-tree rerun passed; the failed
attempt is not counted as successful.

The experimental header contained 10,500 positive exact-rational fixtures. Four
signs, four modes, three API paths and two errno seeds used three incoming-flag
subsets on every row and all 32 requested subsets on six representatives:
3,040,704 logical observations. Current/prior invocation observers each required
that count. Ordered result hash 646fe71591a68d99 pinned results/order; actual
flags/errno/mode were asserted separately. Requested flags can merge on a target.
Pinned MPFR independently agreed with 41,888 signed finite/infinite-divisor targets
and full low-seven quotient fragments. Serialized coverage included every surviving
factor width 16..51, power-of-two early zero, normal residuals, divisor exponents
0/400/511, interior odd divisors and rejection/boundary strata. Literal certificates,
source-linked equivalence/bounds, omission controls and actual source/state plants
supplied separate evidence. These experimental tests are not shipped as new gates.

All 78 prior numerical sets and legacy f5fa269eb60ee34f/292711 remained unchanged.
Raw hashes remained de2cafdcc5da3465/d982af8aeb4c9bfb, selected ordered hashes
84af9b980627e8f5/9f841414af40b535. Six emulated targets agreed on all 78 sets in
12 default/portable numerical configurations. Twenty-four O0/O2 default/forced-loop
raw profiles agreed with actual prior hooks: 4,248,804 logical observations and
8,497,608 physical calls per complete paired profile, including the new focus.
SPARC required 600-second host accounting with the unchanged expected protocol;
its first default 120-second controller invocation timed out and remains failed.
An initial whole-binary x87 search found allowed callee return loads; the separately
compiled actual-context i686 O0 caller had zero fldl/flds argument loads.

Three retained fresh corpora and larger 149,316/80,008-pair independent data passed
both native comparisons. The larger paired profile included 5,070,348 logical /
10,140,696 physical calls; no larger cross-target run was added. These are sampled
and emulated probes, not exhaustive pair/environment, physical-host or full cross-
target GoogleTest claims. Independent mathematical and blind reviews resolved all
findings and reconciled the retained evidence; they did not rerun every heavy gate.

Valgrind was not rerun. Its earlier eight-test scope remains failed (five passing,
three fenv failures), with zero reported memory errors but partial coverage from
early stops. Existing independent invalid/UF/IX instrumentation limitations remain
recorded. No expanded/passing Memcheck claim is made, and assertions were not
weakened. Earlier expf/exp2f/atanf/cbrtf narrow force-only IX-deletion witnesses
remain unverified; production forces stay. Windows and application timing are unrun.

The final restored-kernel GCC14 default `make test` also returns zero, with 233
main tests in 32 binaries. This validates the actual documentation-only tree;
the experimental 234th test is absent. No current GCC16/Clang/ASan rerun of the
restored kernel is claimed here; their candidate evidence is described above,
and the previously verified runtime validation remains in the progress record.

## Timing method and rejection

Two predeclared runs per native compiler/comparison give 1,248 records. Each run
covers 13 ranges, six API paths and clean/UF-IX entry states, with eight paired
warmups and 401 alternating pairs of 4,096 identical values. Integer timestamps,
untimed exact prior bits/full quotient and individually seeded state guards precede
batch timing. Each prior run checks 638,976 logical per-input state observations
before timing. The old eight Float input streams were preserved despite appending
Double ranges. Extra ranges cover odd/no-factor, exact-power early zero, selector
boundary, k15 rejection and k51 large chunks.

The references are separately compiled own-project public functions from 860e771,
with identical library compiler arguments and only four public symbols renamed.
Metadata binds declared revision, object, compiler-driver invocation and arguments,
not arbitrary source authenticity. Historical a54 baseline defaults remain unchanged
in the restored tools. Host NULL comparisons use host remainder, never remquo(NULL).
Host remquo checks only guaranteed low-three quotient bits; own seven bits have
independent exact certificates. Host NaN payload/exceptional errno can differ.

Final ordinary median ratios span 0.964–1.086. GCC14's maximum 1.086 is NULL-output
remquo/quotient-wrap/clean run1; GCC16's 1.072 is remainder/quotient-wrap/UF-IX run2.
The measured Double wide-gap gain does not override the failed ordinary ceiling.
Worst special regression 1.477 is GCC14 NULL-output remquo/zero/clean run1. These
costs are not dismissed as noise. Fixed logical affinity gives no CPU-isolation or
governor-control claim. Call/loop/checksum/timing overhead and amortized initial
exception costs are included; compiler/runtime contexts and absolute times differ.
No net, application, general nonregression or platform win is claimed.

## Experimental source and reproduction

The archived [runtime patch](experiments/ieee-remainder-wide/runtime.patch),
[13-range benchmark](experiments/ieee-remainder-wide/bench-ieee-remainder.c) and
[selected-revision builder](experiments/ieee-remainder-wide/build-baseline.py) are
experimental documentation artifacts, excluded from the library build. Use a
scratch Git checkout of our 860e771 revision, never an active consumer checkout. Apply the
patch there with `patch -p1`, place the archived benchmark at
`tools/bench-ieee-remainder.c`, and build with the chosen compiler's ordinary
library flags. Run the archived builder with `PYTHONPATH=tools` and
`--revision 860e771e93a8c75c03514ba34cbf92afdac1364d`; pass exactly the same compiler
and library arguments. It extracts only our own prior module/helper and renames
its four public symbols. Generate the prior identity header using
`tools/adjacent_baseline.py --family ieee_remainder --expected-revision` with that
revision/object/context, then link the benchmark with
`-DGMATH_IEEE_REMAINDER_PRIOR -include identity.h`, candidate archive and prior
object. Without the macro/object, it compares host libm. `--validate-only` runs
input guards without timing. The restored Make optional targets retain their
historical a54 pin, so they must not silently stand in for this 860 experiment.

Native contexts used C17/O2, strict aliasing, no FP contraction, no math errno,
PIC and hidden library visibility; exact compiler/runtime/object/source identities
and full experimental fixture/control evidence are retained locally. No other
libm implementation source was read or copied. Standard positional division is
not claimed novel.

## Full measured envelopes

The following tables retain every range/path. Cells span two runs and both entry
states; ns columns are amortized median ns/call. Ratio columns span each run's
paired p10/median/p90. They describe the rejected candidate, not the restored kernel.

### GCC14 / actual-prior

Each cell spans two runs and both entry states (four observations).

| API / range | Own ns/call | Reference ns/call | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 10.944–11.452 | 10.392–10.987 | 0.971–1.032 | 1.035–1.056 | 1.070–1.126 |
| remquo / normal | 11.236–12.066 | 10.931–11.664 | 0.982–1.013 | 1.020–1.031 | 1.098–1.121 |
| remquo_null / normal | 11.361–11.927 | 11.196–11.384 | 0.953–1.014 | 1.001–1.031 | 1.027–1.127 |
| remainder / half-ties | 6.779–7.249 | 6.436–6.713 | 0.940–1.024 | 1.025–1.046 | 1.029–1.198 |
| remquo / half-ties | 6.929–7.242 | 6.715–6.882 | 0.932–1.028 | 1.030–1.031 | 1.034–1.203 |
| remquo_null / half-ties | 6.592–6.881 | 6.369–6.641 | 0.935–1.032 | 1.033–1.036 | 1.038–1.178 |
| remainder / quotient-wrap | 5.699–5.913 | 5.465–5.704 | 0.981–1.033 | 1.032–1.054 | 1.068–1.283 |
| remquo / quotient-wrap | 5.859–5.965 | 5.526–5.652 | 1.014–1.029 | 1.037–1.041 | 1.187–1.256 |
| remquo_null / quotient-wrap | 5.536–5.898 | 5.193–5.566 | 1.004–1.029 | 1.030–1.086 | 1.072–1.251 |
| remainder / subnormal | 18.823–19.456 | 18.848–19.293 | 0.976–0.993 | 0.995–1.010 | 1.018–1.033 |
| remquo / subnormal | 18.966–19.242 | 18.667–18.929 | 0.999–1.006 | 1.008–1.021 | 1.019–1.037 |
| remquo_null / subnormal | 18.703–19.526 | 18.674–19.600 | 0.977–0.983 | 0.996–1.002 | 1.010–1.018 |
| remainder / wide-gap | 154.948–156.350 | 678.053–679.468 | 0.225–0.228 | 0.228–0.229 | 0.230–0.234 |
| remquo / wide-gap | 153.874–154.636 | 677.831–678.015 | 0.226–0.227 | 0.227–0.228 | 0.229–0.232 |
| remquo_null / wide-gap | 154.205–154.783 | 677.888–678.055 | 0.227–0.228 | 0.227–0.228 | 0.229 |
| remainder / zero | 3.208–3.533 | 2.780–3.184 | 1.001–1.151 | 1.072–1.157 | 1.144–1.615 |
| remquo / zero | 3.012–4.052 | 2.755–2.774 | 0.963–1.091 | 1.092–1.457 | 1.538–1.618 |
| remquo_null / zero | 3.127–4.268 | 2.899–2.962 | 0.824–1.076 | 1.078–1.477 | 1.156–1.617 |
| remainder / infinite-divisor | 3.420–3.818 | 3.051–3.340 | 1.069–1.071 | 1.140–1.212 | 1.153–1.569 |
| remquo / infinite-divisor | 3.123–4.454 | 2.896–2.903 | 1.071–1.150 | 1.079–1.156 | 1.157–1.541 |
| remquo_null / infinite-divisor | 3.342–3.489 | 2.901–3.122 | 0.844–1.080 | 1.073–1.153 | 1.151–1.534 |
| remainder / NaN-domain | 3.576–4.034 | 3.121–3.615 | 0.894–1.171 | 1.100–1.250 | 1.201–1.375 |
| remquo / NaN-domain | 3.125–3.290 | 2.867–3.020 | 0.997–1.092 | 1.054–1.112 | 1.116–1.233 |
| remquo_null / NaN-domain | 3.580–3.823 | 2.958–3.275 | 1.097–1.214 | 1.101–1.253 | 1.133–1.265 |
| remainder / wide-odd | 654.698–654.727 | 663.369–663.391 | 0.986 | 0.987 | 0.988 |
| remquo / wide-odd | 655.659–655.712 | 663.189–663.276 | 0.987–0.988 | 0.989 | 0.990 |
| remquo_null / wide-odd | 654.606–654.670 | 663.259–663.282 | 0.986 | 0.987 | 0.988 |
| remainder / wide-power2 | 12.794–12.833 | 11.993–12.008 | 1.060–1.066 | 1.068–1.069 | 1.071–1.073 |
| remquo / wide-power2 | 14.380–14.451 | 12.153–12.165 | 1.166–1.179 | 1.183–1.185 | 1.188–1.192 |
| remquo_null / wide-power2 | 12.707–12.752 | 11.998–12.021 | 1.057–1.058 | 1.060–1.061 | 1.063–1.065 |
| remainder / admission-boundary | 71.942–72.140 | 101.876–102.166 | 0.685–0.704 | 0.706 | 0.709–0.726 |
| remquo / admission-boundary | 72.777–72.957 | 102.082–102.347 | 0.697–0.699 | 0.713 | 0.728–0.732 |
| remquo_null / admission-boundary | 71.943–71.966 | 101.844–102.125 | 0.686–0.695 | 0.706 | 0.718–0.726 |
| remainder / low-factor | 654.609–654.667 | 663.280–663.349 | 0.986 | 0.987 | 0.988 |
| remquo / low-factor | 655.683–655.726 | 663.131–663.240 | 0.985–0.988 | 0.989 | 0.990–0.997 |
| remquo_null / low-factor | 654.606–654.679 | 663.205–663.270 | 0.986 | 0.987 | 0.988 |
| remainder / high-factor | 98.429–98.511 | 450.524–450.753 | 0.218 | 0.218–0.219 | 0.219 |
| remquo / high-factor | 99.703–99.924 | 450.234–450.585 | 0.221 | 0.221–0.222 | 0.222–0.223 |
| remquo_null / high-factor | 98.254–98.294 | 450.458–450.612 | 0.217 | 0.218 | 0.219 |
| remainderf / normal | 11.343–11.488 | 11.320–11.951 | 0.902–0.987 | 0.964–1.009 | 0.986–1.038 |
| remquof / normal | 11.400–11.428 | 11.450–11.566 | 0.920–0.986 | 0.988–1.000 | 1.004–1.068 |
| remquof_null / normal | 11.274–11.529 | 11.468–11.566 | 0.931–0.981 | 0.979–1.001 | 0.997–1.051 |
| remainderf / half-ties | 6.559–6.698 | 6.557–6.702 | 0.856–0.999 | 0.999–1.001 | 1.001–1.003 |
| remquof / half-ties | 6.716–6.851 | 6.715–6.850 | 0.997–0.998 | 1.000 | 1.003–1.107 |
| remquof_null / half-ties | 6.495–6.640 | 6.491–6.636 | 0.988–0.999 | 0.999–1.002 | 1.002–1.029 |
| remainderf / quotient-wrap | 5.569–5.717 | 5.515–5.652 | 0.857–0.994 | 1.000–1.001 | 1.019–1.048 |
| remquof / quotient-wrap | 5.636–5.741 | 5.645–5.742 | 0.988–0.991 | 0.998–1.002 | 1.009–1.110 |
| remquof_null / quotient-wrap | 5.500–5.616 | 5.508–5.612 | 0.952–0.995 | 0.999–1.004 | 1.005–1.247 |
| remainderf / subnormal | 11.761–11.812 | 11.581–11.807 | 0.981–1.004 | 0.998–1.016 | 1.021–1.039 |
| remquof / subnormal | 11.924–12.128 | 11.966–12.232 | 0.977–0.988 | 0.989–0.999 | 1.000–1.073 |
| remquof_null / subnormal | 11.650–11.765 | 11.776–11.951 | 0.965–0.983 | 0.977–1.003 | 0.989–1.015 |
| remainderf / wide-gap | 27.075–27.656 | 27.241–28.701 | 0.929–0.993 | 0.945–1.017 | 0.961–1.040 |
| remquof / wide-gap | 27.853–28.117 | 27.866–28.060 | 0.982–0.990 | 0.993–1.003 | 1.006–1.016 |
| remquof_null / wide-gap | 27.103–27.267 | 27.209–27.558 | 0.966–0.978 | 0.990–0.996 | 1.011–1.016 |
| remainderf / zero | 2.836–3.187 | 2.906–3.352 | 0.927–0.930 | 0.930–0.998 | 0.997–1.003 |
| remquof / zero | 2.811–2.884 | 2.815–2.886 | 0.685–0.952 | 0.999–1.002 | 1.002–1.378 |
| remquof_null / zero | 2.902–2.970 | 2.903–2.967 | 0.997–0.998 | 1.000–1.002 | 1.003–1.079 |
| remainderf / infinite-divisor | 2.993–3.270 | 3.053–3.427 | 0.929–0.998 | 0.933–1.002 | 1.001–1.263 |
| remquof / infinite-divisor | 2.830–2.904 | 2.899–4.011 | 0.703–0.904 | 0.725–1.000 | 0.977–1.380 |
| remquof_null / infinite-divisor | 2.904–4.010 | 2.902–2.975 | 0.927–0.998 | 1.001–1.288 | 1.079–1.387 |
| remainderf / NaN-domain | 3.215–3.343 | 3.341–3.505 | 0.859–0.916 | 0.931–0.984 | 0.940–1.073 |
| remquof / NaN-domain | 2.928–2.995 | 2.934–3.029 | 0.967–0.993 | 0.990–1.007 | 1.002–1.031 |
| remquof_null / NaN-domain | 2.958–3.131 | 3.116–3.251 | 0.871–0.948 | 0.948–0.965 | 0.985–1.311 |
| remainderf / wide-odd | 26.903–27.158 | 26.930–27.067 | 0.980–0.986 | 0.998–1.003 | 1.015–1.017 |
| remquof / wide-odd | 27.419–27.530 | 27.427–27.655 | 0.982–0.989 | 0.992–1.002 | 1.003–1.015 |
| remquof_null / wide-odd | 26.611–26.986 | 26.865–26.993 | 0.969–0.982 | 0.986–1.002 | 1.005–1.027 |
| remainderf / wide-power2 | 5.898–6.027 | 5.896–6.158 | 0.845–0.999 | 1.000 | 1.001–1.005 |
| remquof / wide-power2 | 5.897–6.025 | 5.897–6.026 | 0.999 | 1.000 | 1.001 |
| remquof_null / wide-power2 | 5.688–5.808 | 5.690–5.809 | 0.965–0.998 | 0.999–1.000 | 1.001–1.003 |
| remainderf / admission-boundary | 6.229–6.364 | 6.226–6.364 | 0.904–0.999 | 1.000–1.001 | 1.003–1.085 |
| remquof / admission-boundary | 6.468–6.616 | 6.466–6.472 | 0.947–0.999 | 1.000–1.001 | 1.002–1.066 |
| remquof_null / admission-boundary | 6.229–6.232 | 6.228–6.233 | 0.953–0.999 | 1.000 | 1.001–1.003 |
| remainderf / low-factor | 26.712–26.903 | 26.859–27.045 | 0.967–0.973 | 0.990–0.996 | 1.010–1.018 |
| remquof / low-factor | 27.095–27.408 | 27.332–27.551 | 0.980–0.984 | 0.991–0.998 | 1.002–1.015 |
| remquof_null / low-factor | 26.505–26.730 | 26.618–26.716 | 0.973–0.982 | 0.993–1.001 | 1.013–1.022 |
| remainderf / high-factor | 22.383–22.582 | 22.331–22.550 | 0.981–0.993 | 0.999–1.011 | 1.012–1.025 |
| remquof / high-factor | 21.663–21.888 | 21.910–22.009 | 0.964–0.973 | 0.986–0.997 | 1.012–1.020 |
| remquof_null / high-factor | 22.578–22.735 | 22.585–22.683 | 0.979–0.988 | 0.999–1.005 | 1.017–1.031 |

### GCC14 / host

Each cell spans two runs and both entry states (four observations).

| API / range | Own ns/call | Reference ns/call | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 10.080–10.543 | 13.653–14.149 | 0.729–0.738 | 0.737–0.744 | 0.748–0.810 |
| remquo / normal | 10.896–11.393 | 18.008–18.448 | 0.569–0.600 | 0.596–0.625 | 0.663–0.681 |
| remquo_null / normal | 10.227–10.295 | 14.114–14.194 | 0.713–0.720 | 0.720–0.727 | 0.774–0.801 |
| remainder / half-ties | 6.323–6.430 | 25.824–26.025 | 0.238–0.243 | 0.244–0.247 | 0.247–0.286 |
| remquo / half-ties | 7.078–7.233 | 6.954–7.104 | 0.982–1.011 | 0.995–1.021 | 1.007–1.160 |
| remquo_null / half-ties | 6.316–6.349 | 25.591–25.826 | 0.239–0.244 | 0.245 | 0.255–0.278 |
| remainder / quotient-wrap | 5.695–5.837 | 6.828–7.191 | 0.795–0.808 | 0.810–0.833 | 0.835–0.986 |
| remquo / quotient-wrap | 5.952–6.583 | 6.842–7.086 | 0.820–0.863 | 0.842–0.964 | 0.853–1.034 |
| remquo_null / quotient-wrap | 5.654–5.698 | 6.975–7.039 | 0.787–0.789 | 0.810–0.831 | 0.815–0.927 |
| remainder / subnormal | 16.629–16.769 | 194.103–194.983 | 0.084–0.085 | 0.085–0.086 | 0.087–0.088 |
| remquo / subnormal | 18.510–19.132 | 72.832–75.345 | 0.246–0.248 | 0.253–0.256 | 0.263–0.265 |
| remquo_null / subnormal | 16.670–17.314 | 194.675–194.844 | 0.084–0.087 | 0.086–0.089 | 0.088–0.091 |
| remainder / wide-gap | 160.298–161.637 | 633.244–640.737 | 0.245–0.246 | 0.251–0.252 | 0.259 |
| remquo / wide-gap | 164.192–168.263 | 172.960–175.669 | 0.927–0.932 | 0.949–0.951 | 0.972–0.978 |
| remquo_null / wide-gap | 160.333–160.766 | 634.150–636.865 | 0.245–0.246 | 0.251–0.253 | 0.258–0.259 |
| remainder / zero | 2.893–3.008 | 19.715–19.759 | 0.141–0.142 | 0.150–0.152 | 0.153–0.193 |
| remquo / zero | 3.078–4.195 | 5.955–6.654 | 0.444–0.626 | 0.454–0.664 | 0.478–0.705 |
| remquo_null / zero | 2.807–2.814 | 19.729–19.746 | 0.140–0.142 | 0.142 | 0.143–0.189 |
| remainder / infinite-divisor | 3.011–3.018 | 19.802–19.823 | 0.148–0.152 | 0.152 | 0.160–0.178 |
| remquo / infinite-divisor | 3.190–3.265 | 4.590–4.839 | 0.650–0.680 | 0.673–0.693 | 0.682–0.942 |
| remquo_null / infinite-divisor | 2.817–3.008 | 19.783–19.810 | 0.142 | 0.142–0.152 | 0.152–0.213 |
| remainder / NaN-domain | 3.244–3.487 | 78.558–78.574 | 0.038–0.042 | 0.042–0.045 | 0.046–0.047 |
| remquo / NaN-domain | 3.000–3.725 | 2.056–2.438 | 1.392–1.505 | 1.458–1.556 | 1.526–1.729 |
| remquo_null / NaN-domain | 3.138–3.238 | 78.555–78.575 | 0.038–0.040 | 0.040–0.042 | 0.042–0.044 |
| remainder / wide-odd | 665.234–669.688 | 488.956–489.759 | 1.335–1.340 | 1.357–1.367 | 1.397–1.402 |
| remquo / wide-odd | 691.857–700.942 | 563.250–579.594 | 1.127–1.175 | 1.205–1.260 | 1.276–1.317 |
| remquo_null / wide-odd | 664.829–669.209 | 488.997–489.528 | 1.335–1.341 | 1.357–1.368 | 1.397–1.412 |
| remainder / wide-power2 | 11.772–11.791 | 84.815–84.943 | 0.136–0.137 | 0.139 | 0.140–0.141 |
| remquo / wide-power2 | 13.762–14.096 | 71.499–74.292 | 0.187–0.188 | 0.191–0.193 | 0.193–0.195 |
| remquo_null / wide-power2 | 11.714–11.939 | 84.629–86.262 | 0.135–0.137 | 0.138–0.139 | 0.139–0.143 |
| remainder / admission-boundary | 74.685–74.748 | 152.275–152.859 | 0.481–0.482 | 0.490–0.491 | 0.500–0.503 |
| remquo / admission-boundary | 75.568–75.831 | 37.428–37.569 | 1.979–1.985 | 2.021–2.023 | 2.039–2.051 |
| remquo_null / admission-boundary | 74.656–74.682 | 151.858–152.221 | 0.480–0.482 | 0.490–0.491 | 0.501–0.502 |
| remainder / low-factor | 665.750–669.965 | 486.760–487.609 | 1.342–1.348 | 1.363–1.374 | 1.402–1.413 |
| remquo / low-factor | 671.962–674.022 | 189.447–190.197 | 3.439–3.457 | 3.532–3.546 | 3.640–3.682 |
| remquo_null / low-factor | 665.101–670.135 | 486.771–487.237 | 1.344–1.348 | 1.364–1.375 | 1.404–1.418 |
| remainder / high-factor | 101.799–101.884 | 471.222–471.484 | 0.210–0.212 | 0.216 | 0.221–0.223 |
| remquo / high-factor | 104.412–105.006 | 67.056–67.326 | 1.520–1.528 | 1.553–1.554 | 1.581–1.586 |
| remquo_null / high-factor | 101.678–101.810 | 471.178–471.509 | 0.210–0.212 | 0.215–0.216 | 0.221–0.222 |
| remainderf / normal | 10.394–10.591 | 13.993–14.244 | 0.729–0.733 | 0.736–0.741 | 0.745–0.797 |
| remquof / normal | 11.079–11.230 | 16.906–18.803 | 0.583–0.624 | 0.601–0.654 | 0.642–0.683 |
| remquof_null / normal | 10.431–10.553 | 14.068–14.148 | 0.730–0.738 | 0.740–0.746 | 0.748–0.752 |
| remainderf / half-ties | 6.151–6.156 | 25.621–25.622 | 0.237–0.238 | 0.240 | 0.241 |
| remquof / half-ties | 6.845–7.016 | 6.916–7.037 | 0.962–0.991 | 0.974–0.996 | 0.980–1.122 |
| remquof_null / half-ties | 6.098–6.100 | 25.620–25.730 | 0.235–0.236 | 0.238 | 0.238–0.249 |
| remainderf / quotient-wrap | 5.403–5.502 | 6.974–7.041 | 0.762–0.770 | 0.767–0.788 | 0.789–0.955 |
| remquof / quotient-wrap | 5.711–5.814 | 6.775–6.992 | 0.794–0.843 | 0.816–0.852 | 0.827–0.866 |
| remquof_null / quotient-wrap | 5.415–5.502 | 6.974–7.043 | 0.761–0.764 | 0.771–0.787 | 0.788–0.793 |
| remainderf / subnormal | 10.226–10.352 | 191.180–191.250 | 0.053 | 0.053–0.054 | 0.055–0.057 |
| remquof / subnormal | 10.709–10.998 | 70.650–72.423 | 0.149–0.151 | 0.151–0.152 | 0.154–0.159 |
| remquof_null / subnormal | 9.923–10.141 | 191.196–191.237 | 0.051 | 0.052–0.053 | 0.053–0.055 |
| remainderf / wide-gap | 25.262–25.308 | 206.607–207.033 | 0.120 | 0.122 | 0.124–0.126 |
| remquof / wide-gap | 27.000–27.643 | 110.797–114.147 | 0.239–0.240 | 0.242–0.244 | 0.246–0.250 |
| remquof_null / wide-gap | 25.981–26.095 | 206.609–207.158 | 0.123–0.124 | 0.125–0.126 | 0.128–0.130 |
| remainderf / zero | 2.609–2.611 | 19.448–19.478 | 0.132–0.133 | 0.133–0.134 | 0.134–0.135 |
| remquof / zero | 2.754–2.904 | 6.591–6.760 | 0.400–0.404 | 0.407–0.431 | 0.428–0.459 |
| remquof_null / zero | 2.608–2.611 | 19.434–19.481 | 0.131–0.133 | 0.134 | 0.134–0.135 |
| remainderf / infinite-divisor | 2.612–2.758 | 20.052–20.082 | 0.129–0.130 | 0.130–0.140 | 0.131–0.148 |
| remquof / infinite-divisor | 2.831–3.103 | 4.246–4.884 | 0.583–0.690 | 0.594–0.697 | 0.605–0.705 |
| remquof_null / infinite-divisor | 2.611–2.668 | 20.078–20.395 | 0.128–0.130 | 0.130 | 0.138 |
| remainderf / NaN-domain | 2.701–2.782 | 78.326–78.348 | 0.034 | 0.034–0.036 | 0.037 |
| remquof / NaN-domain | 2.876–3.579 | 2.230–2.510 | 1.249–1.285 | 1.287–1.425 | 1.353–1.431 |
| remquof_null / NaN-domain | 2.604–2.696 | 78.323–78.366 | 0.033 | 0.034 | 0.035–0.037 |
| remainderf / wide-odd | 24.773–24.850 | 145.929–146.128 | 0.167 | 0.170 | 0.173–0.175 |
| remquof / wide-odd | 27.171–27.282 | 128.168–128.660 | 0.207–0.209 | 0.212–0.213 | 0.216–0.217 |
| remquof_null / wide-odd | 25.599–25.646 | 145.922–146.367 | 0.172–0.173 | 0.175–0.176 | 0.180 |
| remainderf / wide-power2 | 5.214–5.215 | 75.044–75.065 | 0.068–0.069 | 0.069 | 0.070 |
| remquof / wide-power2 | 5.420–5.536 | 70.976–73.070 | 0.075 | 0.076 | 0.076–0.077 |
| remquof_null / wide-power2 | 5.030–5.033 | 75.018–75.057 | 0.066 | 0.067 | 0.067–0.068 |
| remainderf / admission-boundary | 5.505–5.513 | 89.572–89.639 | 0.060–0.061 | 0.062 | 0.064–0.065 |
| remquof / admission-boundary | 6.310–6.317 | 23.249–23.440 | 0.265–0.269 | 0.269–0.272 | 0.270–0.273 |
| remquof_null / admission-boundary | 5.504–5.509 | 89.376–89.627 | 0.060–0.061 | 0.062 | 0.062–0.063 |
| remainderf / low-factor | 24.549–24.614 | 145.772–146.007 | 0.166 | 0.168–0.169 | 0.172–0.173 |
| remquof / low-factor | 27.798–28.084 | 62.692–62.851 | 0.435–0.436 | 0.443–0.444 | 0.452–0.453 |
| remquof_null / low-factor | 25.306–25.348 | 145.795–145.840 | 0.171 | 0.173–0.174 | 0.177–0.179 |
| remainderf / high-factor | 18.798–19.611 | 122.754–122.852 | 0.151–0.157 | 0.153–0.159 | 0.156–0.164 |
| remquof / high-factor | 20.667–20.834 | 42.159–42.573 | 0.483–0.484 | 0.490–0.492 | 0.499–0.503 |
| remquof_null / high-factor | 18.243–19.770 | 122.646–122.753 | 0.147–0.157 | 0.148–0.161 | 0.152–0.164 |

### GCC16 / actual-prior

Each cell spans two runs and both entry states (four observations).

| API / range | Own ns/call | Reference ns/call | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 11.171–11.415 | 10.892–11.201 | 0.997–1.013 | 1.021–1.029 | 1.044–1.054 |
| remquo / normal | 11.386–11.451 | 11.165–11.249 | 1.002–1.011 | 1.013–1.023 | 1.024–1.037 |
| remquo_null / normal | 11.603–11.750 | 11.285–11.378 | 1.007–1.017 | 1.024–1.032 | 1.040–1.048 |
| remainder / half-ties | 7.006–7.201 | 6.890–7.199 | 0.918–0.986 | 0.967–1.013 | 1.034–1.062 |
| remquo / half-ties | 7.053–7.211 | 6.899–7.048 | 1.018–1.020 | 1.022–1.023 | 1.025–1.027 |
| remquo_null / half-ties | 6.845–6.994 | 6.802–7.066 | 0.967–0.979 | 1.007–1.012 | 1.025–1.031 |
| remainder / quotient-wrap | 6.329–6.497 | 5.905–6.298 | 1.003–1.040 | 1.015–1.072 | 1.072–1.105 |
| remquo / quotient-wrap | 5.974–5.976 | 5.802–5.818 | 1.024–1.027 | 1.028–1.030 | 1.032–1.034 |
| remquo_null / quotient-wrap | 5.852–6.177 | 5.946–6.143 | 0.959–1.001 | 0.985–1.017 | 1.036–1.082 |
| remainder / subnormal | 19.337–19.737 | 19.213–19.301 | 0.988–1.006 | 1.004–1.021 | 1.016–1.039 |
| remquo / subnormal | 19.281–19.713 | 18.990–19.357 | 1.001–1.009 | 1.016–1.021 | 1.027–1.031 |
| remquo_null / subnormal | 19.232–19.530 | 18.788–19.147 | 1.000–1.011 | 1.020–1.022 | 1.031–1.034 |
| remainder / wide-gap | 155.219–155.489 | 677.839–677.900 | 0.228–0.229 | 0.229 | 0.230–0.231 |
| remquo / wide-gap | 154.983–155.260 | 677.739–677.828 | 0.228 | 0.229 | 0.230–0.231 |
| remquo_null / wide-gap | 155.000–155.210 | 677.928–677.970 | 0.228 | 0.229 | 0.230 |
| remainder / zero | 3.341–3.817 | 3.205–3.584 | 0.910–1.064 | 1.003–1.140 | 1.136–1.230 |
| remquo / zero | 2.840–2.965 | 2.623–3.056 | 0.927–1.080 | 0.932–1.083 | 1.086 |
| remquo_null / zero | 3.204–3.627 | 3.124–3.413 | 0.881–0.883 | 0.997–1.071 | 1.003–1.309 |
| remainder / infinite-divisor | 3.349–3.844 | 3.198–3.668 | 0.931–0.998 | 1.061–1.131 | 1.070–1.232 |
| remquo / infinite-divisor | 2.964–3.271 | 2.628–2.992 | 0.977–1.081 | 1.003–1.151 | 1.168–1.247 |
| remquo_null / infinite-divisor | 3.207–3.786 | 3.058–3.213 | 0.881–0.998 | 0.997–1.211 | 1.071–1.217 |
| remainder / NaN-domain | 3.761–4.096 | 3.174–3.550 | 1.070–1.152 | 1.137–1.209 | 1.206–1.248 |
| remquo / NaN-domain | 3.198–3.441 | 2.654–2.784 | 1.158–1.191 | 1.198–1.235 | 1.220–1.256 |
| remquo_null / NaN-domain | 3.624–3.684 | 3.013–3.231 | 1.053–1.120 | 1.104–1.201 | 1.144–1.257 |
| remainder / wide-odd | 655.779–655.822 | 663.037–663.115 | 0.988 | 0.989 | 0.990–0.991 |
| remquo / wide-odd | 655.518–655.622 | 662.890–662.942 | 0.988 | 0.989 | 0.990–0.991 |
| remquo_null / wide-odd | 655.752–655.791 | 663.100–663.182 | 0.988 | 0.989 | 0.990 |
| remainder / wide-power2 | 13.300–13.305 | 12.074–12.087 | 1.095–1.099 | 1.100–1.101 | 1.103–1.105 |
| remquo / wide-power2 | 13.519–13.526 | 12.136–12.167 | 1.109 | 1.112–1.114 | 1.115–1.117 |
| remquo_null / wide-power2 | 13.234–13.246 | 12.002–12.011 | 1.098–1.100 | 1.102–1.104 | 1.105–1.107 |
| remainder / admission-boundary | 72.581–72.817 | 101.907–101.937 | 0.695–0.700 | 0.714 | 0.729–0.730 |
| remquo / admission-boundary | 72.562–72.768 | 102.386–102.408 | 0.693–0.695 | 0.710 | 0.725–0.728 |
| remquo_null / admission-boundary | 72.597–72.842 | 101.865–102.334 | 0.697–0.700 | 0.714 | 0.726–0.732 |
| remainder / low-factor | 655.729–655.780 | 662.945–663.004 | 0.988 | 0.989 | 0.990–0.991 |
| remquo / low-factor | 655.499–655.569 | 662.812–662.876 | 0.988 | 0.989 | 0.990 |
| remquo_null / low-factor | 655.722–655.853 | 663.013–663.137 | 0.986–0.988 | 0.989 | 0.990–1.001 |
| remainder / high-factor | 98.180–98.261 | 451.036–451.088 | 0.217 | 0.218 | 0.218–0.219 |
| remquo / high-factor | 97.573–97.760 | 449.943–450.321 | 0.216 | 0.217 | 0.218 |
| remquo_null / high-factor | 98.252–98.296 | 450.303–450.374 | 0.217 | 0.218 | 0.219 |
| remainderf / normal | 11.482–11.518 | 11.562–11.664 | 0.966–0.970 | 0.988–0.998 | 1.010–1.022 |
| remquof / normal | 11.473–11.628 | 10.952–11.370 | 1.009–1.038 | 1.023–1.050 | 1.036–1.063 |
| remquof_null / normal | 11.540–11.650 | 11.427–11.589 | 0.988–1.000 | 1.002–1.013 | 1.018–1.027 |
| remainderf / half-ties | 6.850–6.864 | 6.772–6.956 | 0.961–0.987 | 0.981–1.007 | 1.017–1.037 |
| remquof / half-ties | 6.897–6.903 | 6.900–6.911 | 0.997–0.998 | 0.998–1.000 | 1.000–1.002 |
| remquof_null / half-ties | 6.791–6.848 | 6.770–6.827 | 0.955–0.982 | 0.998–1.004 | 1.036–1.043 |
| remainderf / quotient-wrap | 6.032–6.204 | 5.883–6.135 | 0.944–1.003 | 1.010–1.030 | 1.034–1.089 |
| remquof / quotient-wrap | 5.698–5.818 | 5.679–5.790 | 0.998–1.000 | 1.001–1.022 | 1.005–1.032 |
| remquof_null / quotient-wrap | 6.000–6.013 | 5.993–6.007 | 0.945–0.983 | 0.997–1.003 | 1.023–1.044 |
| remainderf / subnormal | 11.579–11.745 | 11.881–11.973 | 0.946–0.962 | 0.966–0.988 | 1.003–1.009 |
| remquof / subnormal | 11.822–11.928 | 11.467–11.796 | 0.996–1.023 | 1.009–1.032 | 1.023–1.045 |
| remquof_null / subnormal | 11.590–11.744 | 11.827–11.903 | 0.963–0.970 | 0.978–0.988 | 0.995–1.004 |
| remainderf / wide-gap | 27.823–27.876 | 28.094–28.145 | 0.972–0.977 | 0.988–0.990 | 1.002–1.004 |
| remquof / wide-gap | 27.906–28.024 | 27.928–28.019 | 0.985–0.989 | 0.998–1.001 | 1.011–1.015 |
| remquof_null / wide-gap | 27.894–27.937 | 27.916–27.968 | 0.983–0.984 | 0.998–1.001 | 1.014–1.016 |
| remainderf / zero | 3.068–3.977 | 3.138–3.825 | 0.767–0.939 | 0.881–1.065 | 0.939–1.245 |
| remquof / zero | 2.676–2.995 | 2.985–3.117 | 0.856–0.999 | 0.947–1.004 | 1.002–1.168 |
| remquof_null / zero | 3.054–3.565 | 3.121–3.483 | 0.802–0.876 | 0.877–1.061 | 1.003–1.410 |
| remainderf / infinite-divisor | 3.132–3.666 | 3.135–3.653 | 0.865–0.936 | 0.937–1.003 | 1.063–1.198 |
| remquof / infinite-divisor | 2.620–3.057 | 2.986–3.118 | 0.856–0.997 | 0.997–1.001 | 1.003–1.163 |
| remquof_null / infinite-divisor | 2.839–3.486 | 3.058–3.490 | 0.752–0.873 | 0.873–1.059 | 1.162–1.213 |
| remainderf / NaN-domain | 3.255–3.466 | 3.229–3.376 | 0.935–1.070 | 1.000–1.074 | 1.071–1.149 |
| remquof / NaN-domain | 2.724–2.779 | 2.715–2.792 | 0.932–0.994 | 0.992–1.001 | 1.004–1.053 |
| remquof_null / NaN-domain | 3.012–3.230 | 3.082–3.248 | 0.862–0.932 | 0.983–0.998 | 1.002–1.176 |
| remainderf / wide-odd | 26.845–27.066 | 26.768–27.009 | 0.978–0.987 | 0.998–1.003 | 1.017–1.019 |
| remquof / wide-odd | 27.315–27.360 | 26.973–27.091 | 0.999–1.005 | 1.010–1.015 | 1.019–1.025 |
| remquof_null / wide-odd | 26.956–26.981 | 27.214–27.289 | 0.970–0.973 | 0.987–0.990 | 1.002–1.006 |
| remainderf / wide-power2 | 5.750–6.444 | 5.754–6.591 | 0.975–0.998 | 0.999–1.001 | 1.001–1.037 |
| remquof / wide-power2 | 6.018–6.024 | 6.019–6.023 | 0.994–0.999 | 1.000 | 1.000–1.001 |
| remquof_null / wide-power2 | 5.843–5.845 | 5.842–5.849 | 0.971–0.998 | 0.999–1.000 | 1.001–1.028 |
| remainderf / admission-boundary | 6.439–6.690 | 6.332–6.614 | 0.989–1.012 | 1.000–1.045 | 1.014–1.107 |
| remquof / admission-boundary | 6.496–6.630 | 6.493–6.632 | 0.997–0.998 | 0.999–1.001 | 1.001–1.003 |
| remquof_null / admission-boundary | 6.286–6.417 | 6.286–6.415 | 0.961–0.998 | 0.999–1.006 | 1.003–1.043 |
| remainderf / low-factor | 26.730–26.792 | 26.852–27.014 | 0.974–0.980 | 0.993–0.997 | 1.008–1.012 |
| remquof / low-factor | 27.179–27.445 | 26.896–27.321 | 0.990–1.000 | 1.005–1.011 | 1.017–1.025 |
| remquof_null / low-factor | 26.768–26.809 | 27.203–27.332 | 0.964–0.968 | 0.981–0.984 | 0.999–1.001 |
| remainderf / high-factor | 22.526–22.890 | 22.263–22.886 | 0.973–0.995 | 0.990–1.015 | 1.003–1.039 |
| remquof / high-factor | 21.774–22.411 | 21.643–22.588 | 0.970–0.985 | 0.990–1.006 | 1.006–1.024 |
| remquof_null / high-factor | 22.631–22.801 | 22.884–22.963 | 0.976–0.980 | 0.989–0.992 | 1.002–1.006 |

### GCC16 / host

Each cell spans two runs and both entry states (four observations).

| API / range | Own ns/call | Reference ns/call | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 10.221–10.530 | 13.595–14.148 | 0.730–0.740 | 0.741–0.760 | 0.753–0.781 |
| remquo / normal | 11.159–11.335 | 17.974–18.095 | 0.588–0.603 | 0.614–0.626 | 0.628–0.644 |
| remquo_null / normal | 10.439–10.492 | 14.158–14.220 | 0.730–0.734 | 0.736–0.739 | 0.741–0.751 |
| remainder / half-ties | 6.424–6.579 | 25.939–25.946 | 0.245–0.249 | 0.248–0.253 | 0.250–0.261 |
| remquo / half-ties | 7.066–7.075 | 7.454–7.633 | 0.921–0.938 | 0.928–0.945 | 0.939–0.954 |
| remquo_null / half-ties | 6.419–6.430 | 25.941–25.946 | 0.245–0.246 | 0.247–0.248 | 0.248–0.250 |
| remainder / quotient-wrap | 5.901–6.313 | 6.828–6.974 | 0.837–0.863 | 0.863–0.922 | 0.870–0.927 |
| remquo / quotient-wrap | 5.948–6.080 | 7.428–7.678 | 0.769–0.783 | 0.791–0.798 | 0.798–0.811 |
| remquo_null / quotient-wrap | 5.898–6.041 | 6.829–6.975 | 0.831–0.863 | 0.862–0.866 | 0.867–0.871 |
| remainder / subnormal | 16.619–16.837 | 194.628–194.792 | 0.084–0.085 | 0.085–0.086 | 0.087–0.088 |
| remquo / subnormal | 19.137–19.273 | 75.038–75.514 | 0.246–0.247 | 0.254–0.256 | 0.264–0.266 |
| remquo_null / subnormal | 16.369–17.063 | 194.591–195.303 | 0.083–0.086 | 0.084–0.088 | 0.087–0.089 |
| remainder / wide-gap | 161.193–162.068 | 634.764–640.278 | 0.245–0.248 | 0.252–0.253 | 0.260–0.261 |
| remquo / wide-gap | 167.043–169.022 | 175.249–176.458 | 0.927–0.931 | 0.947–0.949 | 0.969–0.972 |
| remquo_null / wide-gap | 161.134–162.394 | 635.989–640.094 | 0.246–0.249 | 0.253–0.254 | 0.259–0.262 |
| remainder / zero | 3.206–3.279 | 19.866–19.871 | 0.141–0.161 | 0.161–0.162 | 0.162–0.172 |
| remquo / zero | 2.991–3.266 | 6.337–6.715 | 0.426–0.459 | 0.453–0.481 | 0.500–0.540 |
| remquo_null / zero | 2.892–3.131 | 19.841–19.872 | 0.131–0.151 | 0.147–0.152 | 0.152–0.172 |
| remainder / infinite-divisor | 3.211–3.278 | 19.924–19.934 | 0.151–0.161 | 0.161–0.163 | 0.161–0.172 |
| remquo / infinite-divisor | 3.119–3.494 | 5.191–5.576 | 0.528–0.589 | 0.584–0.640 | 0.629–0.686 |
| remquo_null / infinite-divisor | 3.007–3.014 | 19.921–19.935 | 0.140–0.150 | 0.150–0.151 | 0.153–0.171 |
| remainder / NaN-domain | 3.293–3.421 | 78.530–78.546 | 0.039–0.040 | 0.042–0.043 | 0.045 |
| remquo / NaN-domain | 3.165–3.637 | 2.507–2.879 | 1.141–1.228 | 1.242–1.315 | 1.265–1.340 |
| remquo_null / NaN-domain | 3.188–3.234 | 78.531–78.549 | 0.039–0.040 | 0.041 | 0.043–0.044 |
| remainder / wide-odd | 673.166–687.015 | 489.270–499.650 | 1.269–1.342 | 1.356–1.370 | 1.404–1.409 |
| remquo / wide-odd | 701.687–736.487 | 564.124–588.414 | 1.140–1.180 | 1.251–1.262 | 1.308–1.314 |
| remquo_null / wide-odd | 672.073–677.520 | 489.596–490.618 | 1.341–1.346 | 1.369–1.375 | 1.405–1.408 |
| remainder / wide-power2 | 12.282–12.288 | 84.670–85.082 | 0.143–0.144 | 0.145 | 0.146–0.149 |
| remquo / wide-power2 | 13.240–13.249 | 74.241–74.602 | 0.176–0.177 | 0.178–0.180 | 0.181 |
| remquo_null / wide-power2 | 12.236–12.248 | 84.731–84.852 | 0.142–0.143 | 0.145 | 0.146–0.147 |
| remainder / admission-boundary | 75.347–75.364 | 152.123–152.446 | 0.484–0.488 | 0.494–0.496 | 0.505–0.506 |
| remquo / admission-boundary | 75.550–76.767 | 37.642–38.210 | 1.971–1.977 | 2.006–2.008 | 2.032–2.039 |
| remquo_null / admission-boundary | 75.357–75.372 | 152.229–152.453 | 0.484–0.488 | 0.494–0.495 | 0.503–0.505 |
| remainder / low-factor | 673.164–676.334 | 487.552–488.296 | 1.346–1.349 | 1.373–1.380 | 1.411–1.415 |
| remquo / low-factor | 675.935–677.758 | 189.576–190.086 | 3.451–3.461 | 3.550–3.559 | 3.656–3.684 |
| remquo_null / low-factor | 676.305–681.201 | 487.879–490.979 | 1.331–1.352 | 1.375–1.380 | 1.409–1.415 |
| remainder / high-factor | 101.942–101.971 | 471.719–472.196 | 0.212 | 0.216 | 0.220–0.222 |
| remquo / high-factor | 102.377–102.862 | 67.382–67.427 | 1.486–1.497 | 1.518–1.520 | 1.542–1.548 |
| remquo_null / high-factor | 101.477–101.709 | 471.634–472.385 | 0.211 | 0.215 | 0.220 |
| remainderf / normal | 10.619–10.974 | 14.406–14.409 | 0.731–0.754 | 0.739–0.763 | 0.752–0.774 |
| remquof / normal | 11.172–11.354 | 17.681–18.889 | 0.587–0.628 | 0.601–0.632 | 0.609–0.659 |
| remquof_null / normal | 11.477–11.602 | 14.115–14.412 | 0.796–0.802 | 0.804–0.814 | 0.815–0.828 |
| remainderf / half-ties | 6.420–6.439 | 25.727–26.256 | 0.244 | 0.245–0.248 | 0.251–0.255 |
| remquof / half-ties | 6.912–6.917 | 7.594–7.719 | 0.889–0.907 | 0.896–0.912 | 0.902–0.917 |
| remquof_null / half-ties | 6.260–6.387 | 25.728–26.253 | 0.241–0.242 | 0.243 | 0.251–0.254 |
| remainderf / quotient-wrap | 5.876–6.008 | 6.830–7.040 | 0.808–0.835 | 0.859–0.862 | 0.866–0.869 |
| remquof / quotient-wrap | 5.795–5.931 | 7.145–7.350 | 0.791–0.807 | 0.797–0.813 | 0.802–0.819 |
| remquof_null / quotient-wrap | 5.878–6.018 | 6.973–6.977 | 0.807–0.858 | 0.841–0.863 | 0.866–0.868 |
| remainderf / subnormal | 10.037–10.115 | 191.542–192.014 | 0.052 | 0.052–0.053 | 0.053–0.055 |
| remquof / subnormal | 11.324–11.341 | 73.116–73.266 | 0.151–0.152 | 0.154–0.155 | 0.158–0.161 |
| remquof_null / subnormal | 9.867–10.242 | 191.558–191.754 | 0.051–0.053 | 0.051–0.053 | 0.052–0.055 |
| remainderf / wide-gap | 26.167–26.245 | 207.180–207.482 | 0.125 | 0.126–0.127 | 0.129 |
| remquof / wide-gap | 27.823–28.057 | 114.431–114.842 | 0.239–0.241 | 0.243–0.244 | 0.248–0.250 |
| remquof_null / wide-gap | 26.066–26.211 | 207.030–208.407 | 0.124–0.125 | 0.126 | 0.129–0.130 |
| remainderf / zero | 3.011–3.407 | 19.576–19.625 | 0.133–0.153 | 0.154–0.174 | 0.174–0.176 |
| remquof / zero | 2.683–2.988 | 6.827–7.196 | 0.365–0.371 | 0.391–0.406 | 0.445–0.469 |
| remquof_null / zero | 2.701–3.049 | 19.591–19.603 | 0.123–0.143 | 0.143–0.145 | 0.144–0.174 |
| remainderf / infinite-divisor | 3.010–3.282 | 20.199–20.217 | 0.129–0.148 | 0.149–0.166 | 0.149–0.169 |
| remquof / infinite-divisor | 2.872–3.122 | 4.339–4.784 | 0.597–0.626 | 0.611–0.719 | 0.709–0.850 |
| remquof_null / infinite-divisor | 2.809–3.346 | 20.208–20.218 | 0.119–0.139 | 0.139–0.168 | 0.139–0.169 |
| remainderf / NaN-domain | 2.797–2.906 | 78.335–78.366 | 0.034–0.036 | 0.036–0.037 | 0.038–0.039 |
| remquof / NaN-domain | 2.651–2.984 | 2.676–3.011 | 0.988–0.992 | 0.991–1.061 | 0.994–1.129 |
| remquof_null / NaN-domain | 2.699–2.839 | 78.330–78.345 | 0.033–0.034 | 0.035–0.036 | 0.036 |
| remainderf / wide-odd | 25.062–25.143 | 146.427–146.916 | 0.168–0.170 | 0.171–0.172 | 0.174–0.176 |
| remquof / wide-odd | 27.594–27.679 | 129.285–129.512 | 0.209–0.210 | 0.213–0.214 | 0.218 |
| remquof_null / wide-odd | 24.949–25.035 | 146.437–146.857 | 0.168 | 0.171 | 0.174–0.175 |
| remainderf / wide-power2 | 5.092–5.097 | 75.049–75.215 | 0.067 | 0.068 | 0.068–0.069 |
| remquof / wide-power2 | 5.531–5.536 | 73.378–73.650 | 0.074–0.075 | 0.075 | 0.076 |
| remquof_null / wide-power2 | 5.072–5.119 | 75.161–75.904 | 0.067 | 0.068 | 0.068 |
| remainderf / admission-boundary | 5.705–5.785 | 89.885–90.429 | 0.062 | 0.062–0.063 | 0.065–0.066 |
| remquof / admission-boundary | 6.361–6.368 | 23.668–23.804 | 0.264–0.266 | 0.268–0.269 | 0.270 |
| remquof_null / admission-boundary | 5.577–5.771 | 89.766–90.009 | 0.061–0.062 | 0.062–0.063 | 0.065–0.067 |
| remainderf / low-factor | 24.764–24.824 | 146.240–146.482 | 0.166–0.167 | 0.169–0.170 | 0.173–0.174 |
| remquof / low-factor | 28.171–28.204 | 63.367–63.826 | 0.434–0.435 | 0.443 | 0.451–0.452 |
| remquof_null / low-factor | 24.733–24.762 | 146.183–146.531 | 0.166–0.167 | 0.169–0.170 | 0.173–0.174 |
| remainderf / high-factor | 19.350–20.149 | 123.154–123.283 | 0.155–0.160 | 0.157–0.163 | 0.160–0.165 |
| remquof / high-factor | 20.364–20.421 | 42.821–42.890 | 0.468–0.470 | 0.476–0.478 | 0.485–0.489 |
| remquof_null / high-factor | 19.810–20.230 | 123.147–123.342 | 0.153–0.161 | 0.161–0.164 | 0.164–0.169 |

