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
