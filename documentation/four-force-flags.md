# Exception-force verification for four Float functions

`make check-four-force-flags` separates two kinds of evidence:

- **Natural public calls:** 5,760 cases exercise the production archive through
  a separately compiled, non-LTO caller. Selected ordinary, tiny, exact and
  special inputs run in all four rounding modes and all 32 incoming flag subsets.
  Required exception flags, errno and control preservation are asserted.
- **Calibrated call sites:** five staged source variants cover expf/exp2f's
  subnormal UF/IX forces, atanf's final IX force, and cbrtf's final and subnormal
  IX forces. A test-only callback records the flags already present, clears only
  the relevant flags immediately before the selected force, and counts hits.
  Positive controls must restore the exact required flags and match the natural
  public result bits. Identical variants deleting only that force must fail the
  flag assertion while retaining result bits and passing state/path checks.

The calibrated positive populations contain 768 cases per compiler profile.
Incoming flags affected by injection are excluded from calibration; unrelated
incoming flags are retained. Natural calls independently test preservation of
all incoming subsets. Missing/duplicate records, missed call sites, wrong state,
compile/link errors, crashes and timeouts cannot count as mutation detection.
The gate records pre-injection flags, every deletion row, compiler identity,
compile/link flags and the production archive SHA256 in its JSON result.
All injection remains in temporary test sources; production never clears flags.

The historical gaps were not four demonstrated numerical defects. In particular,
expf/exp2f have no separate normal-result IX force: their arithmetic establishes
IX, and their additional subnormal force conservatively adds UF/IX. Prior
exhaustive subnormal scans found flags already set by narrowing. Likewise,
atanf/cbrtf arithmetic can mask removal of a final IX force. Calibration verifies
that each explicit force independently fulfills its obligation if earlier flags
are absent. It does not manufacture a natural, uninstrumented deletion witness,
prove redundancy on every compiler, or establish exhaustive numerical accuracy.
The earlier scan and natural-mutation limits remain historical evidence.

Focused GCC16 O2/O0 and Clang checks pass both populations and reject all five
calibrated deletions. Existing numerical corpora and runtime sources are unchanged.
The normal default suite includes this gate; broader family accuracy/state tests
remain separate and mandatory. No performance or new platform claim is made.
