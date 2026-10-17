# Design

**Status:** `sin`, `cos` and `tan` are implemented (part 1 of CAP-1).
`atan2`, `exp`, `log`, `pow` and `hypot` are not.

Deterministic elementary functions that give the same bits on every host.

The dependency rules and the determinism gates that bind this library are in
the Makefile's header comment and in `tools/`: `check-fp-contract`,
`check-edges`, `check-libm` and `check-no-x87`, each shown to fail on a planted
violation by `make check-gates`. The plan is in the workspace, not in this
repository.

## sin, cos and tan

Written from published algorithms and the oracle's results only; no library's
source was read.

**Reduction.** For `|x| > pi/4`, `x * 2/pi` is formed exactly enough by the
Payne-Hanek method (Payne and Hanek, 1983): the integer-valued bits of `2/pi`
beyond the window that can matter are multiples of 4 and dropped; a 256-bit
window of the bits below is multiplied by `x`'s 53-bit significand in 32-bit
limbs with 64-bit products. That gives the quadrant (`N mod 4`, with the
fraction rounded to the nearest integer) and a 256-bit fraction in `[-1/2, 1/2]`,
whose leading 106 bits times `pi/2` (a double-double) give `r = rh + rl`,
`|r| <= pi/4`, to a relative error of about `2^-100`. The smallest fraction any
double has is about `2^-61` (`6381956970095103 * 2^797`), so the window's
truncation error of `2^-168` is far below one ulp of the result. Only integer
arithmetic is used: a 128-bit type is not available on i686 and an integer to
double conversion compiles to an x87 `fild` there, which `check-no-x87` refuses,
so a 53-bit integer becomes a double through the bit pattern of `2^52 + k`.
The table is indexed from the exponent of `x`, so `|x|` up to `DBL_MAX` takes
the same code as `|x| = 1`.

**Fast reduction.** For `pi/4 < |x| < 2^20` the quotient is one multiplication
(`n = round(x * 2/pi)`, taken through the `2^52 + 2^51` trick, which needs no
integer to double conversion) and the remainder is `x - n*P1 - n*P2 - n*P3 -
n*P4` with `pi/2 = P1 + P2 + P3 + P4`, `P1..P3` of 33 bits and `P4` a double
(Cody and Waite, 1980). Every product with `P1..P3` is exact because `n` has at
most 20 bits, `x - n*P1` is exact, and the sums are Knuth's TwoSum, so the
remainder is a double-double accurate to `2^-134` absolute. That is
`2^-79` of the remainder or better for `|r| >= 2^-55`, and the fast path hands
anything smaller (no double below `2^20` is closer than `2^-60` to a multiple
of `pi/2`) to Payne-Hanek, as it does a quotient the rounding put one off
(`|r|` above the double `pi/4`). Where it answers it returns the same `n` and
the same `rh` as Payne-Hanek and an `rl` that differs by under `2^-79 |r|`
(measured at most `2^-87`), so the results are the same bits: the committed
hash over the original 46,569 results did not change. `trig.c` states the
proof, `test_trig_reduce.cpp` compares the two reductions, and `make bench`
times them.

**Kernels.** `sin r = r - r^3/6 + r^5 S(r^2)` and
`cos r = 1 - r^2/2 + r^4/24 + r^6 C(r^2)`, with `r^3/6`, `r^2/2` and `r^4/24`
carried as double-doubles (Dekker's product and Knuth's sum, error-free without
a fused multiply-add) and only the small remainder in plain double. `S` has
degree 6 and `C` degree 5, fitted by `tools/oracle/fit_coeffs.py` against the
Taylor series at 400 bits to a worst weighted error of about `2^-75`, then
rounded to double. The first cos kernel kept `r^4/24` in plain double and measured
0.56 ulp; carrying it as a double-double brought the corpus maximum to 0.503.
`tan` is the double-double quotient of the two kernels (or its reciprocal and
negative for an odd quadrant), so its error is one final rounding plus about
`2^-60`.

**Special values.** `|x| < 2^-28` returns `x` for `sin` and `tan`, and `|x| <
2^-27` returns 1 for `cos`, which is within the contract and is exact for
subnormals and zeros. An infinite or NaN argument gives the quiet NaN
`0x7ff8000000000000` on every target (the sign and payload of the NaN an IEEE
operation makes differs between x86 and the others, so it is fixed), and an
infinity raises invalid.

**Checks.** See the README. The unit test holds the committed corpus to 0.52
ulp as well as to the contract of 1, so that a coefficient perturbed in its
last place is seen; the committed hash catches what even that cannot.
