# Native long-double value and rounding foundation

The fifteen suffix-l interface names in `basic.h` operate on native C `long double`.
Their results are deterministic within a format. Binary64, extended80,
binary128 and IBM double-double have different representable populations and
do not promise identical encodings. Native padding is never numerical identity.
No Float/Double kernel, table, answer population or legacy aggregate is changed.

The numerical engine uses a fixed array of 1,032 unsigned 32-bit limbs, with
bit zero representing 2^-16494. This covers the entire finite binary128 range
and every bit in the exact sum of two finite binary64 components. There is no
allocation, host math call, conversion through Double or floating arithmetic in
numerical decisions. Only the existing explicit invalid and divide-by-zero
helpers execute arithmetic to raise required flags. Packing uses integer
nearest/even decisions; exact representable results have no new rounding flags.

`fabsl` clears the numerical sign; `copysignl` uses only the raw sign of its
second argument, including malformed values and signaling NaNs. `nanl` ignores
its tag without dereferencing it. All NaN results are positive canonical quiet
NaNs. A signaling NaN or invalid extended80 encoding raises invalid. Extended80
pseudo-denormals normalize to exponent one; nonzero exponents with a clear
explicit integer bit are invalid. Minimum and maximum select the numeric input
when exactly one argument is a quiet NaN. Any signaling/invalid operand or two
NaNs return canonical NaN. Opposite-signed zero ties select -0 for minimum and
+0 for maximum; same-sign zeros retain their sign.

`floorl`, `ceill`, `truncl`, `roundl` and `rintl` ignore the caller's mode.
Round uses ties away from zero; rint uses fixed ties even. Both rint and
nearbyint follow the existing library policy of adding no inexact flag when
rounding finite fractions. `nearbyintl` reads the native arithmetic rounding
control. On extended80 x86 this means x87 RC, even when MXCSR disagrees; x87
precision control is irrelevant to integer decisions. No control is written.

`modfl` writes the integral part and returns the signed fractional part. Its
output pointer may be NULL or alias the caller's source object: the by-value
input is consumed before the store. Infinity splits into itself and a signed
zero; NaN writes/returns canonical NaN. `frexpl` returns a fraction of magnitude
[0.5,1) and an exponent, with zero exponent for special values. Its exponent
pointer may be NULL; otherwise it must designate a valid int object and must
not overlap a long-double object. `ilogbl` returns GMATH_ILOGB0 for zero,
GMATH_ILOGBNAN for NaN and INT_MAX for infinity, raising invalid in each case.
`logbl` returns the exact exponent for finite nonzero values, positive infinity
for either infinity, or negative infinity with divide-by-zero for zero.
Every operation preserves errno, controls and incoming standard flags.

IBM DD decoding sums both components exactly, preserving widely separated tails,
cancellation and the sign of a leading zero pair. Nonfinite low components and
infinity paired with a nonzero low component are invalid. Exact finite sums
outside ±(DBL_MAX + 0x1.fffffffffffffp+969) are malformed and raise invalid with
canonical NaN. Independent raw fixtures cover both signed limits and their
immediate neighbors, plus (DBL_MAX, DBL_MAX). Finite output uses a
nearest/even binary64 leader, its exact residual as the low component, and +0
for a zero low component. A leader above the binary64 overflow midpoint clamps
to maximum finite before forming the residual. Raw overlapping component pairs
are synthetic inputs, not evidence that the native ABI creates a normalized DD
population. No uniform 106- or 113-bit lattice is assumed.

IBM DD `frexpl` is deliberately unavailable: `GMATH_HAVE_FREXPL` is zero and
its public declaration and native definition are omitted. For x=(1,2^-1074), the necessary normalized
fraction is 0.5+2^-1075, outside the lattice of sums of two binary64 components.
[C11 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)
§7.12.6.4 requires exact reconstruction; Annex F.10.3.4 specifies exact,
mode-independent finite binary decomposition.
[IBM documents DD](https://www.ibm.com/docs/ssw_aix_72/com.ibm.aix.genprogc/128bit_long_double_floating-point_datatype.htm)
as a variable-precision exact component sum, including the witness above. No approximation or error-as-number
is substituted. The corpus has no DD frexp numeric row; the oracle proves the
unrepresentability witness, and a compile-only macro fixture checks availability,
missing declaration and missing definition. That fixture is not native DD
execution. All fifteen functions are available on binary64/extended80/binary128;
DD has fourteen. Existing nexttoward DD decoding is unchanged.

On SysV AMD64 native80, naked wrappers pass incoming memory bytes to an integer
helper and execute one `fldt` only for the final return. Thus an incoming
signaling NaN or malformed encoding is classified before x87 can transform it.
The ABI may set the architecture-specific denormal operand status when a final
extended80 subnormal crosses st(0); this is not a C standard exception. Standard
underflow/inexact are not incidentally raised. Unmasked traps are outside the
coherent nontrapping environment contract inherited from the existing family.

The new archive gate extracts and inspects every member against the source
population. All legacy members run through the byte-identical shared
`check-no-x87.sh`. The new object permits only checked native80 return transfers
and control reads; x87 arithmetic and control writes are rejected on x86.
Other target checks reject the listed control-writing instructions; they do not
prove absence of every arithmetic instruction across all ISAs. Missing members,
duplicates, unexpected members and missing wrapper coverage fail closed. The
suite's cross-platform scripts still invoke the old gate directly on a whole
archive. Those invocations require a future coordinated suite change and are
not covered by this local Makefile integration.

The committed bounded corpus contains raw format-specific inputs, expected
results, auxiliary outputs, sentinels and flags. Python `Fraction` calculations
are the independent oracle; host libm output is not an oracle. Frozen SHA256
values cover both corpus and supplemental format-specific FNV hashes stored in
`tests/corpus/long-double-foundation.hash`, separately from the old 122 names
and aggregate. The default `corpus-hash` CLI retains its exact legacy stdout
fields. It silently validates native long-double rows, hash and count, and
returns failure if that validation fails. Native unit tests link the actual
archive. A separate raw probe runs all four layouts synthetically and its actual native ABI independently.
The latter deliberately makes MXCSR and x87 RC disagree, exercises 24/53/64-bit x87
precision settings, and retains incoming standard flags and errno. Compiled
pack, tie-round, NaN, state, x87-arithmetic and control-write defects must each
fail for their intended reason after an unmodified positive control passes.

| Representation | Synthetic integer adapter | Executed ABI (host or QEMU) |
| --- | --- | --- |
| binary64 | Exact rational fixture population, all15 | GCC16 compiler-selected x86-64 ABI mode |
| extended80 | Exact rational fixture population | x86-64 SysV with GCC14/GCC16/Clang19; GCC16 i686 under QEMU; mixed controls and precision settings |
| binary128 | Exact rational fixture population, all15 | GCC16 compiler-selected x86-64 ABI mode; ARM64, s390x and SPARC64 target ABIs under QEMU |
| IBM double-double | Exact sums, range limits, separated tails and cancellation;14 functions | GCC16 PowerPC32 and PowerPC64 target ABIs under QEMU; frexpl explicitly unavailable |

Focused GCC14, GCC16 and Clang19 checks pass 10,449 synthetic rational rows.
GCC16 executes 2,592 native80 rows, 2,484 binary64 ABI-mode rows and 2,565
binary128 ABI-mode rows. Clang19 ASan/UBSan passes the same synthetic/native80
population. Three archive-linked unit tests pass with GCC14 and Clang19.
Thirteen compiled numerical/state/instruction/wrapper/unwind defects, two archive
population defects and thirteen malformed probe inputs fail for their intended
reason; the unmodified control passes. Mocked frame tables also prove unexpected
CFA and return-address rules are rejected. Focused Make checks execute the actual
archive-linked unit binary, and changing either FP helper rebuilds the raw probe. The DD
compile-only availability fixture also passes. The old hash remains
f5fa269eb60ee34f over 292,711 aggregate results and all122 function sets.
Focused validation is recorded under the private build evidence directory.
GCC16 target binaries additionally pass all 10,449 synthetic rows and their
format-specific ABI population under QEMU: 2,808 DD rows on each PowerPC target,
2,565 binary128 rows on each ARM64/s390x/SPARC64 target, and 2,592 extended80 rows
on i686. These execute target instructions and calling conventions under
emulation; physical hardware execution is not claimed. Synthetic decoding and
compiler-selected ABI modes alone are not substitutes for these target runs.

The corrected new-object instruction gate also passes all six GCC16 target
objects. Its ELFv1 PowerPC64 code-entry handling is explicit; native80 host
wrappers additionally validate helper arguments, output slot, stack restoration
and unwind rows. This does not run or repair the suite's separate legacy caller.

Family review findings are resolved. Composite default GCC16 verification accounts
for all 110 default gates and runs all 42 main binaries: 288 tests, 287 passes
and one expected native32-long skip. An interrupted default attempt passed the
first 70 gates, then failed because two legacy mutation builders omitted the new
object. Those source-selection lists were repaired without changing any mutation
or assertion. Both repaired portions pass their targeted checks. All 77
production/main-test objects from the frozen original and repaired trees match
after removing debug sections and the GNU build ID only. The remaining aggregate
prerequisites, its trig recipe, all 39 successor gates and every main binary
then pass. Default gates retain their explicitly reported optional oracle skips;
this does not claim additional oracle execution. This is validated resumption;
all three earlier failed full attempts remain failures. Build records were
archived, gzip/tar verified and bulky
temporary builds reclaimed after each run.

The library and every caller must use the same native long-double ABI and
compiler ABI flags. The compiler-selected binary64/binary128 test modes are
separate builds and cannot be mixed with an extended80 library.

## Roots, exponentials, logarithms and power

The eleven additional interfaces are `sqrtl`, `cbrtl`, `hypotl`, `expl`,
`exp2l`, `expm1l`, `logl`, `log2l`, `log10l`, `log1pl` and `powl`.
They use the same four native representations and raw NaN classification.
Their integer decisions target nearest/ties-even independently of caller RC,
precision control and DAZ/FTZ. Roots are correctly rounded. Transcendentals
return a value whose actual predecessor and successor enclose the real
result; correctly rounded transcendental or directed-output guarantees are
not made. DD neighbors are exact sums of two binary64 components.

Square/cube roots use restoring integer recurrences. With root prefix r and
square s=r*r, the next square trial is 4*r+1 and the cube trial is 12*s+6*r+1.
The residual remains nonnegative and smaller than the next trial. For DD,
retaining through 2^-1076 requires at most 2101 digits, including hypot near
the finite upper limit. The cube square/residual needs fewer than 4208 bits;
216 32-bit scratch limbs cover that bound. Single formats retain at least
three guard digits, down to the complete binary128 minimum-subnormal grid.
Final selection compares the exact square/cube of the *sum* of the adjacent
candidates with 2^degree times the exact radicand. It never halves that sum
on the output grid. Exact powers decide ties and exactness flags.

The transcendental intervals use 4352 fractional bits and 64 integer bits.
The latter cover the reduced logarithms and the bounded exponential input;
out-of-range magnitudes are classified before multiplication or projection.
Normalization preserves the entire DD component span:2098 bits from 2^1023
to 2^-1074. No input conversion rounds away a near-unit remote tail.
Positive directed division and signed directed multiplication enclose every
truncation. Logarithms use twice the positive atanh series at
0<=t<=1/3+2^-4352. Its 1400 terms leave a positive tail smaller than 2^-4430;
one upper fixed-point unit encloses it. The logarithm of two is obtained
from the same series at 1/3. Exponentials reduce by an interval for k*log(2),
with k selected using the upper endpoint, so 0<=r<log(2)+2^-4200.
Their 1000-term positive Taylor series has remainder below 3/1001!<2^-8500.
Negative reduced arguments use outward reciprocals.

Writing u=2^-4352, term-width recurrence for atanh contracts by less than
1/8 after each product; including division rounding, a term width is below
32 u. Summing 1400 terms, scaling by two and allowing the input-division width
gives less than 2^18*u. Multiplication by the largest decoded exponent
(less than 2^15) gives logarithm width below 2^34*u. Exp reduction multiplies
the logarithm-of-two interval by k<24000; its endpoint error is below 2^34*u.
The Taylor recurrence, including 1000 directed divisions, gives endpoint
error below 2^38*u. These are conservative bounds, rather than observed
accuracy measurements.

For finite power with base other than one, the smallest nonzero magnitude
of log(abs(base)) exceeds 2^-1075: the closest DD base to one differs by
2^-1074, and the single-format gaps are larger. A power argument that can
remain in the evaluated exponential range therefore has exponent-parameter
leading exponent at most 1090. Normalized multiplication and rescaling give
argument width below 2^1125*u, and combined exponential width below
2^1128*u relative to its binary scale. At the largest DD finite output,
the absolute enclosure width is below 2^-2200, much smaller than the
absolute DD minimum gap 2^-1074. Single formats retain over 3000 spare bits
relative to their normal gaps; at gradual underflow the exact wide output
grid reaches 2^-32988. Thus these fixed iteration and precision bounds are
complete for the supported inputs; there is no unchecked precision fallback.
The final finite result is checked against both actual neighbors after any
single candidate correction. An impossible internal certificate failure
traps instead of substituting a numerical answer.

For log1p/expm1 inputs below 2^-128 in single formats, returning the exact
operand has quadratic error below 1/8 of a local gap. DD uses the stricter
2^-550 threshold, whose quadratic error is below its absolute minimum gap.
This path retains binary128/extended80 minimum subnormals, including inputs
far below the absolute fixed-point floor. Tiny exp/pow arguments below
2^-1100 return one with inexact; their changes are inside both neighbors.

Exact identities bypass intervals: powers of two for exp2/log2, exact
positive powers of ten for log10, and representable dyadic powers. Power
first classifies all signaling/malformed operands, then applies quiet-NaN
unit/zero identities, signed zeros/infinities and poles. A finite negative
base requires an exactly integral exponent; parity is read from its complete
integer encoding. Exact dyadic roots of an odd significand are established
by restoring integer square roots before exponentiation. Negative or
fractional exponents do not pass through a narrowed integer cast.

Nonexact finite outputs add inexact, and nonexact rounded tiny outputs add
underflow/inexact. DD rounded-result tininess uses 2^-969. Exact representable
roots, powers and identities add no rounding flags. Pole/domain cases add
divide-by-zero/invalid as specified by their counterparts; all NaNs are
canonical positive quiet NaNs. Hypot lets infinity dominate a quiet NaN only
after signaling/malformed priority. Incoming flags, errno and controls are
preserved. The kernels allocate no heap and have no mutable global state.

The eleven-family corpus, hash, mandatory pinned MPFR/mpmath oracle and
separate raw/ABI probe are independent of the legacy corpus-hash CLI and
its unchanged stdout. Reconstruction creates only a missing cache using
atomic linking; an existing corrupt cache fails unchanged. Coverage and
executed compiler/target evidence are recorded separately as validation is
completed; the preceding foundation-family execution counts do not claim
execution of these eleven APIs.

The supported allowance for this family is **2 MiB of usable thread stack**;
a smaller stack is not claimed. GCC 14 stack-usage measurements sum every
production function frame conservatively to 595,136 bytes atO0 and 297,672
bytes atO2; the largest individual frames are 58,032 and 54,080 bytes.
SeparateO0/O2 threads with exactly 2 MiB of writable stack and inaccessible
guard pages at both ends execute all eleven native calls and the DD
near-unit/minimum-tail witnesses. The integer call graph is acyclic, scratch
arrays are fixed, and the wrapper's explicit stack reservation is bounded.

Focused verification executes 642 pinned synthetic cells and 159 native80
literal cells with GCC 14, plus 7,986 mixed synthetic/native80 state calls.
GCC 14 O0, Clang 19 O2, Clang 19 ASan/UBSan and the compiler-selected binary64 and
binary128 ABI builds each execute their 159 native literal cells. Independent
exact integer calibration checks 1,485 signed directed add/multiply/divide/shift
cases, including zeros, carry and sticky boundaries. The required host target
`make check-long-double-eleven-oracle` checks the public pinned runtime
versions, recomputes all 642 cells with directed MPFR and independent mpmath,
and checks a fresh 44-cell production population. Absence or a version mismatch
fails that target. Rebuilt images with the same public runtime pin are accepted;
immutable identities are recorded only in private validation evidence.
The frozen default probes remain container-free; host oracle validation is a
required separate step before the cold default suite.

| Executed target ABI under GCC 16/QEMU | Native literal cells | Additional targeted native state/special calls |
| --- | ---: | ---: |
| PowerPC32 IBM DD | 165 | 284 |
| PowerPC64 IBM DD | 165 | 284 |
| ARM64 binary128 | 159 | 228 |
| s390x binary128 | 159 | 228 |
| SPARC64 binary128 | 159 | 228 |
| i686 extended80 | 159 | 272 |

The additional calls cover negative zeros/infinities, infinity to negative
powers, all eleven raw signaling/malformed priorities, exact exp2 range
boundaries, repeated odd-significand roots and DD remote-tail exponent parity.
They vary rounding controls, precision settings, incoming flags and supported
DAZ/FTZ. Host binary64/binary128 ABI builds execute 228 such calls each, and
Clang ASan/UBSan executes 272 native80 calls. Native80 byte callers avoid operand
loads through x87 on both AMD64 and i686; full wrapper operands, helper targets,
stack restoration and CFA rows are checked for both ABIs. Target execution is
under emulation; physical execution on these six target machines is not claimed.

Clean controls pass before five compiled numerical defects and five compiled
arithmetic/control/wrapper/unwind/caller defects are rejected. An additional
i686 wrong-slot and wrong-CFA object pair is rejected, alongside mocked frame
and instruction fixtures. Cold, warm and racing preparation, unchanged corrupt
caches, bounded canonical fields and optimized-Python rejection are checked.
Injected short/corrupt writes and flush/fsync/close failures publish no cache and
leave no temporary file. A deliberately wrong answer with its JSON, hash and
source pin all repinned passes structural loading and is then rejected by the
independent numerical oracle. The complete 38-member archive partition and
namespace/host-math gates pass. The unchanged legacy CLI still emits exactly its
original 7,319 bytes, with aggregate `f5fa269eb60ee34f` over 292,711 results and 122
function sets. Focused records retain failed tool/calibration attempts separately;
default-suite evidence is reported separately.

The original 642 literal cells remain unchanged. A separately pinned supplement
adds 184 directed-MPFR-certified adjacent transition cells for exp, expm1 and
power, including signed odd powers, plus finite hypot overflow. The first 148
answers are preserved; 36 additional positive-base-two cases cover fractional
exponents around overflow, half-minsub and minimum-normal transitions. Required
oracle verification regenerates the complete input registry; default checks
reject duplicate or incomplete per-format/function populations. Supplementary
transcendental checks use the selected result's actual neighbor enclosure and
selected-result tininess, rather than requiring correctly rounded results.
`make validate-long-double-eleven-host` executes the required host oracle target
and then the default suite, stopping before the suite if the oracle fails.
`make test` itself remains container-free.

The primitive calibration and O0/O2 guarded-stack fixtures are committed and run
from the eleven-family controls target. Primitive checks run wherever the
supported C toolchain is available; the guarded pthread/mmap fixture explicitly
reports unsupported platforms outside Linux. Default controls also exercise a
fresh container-free population using exact dyadic identities and rational
series bounds, independently of the required separate MPFR preflight.

GCC16.2.0 focused verification also passes both family targets under the
repository's default strict warning flags: 826 synthetic cells, 205 native80
cells, 8,394 state rows, compiled faults, 1,485 primitive cases and guarded
O0/O2 stacks. The first cold default attempt stopped on a warning in an injected
mutation before that gate's intended assertion. A local volatile read repairs
the test without disabling warnings; the failed attempt remains failed and
retained. The fresh cold GCC16.2.0 default retry passes all 116 gates and
45 main binaries: 294 tests, 293 passes and one expected native32 long-width
skip, in 6,234.93 seconds. The tracked source and index stayed frozen throughout.
After the run, all 8,637 build records were archived and the gzip CRC and tar
inventory verified; temporary builds and all nine generated corpus caches were
then reclaimed, followed by another frozen-source check. Every prior runtime,
table, literal corpus and legacy hash output remains unchanged. Optional older
nested-container oracle checks retain their explicit skips; the required oracle
checks for this family passed separately. No new format deferral was introduced.
