# Long-double integer arithmetic

Nine native APIs add exact integer decisions for conversions, remainders,
positive difference and explicit fused multiply-add. Binary64, extended80 and
binary128 provide all nine. IBM double-double provides the four conversions,
fdiml and fmal. GMATH_HAVE_FMODL, GMATH_HAVE_REMAINDERL and GMATH_HAVE_REMQUOL
are zero on DD, with no declaration or definition for those operations: an
exact remainder of two DD values need not be a sum of two binary64 numbers.
A rounded substitute would violate the exact remainder contract.
For example, x=1+2^-200 and y=3/4+2^-100 are both DD values. Both quotient
rules select one, leaving 1/4-2^-100+2^-200. Its nearest binary64 leader is
1/4, whose residual needs100 significant bits. Every sum of two binary64
values admits a nearest binary64 leader with an exact binary64 residual;
this remainder therefore has no DD representation.

The existing foundation/scaling modules, tables and reference populations are
unchanged. New code lives in long_double_nine.c and long_double_nine_bits.h;
it reuses the existing raw decoder, canonical packer and DD population helper.
No host math implementation supplied algorithm source or runtime results.

## Numerical decisions

The conversions inspect the exact decoded magnitude. The binary point splits
its integral low 64 bits from the fractional remainder. lround/llround increment
at a half tie; lrint/llrint use the caller's direction with even nearest ties.
A checked unsigned magnitude admits the asymmetric destination MIN endpoint
without signed overflow. Range checking follows rounding and precedes any IX.
Nonfinite/out-of-range results return destination MIN and add invalid only;
valid current-mode fractions add IX, whereas lround/llround never do.
Native long32/long64 and signed64 long long are supported. Extended80 reads x87
RC independently of MXCSR and x87 PC24/53/64; other formats use the established
native control reader. No control write occurs in production.

For single-format remainders, normalized significands of at most113 bits feed
a four-limb positional division. Each quotient bit advances the low-seven-bit
accumulator, including zero bits after an exact residual. fmod truncates;
remainder/remquo compare twice the residual against the divisor and use quotient
parity for half ties. The residual is exactly representable, including minsub,
so no valid call adds flags. Exact zero retains the original dividend sign.
remquo writes the signed quotient magnitude modulo128, or omits it for NULL.
NaN/domain results deterministically write quotient zero. Both operands are
classified for signaling NaNs before any special return.

FMA uses 2064 unsigned32 limbs on a 2^-32988 grid: binary128 minsub squared fits
at the low endpoint, and products below 2^32768 fit at the high endpoint.
Schoolbook integer multiplication followed by signed magnitude addition forms
the exact result before rounding. This avoids intermediate overflow, underflow
and double rounding. fdim uses the same exact sum representation with a negated
second operand and rounds once nearest/even, independently of caller mode.

Single-format results round on their own precision and subnormal grid. DD
results use the union of sums of two binary64 components. Their nearest leader,
residual and neighboring candidates establish nearest rounding; strict upper
or lower brackets supply directed rounding. DD is never modeled as fixed106
precision. The independent rational interval certificate enumerates all leader
cells meeting an interval and proves that no interior representable sum exists.
Tie parity is measured in the actual gap unit. The terminal finite DD spacing
is 2^917; the virtual next value and its halfway point determine overflow.
The minimum normal DD magnitude is 2^-969. Underflow uses rounded-result
tininess and requires inexact. Exact finite/tiny results add no flags.

Special priorities match the existing Float/Double FMA policy: a signaling or
malformed operand, or an infinity-times-zero product, raises invalid even when
another operand is a quiet NaN. A quiet NaN otherwise propagates canonically
before conflicting infinities are considered. Opposite infinite product/addend
signs are invalid. Exact cancellation is -0 in downward mode and +0 otherwise;
matching signed product/addend zeros retain that sign. All APIs preserve errno,
controls and incoming standard flags. Native80 returns may set architectural
(nonstandard) denormal status, as documented for the existing foundation.

## Verification and boundaries

The independent Fraction oracle recomputes every committed answer cell and
every expanded state row, including raw malformed encodings, all operands,
mode, precision control, incoming flags, destination width, results and quotient
bits. There are8,421 literal answer cells (612,833 bytes), preserving the seeded
and fixed per-input answers. A deterministic recipe expands them to77,016 rows
(22,257,624 bytes) in an ignored cache at the ordinary loader path. The complete
cache SHA256 and per-format/native-width hashes are committed. All previous
40,268 rows remain a byte-identical prefix of the expanded population. Fixed-width record parsing rejects
NUL, missing LF, overflow tokens, extra fields and foreign-format invalid rows.
Per-format/native-long-width hashes include all input, state and output fields;
complete SHA256 metadata and independent population reconstruction protect bytes.
Repinning a wrong literal or a wrong expanded answer still fails rational
recomputation. `make prepare-corpora` and `tools/prepare-long-double-nine.py`
reconstruct a missing cache from the literal cells; an existing corrupt cache
fails without repair. Publication requires a complete write, successful flush,
fsync and close, and a matching temporary length/SHA before an atomic no-replace
link. An appearing cache is checked rather than overwritten. This provides
ordinary failure/race integrity, not a multi-file crash transaction.

A separate caller object is compiled without LTO and actually calls production
public functions; synthetic adapters supplement native ABI evidence. The
x86-64 native80 caller copies argument bytes using integers, with no input
fldt even at O0; its only x87 transfer stores the final ABI return. Strict Clang
may emit fwait immediately after fnstcw; the gate permits only that reader-local
pair in production. The object
gate bounds floating arithmetic to isolated exception helpers, rejects control
writes, checks native80 return slots and every CFA row, and verifies external
caller relocations. The complete archive partition retains the unchanged legacy
instruction gate on every older member. Default gates run numerical/native
checks and compiled defect/loader controls. The aggregate corpus probe consumes
the new native literals without changing its previous output hash population.

Focused GCC/Clang, sanitizer and six QEMU native ABI results are recorded in
libm-progress.md. The raw probe captures actual seeded entry flags, requires
clear-entry flags to be zero and validates operation flags against the union of
that entry state and the independent reference. Observed input/state/output
SHA256 records supplement the portable literal-state hashes. Unrun physical hosts, Windows/LLP64, exhaustive encodings and
performance are not claimed. These are exact-operation contracts and sampled
implementation checks, not complete libm behavioral parity. Consumer and suite
migration remain separate work.


## Usable stack and x86 denormal controls

These nine APIs require at least2MiB of unconsumed usable stack at entry;
guard pages are additional. Small-thread-stack execution is outside the
supported contract. No arithmetic or allocation strategy changes to enforce
this caller requirement. The fixed integer arrays and decoded values explain
the requirement; it does not depend on input exponent or division-loop length.

On x86-64 GNU/Linux with GCC14.2, `-fstack-usage` reports largest frames of
58,032 bytes at O0 and45,744 at O2 for production plus the four-format synthetic
client. Conservatively summing every reported frame across both translation
units, including mutually exclusive paths, gives482,400/233,896 bytes. The
helper graph is acyclic. The focused gate rejects unbounded frames or an
all-frame sum reaching1MiB, leaving at least another1MiB of the supported budget
for caller/runtime overhead. A pthread with exactly2MiB supplied memory and
inaccessible pages at both ends exercises all formats, all nine native APIs
and nested DD population paths at O0/O2. These measurements cover the stated
compiler/ABI, not every platform or sanitizer-inflated stack frame.

The separate focused state probe enables supported DAZ-only, FTZ-only and
combined MXCSR profiles, checks subnormal values/flags/errno and unchanged
controls, and restores the original environment. It covers the four integer
adapters plus actual native80 and compiler-selected native64 ABI calls. One
FTZ-conditional compiled defect must reject. These profiles run once per
focused gate, rather than multiplying every corpus or arithmetic mutation.

The selected compiler target macros gate the POSIX pthread/mmap harness.
Non-POSIX targets explicitly skip that harness while retaining compiler stack
usage measurement; Windows/LLP64 execution remains unrun.


## Completed default verification

One reviewed cold default GCC16 `make -j1 test` exits zero. All 114
default gates run, preserving the preceding 112 gates in order. All 44 main
binaries run 292 tests: 291 pass and one expected native32-long test skips.
The new gate independently recomputes all 8,421 literal answer cells and 77,016
expanded rows and verifies 15,513 native80/long64 ABI calls. Arithmetic, state,
ABI, cache and configuration controls retain their focused rejecting cases.

All 58 earlier runtime/table paths, 136 existing corpus files and every original
file mode remain unchanged. The canonical legacy corpus-hash population remains
unchanged. Source bytes, index, worktree and HEAD were frozen before/after the
run and checked again after cleanup. Build log/result evidence was archived,
gzip CRC and exact tar inventory verified, then bulky builds and eight generated
cache copies reclaimed. Earlier failed/interrupted focused attempts remain
failures, with primary logs and verified archives retained. Optional oracle
skips remain explicitly labeled; this does not claim additional physical-host,
Windows/LLP64, exhaustive, performance or full-libm behavioral verification.
