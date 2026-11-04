# Native long-double scaling and adjacent values

`gmath_ldexpl`, `gmath_scalbnl`, `gmath_scalblnl`, `gmath_nextafterl` and
`gmath_nexttowardl` support binary64, extended80, binary128 and IBM double-double
(DD). They use the foundation byte adapters and exact bounded integer dyadics;
no input or numerical decision narrows through double. DD `frexpl` remains
unavailable. The foundation NaN, malformed encoding, finite DD range and native
padding rules apply unchanged.

Scaling computes the exact native component sum times a power of two, then
rounds once to nearest, ties to even, independently of the caller's mode.
Comparisons against bounded terminal exponents precede narrowing native `long`
values, negation and shifts. For single formats, the cut is computed on the
unshifted input, retaining guard/sticky and parity even when the exact scaled
value lies below the bounded dyadic grid. DD retains sticky information below
its much higher minimum-subnormal grid before searching representable sums.

Exact finite/subnormal scaling adds no flags. Inexact results add IX; tiny
rounded zero/subnormal results add UF/IX; overflow returns signed infinity with
OF/IX. Tininess is tested after rounding. DD's minimum normal is **2^-969**,
not its binary64 leader's minimum normal. For example `(1,minsub)/2` returns
normal `0.5` with IX only, whereas adjacency around 2^-1000 adds UF/IX.

Equality in either adjacent API returns the destination value, including its
zero sign. Otherwise the result is the immediate representable neighbor toward
the destination. Zero steps to signed minsub; infinity inward steps to maximum
finite. Unequal zero/subnormal results add UF/IX even for exact steps;
finite-to-infinity adds OF/IX; other finite steps add none. Both operands of
`nexttowardl` already have native long-double precision.

Explicit helpers raise flags. errno, control registers and incoming standard
C flags are preserved. These are project policies; full host-libm errno and
directed scaling parity are not claimed. Native80 AMD64 wrappers pass incoming
object addresses to an integer byte engine and perform exactly one final
canonical `fldt`. Exact stack slots, exponent sign extension, helper call,
restoration, every unwind row and FDE coverage through the complete return
instruction are checked by the object gate. The four explicit flag helpers
are isolated with noinline boundaries; floating arithmetic, including SSE
arithmetic, is rejected outside those helpers. Control writes remain forbidden
everywhere, including s390 SFPC and ARM VMSR to FPSCR.

## DD coverage and rounding certificate

The population is sums of two finite binary64 values within the foundation
finite limit. It is not a uniform 106-bit lattice. Every such sum admits a
normalized encoding: take its nearest binary64 leader, clamped at DBL_MAX at
the finite limit; its residual is exactly binary64. To see why the residual is
representable, align the two original significands. If they overlap, subtraction
of their rounded sum cancels the leading bits, leaving at most 53 significant
bits. If they are separated, rounding selects the leading component and leaves
the other component (or, at its rounding boundary, the same bounded residual).
Subnormal residuals stay on the binary64 minimum-subnormal grid.

For a fixed leader, rounding the exact residual and taking its two immediate
binary64 neighbors brackets the requested exact value. A DD neighbor cannot
skip a complete leader rounding cell: the boundary is itself the sum of its
leader and a binary power residual. Consequently the containing leader cell
and its boundary cells suffice. The implementation conservatively includes
RN64(x) and two leaders on either side. Its fifteen candidates therefore
contain the closest DD value on each side, including residual zero, separated
tails, cancellation, binade changes and midpoint seams. Candidates outside the
finite range are excluded. Integer distance comparisons select the nearest;
ties use the bit at the actual power-of-two gap, rather than an assumed global
precision. At the finite endpoint the virtual successor spacing is 2^917,
so the nearest overflow threshold is maximum DD plus 2^916.

The Fraction oracle independently uses rational division and three leader
cells. In addition, **an interval certificate does not use a candidate radius**:
monotonicity of RN64 bounds every possible normalized leader between RN64 of
the two interval endpoints. It walks that entire leader range and, for each
leader, finds the first binary64 residual strictly above the lower endpoint.
If that sum is below the upper endpoint the certificate fails. Adjacent pairs
have no interior sum; rounded results have no interior sum in the open interval
between the result and its reflection across the exact answer. This separately
checks that a candidate search did not miss a closer or intermediate value.
A separate closed-endpoint check decodes the reflected endpoint's nearest leader
and verifies its residual exactly. When that endpoint is representable, the
chosen result must have an even integer coefficient in the actual gap. Eight
independent positive/negative certificate controls cover normal IX-only and
tiny UF/IX ties, both signs and both lower-even/upper-even outcomes.

## Evidence and limits

Bulk probe runs preceding the external-caller correction below included public
wrapper definitions in the caller translation unit. Those artifacts are retained
as **inline-capable numerical/state evidence**, not proof of an external public
ABI call. The latest separate-object runs below supersede their ABI claims.
The independently linked literal corpus client did not have this problem.


The separate committed corpus contains 5,289 binary64, 5,418 extended80, 5,332
binary128 and 6,149 DD cases. It leaves the foundation and Float/Double corpora
unchanged. The native client checks literal bits, flags, errno, mixed controls,
strict token ranges, all four literal populations and hashes. Integrity hashes
now include format, operation, both operands, exponent, mode, precision setting,
incoming flags, result and outgoing flags, each as little-endian uint64 (signed
exponents sign-extended). Foreign-format rows remain bound to all their semantic
inputs even when the native client skips execution. The oracle parses and
recomputes every committed result/flag and checks fixed populations independently
of fixture generation and JSON SHA pins. Literal corpus rows are unchanged;
only the new-family hash file and its JSON digest changed. The oracle labels
synthetic format adapters separately from actual native ABI calls. Actual
native-long minima/maxima are supplied according to the probe's compiled width.

Focused compiler, sanitizer, emulated ABI and planted-defect results are
recorded after execution; a full default suite is reserved for the reviewed,
frozen family. Emulated ABI execution is not physical-host or full GoogleTest
evidence. The library's existing unrelated numerical policies remain unchanged.

Initial pre-review focused execution completed with GCC16: 22,204 synthetic rational rows and
5,420 native extended80 ABI rows, two new unit tests, fourteen new compiled
faults, six corpus/hash corruptions and eleven malformed probe inputs. The
unchanged foundation checks also pass: 10,449 synthetic rows, 2,592 native
rows, three unit tests, thirteen compiled faults and two archive population
faults. The complete archive gate covers 36 objects: 34 unchanged legacy
members, the foundation and the new family. Symbol/header hygiene passes.

The initial Clang and Clang ASan/UBSan runs each passed a larger 71,732-row synthetic sample and
17,804 native80 ABI rows. Compiler-selected native binary64 and binary128
modes pass 17,675 and 17,718 native rows respectively, plus the same synthetic
sample. All five native80 wrappers pass strict object/CFI inspection, including
the sanitized object. Initial focused attempts failed a compiler warning and
a planted-control diagnostic assertion; corrected reruns pass. Sanitizer
metadata initially triggered duplicate-marker detection; exact symbol selection
fixes that gate, while compiled missing/wrong and duplicate marker controls
continue to reject.

The initial six GCC16/QEMU ABI probes and their object gates passed. PowerPC64 and PowerPC32
exercise DD with long64 and long32 respectively (6,159 native rows each).
AArch64, s390x and SPARC64 exercise binary128 (5,334 each); i686 exercises
extended80 with long32 (5,420). Each run also checks the four synthetic adapters
and actual native-long extrema; these are emulated ABI results. Every owned
cross build was archived, gzip/content-inventory checked and reclaimed.

The existing aggregate remains `f5fa269eb60ee34f` over 292,711 results and 122
function sets. The baseline and updated corpus-hash programs produce exactly
the same 7,319 stdout bytes; the new literal corpus validates quietly. No full
default suite has been run for this family during implementation: review,
freeze and that single final execution remain the final acceptance step.


### Focused review-fix validation

The affected GCC16 oracle now passes 23,924 synthetic rows and 5,804 native80
rows, plus recomputation of all 22,188 committed answers and both unit tests.
The 1,728 bounded boundary witnesses repeat identical operands across all four
rounding modes, three x87 precision settings and separately clear/preseeded
flags. Only divide-by-zero is preseeded, so required IX/UF/OF/invalid cannot be
masked. DD midpoint witnesses include both signs and lower-even/upper-even
results, with normal IX-only and tiny UF/IX outcomes. Native exponent-extreme
unit assertions inspect raw zero/infinity encodings for both input signs.

Seventeen host compiled faults reject, including DD tie selection, SSE
arithmetic in the byte engine, and a real shortened ELF FDE with unchanged
unwind rows. Twelve native-client corruption controls reject, including
parse-valid foreign-format operation/operand/control edits. A wrong answer
with updated SHA metadata fails independent rational recomputation. Fourteen
malformed byte inputs reject, including embedded NUL at final EOF; hash/corpus
readers reject NUL and overlong records using byte-counted bounded reads.
Initial-header and payload hangs are killed and reaped at bounded deadlines;
a separate controller timeout control exercises its own kill/reap path.

Affected Clang and Clang ASan/UBSan probes/object gates pass the same 23,924
synthetic and 5,804 native80 rows. Compiler-selected native64 and native128
probes/object gates pass 5,675 and 5,718 native rows respectively. The six
GCC16/QEMU reruns and object gates also pass: DD PowerPC64/32 each has 6,727
native rows (long64/32), binary128 AArch64/s390x/SPARC64 each has 5,718, and
i686 native80 has 5,804 (long32). A compiled s390 SFPC fault rejects on its
actual target object. ARM VMSR/FPSCR guards have synthetic parser controls;
no ARM32 execution is claimed. Bad intermediate unwind rows and shortened
ranges also have independent parser controls.

Only affected family checks were rerun after review. The preceding larger
samples, foundation/archive checks and stdout comparison above remain earlier
evidence. Failed attempts are retained. Review-fix build archives were verified
before reclamation; full default validation and a local commit remain outside
this implementation handoff.


### External caller correction

The synthetic adapter now includes the shared implementation under a private
`GMATH_LONG_DOUBLE_SCALE_RAW_ONLY` guard, which omits both the byte engine and
public wrapper definitions. All five native calls therefore resolve from a
separately compiled real production object. Make and numerical fault-control
builds compile caller and production separately, with LTO disabled at compilation
and linking. Numerical mutants alter the appropriate production source as well
as the synthetic adapter; the byte-engine state fault now fails in the appended
native batch, demonstrating that it reaches the separately linked implementation.

A caller-object gate requires five undefined public symbols and five target
relocations, rejects public definitions/private byte-engine references/LTO, and
requires actual call/jump instructions on x86. Caller, production and linked
symbol/disassembly records retain the evidence on every tested ABI. A compiled
RAW_ONLY guard fault is rejected. Eighteen host compiled faults now reject;
the preceding seventeen controls retain their intended rejection reasons.

The exact updated Make recipes pass GCC16 native80 checks: 23,924 synthetic
rows, 5,804 true external native rows, and recomputation of all 22,188 committed
answers. GCC16 production objects before/after the guard correction are
byte-identical after debug/build-ID removal, including code, data, relocations
and unwind sections. Clang and Clang ASan/UBSan pass the same true native80
population. GCC16 compiler-selected binary64 and binary128 modes pass 5,675 and
5,718 external native rows. All have five external public call relocations;
in particular, binary64 no longer calls the private engine from its caller.

The six GCC16/QEMU separate-object probes and caller/production gates pass:
PowerPC64/32 DD each has 6,727 external native rows (long64/32),
AArch64/s390x/SPARC64 binary128 each has 5,718, and i686 native80 has 5,804
(long32). These are emulated ABI results, separate from physical-host evidence.
The default gate exercises the same external-caller link path. No wider suite or
full default run was performed for this correction. Previous inline-capable
runs remain preserved; all new owned builds were archived and verified before
reclamation.

### Focused minnormal seam addition (P2)

The boundary matrix now also contains raw `(2*N-k*q, -1)` scaling inputs,
where N is the format's minimum normal, q its minimum subnormal and k is 1, 3, 5.
Both signs repeat across every existing mode/precision/clear-vs-preseed setting.
For k=1, the exact midpoint rounds to N with IX only; the neighboring tiny
midpoints k=3/5 round to N-2*q with UF/IX. Exact raw input reconstruction and
these two explicit flag requirements are checked independently of the probe.
This adds 576 rows (144 per format), bringing the integrated boundary matrix
from 1,728 to 2,304. Committed literal rows and their hashes are unchanged.

Only the added witnesses and their new fault were executed for this addition.
The 11 retained true-ABI executables were extracted from verified archives:
GCC16/Clang/ASan native80, GCC16 selected64/128 and the six QEMU targets. Each
passes 576 synthetic and 144 matching native rows. Every format's synthetic
outcomes contain 48 rounded-minnormal IX-only cases and 96 neighboring tiny
UF/IX cases; matching native outcomes have the same 48/96 split. These cases
cover both signs, all four modes, three precision settings and clear versus
separately preseeded flags. Previous broad counts above remain prior evidence;
no broader matrix was repeated or claimed for the expanded boundary set.

A new compiled flag fault raises UF only in the inexact-scaling branch when
the rounded result is exactly minnormal. Exact scaling, other normal values and
adjacency cannot trigger it. Using retained unmodified caller objects keeps the
synthetic path correct; the new IX-only witness rejects the fault in the native
batch for GCC16 binary64, extended80 and binary128. In all three negative runs,
row 576 returns the correct minnormal bits with flags 12 instead of 4 (UF/IX
instead of IX). The default controller includes this additional fault, but only
this fault was rerun here; previous control results remain earlier evidence.
Production sources, public caller binaries and literal answers were unchanged.
Extracted executables/objects and fault builds were archived, verified and
pruned after the focused checks. No full default suite or commit ran.

### Completed default verification

One cold default GCC16 `make test -j1` exits zero on the reviewed frozen family.
All 112 default gates run, including all 110 preceding gates in their original
order. All 43 main binaries run 290 tests: 289 passes and one expected
native32-long skip. The integrated new-family check executes 24,500 synthetic
rational rows and 5,948 external native80 rows, including the full 2,304-row
boundary matrix; every 22,188 committed answer/flag and semantic hash is recomputed.
All 19 compiled host defects and the byte, integrity, deadline, caller and unwind
controls reject as intended. The default gates retain their explicitly reported
optional oracle skips; this does not claim additional oracle execution.

All 56 pre-existing runtime/table paths, 133 previous corpus files and all
original file modes remain unchanged. Staged privacy/diff checks pass. Frozen
tracked bytes, index, worktree and HEAD remain unchanged before/after validation
and after cleanup. Build log/result records were archived, gzip CRC/tar inventory
verified, then bulky builds and generated cache copies reclaimed. Earlier failed
focused attempts remain failures; inline-capable earlier results retain their
numerical-only classification. The separate suite archive-caller coordination
remains outside this math-only change.

x87 precision-control and mixed-MXCSR settings apply on x86. On non-x86 targets,
the PC fields are repeated fixture tags, not additional native precision modes.

Library and caller must use the same native long-double ABI and compiler ABI
flags. Compiler-selected binary64/binary128 modes are separate builds; they
cannot be mixed with an extended80 library. See the [foundation contract](long-double.md)
for native padding, malformed encodings and ABI status-bit limits.
