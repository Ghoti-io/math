/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Copyright (C) 2026 Corey Pennycuff
 *
 * This file is part of Ghoti.io Math.
 *
 * Ghoti.io Math is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Ghoti.io Math is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/**
 * @file
 *
 * The two square roots, private to sqrt.c and hypot.c (a header, so that
 * hypot's use of the square root is inlined and the unit tests can include the
 * .c files as C++).  Both give the correctly rounded square root (to nearest,
 * ties to even; a square root has no ties), which IEEE 754 requires of sqrt, so
 * they give the same bits as each other and on every target.
 *
 * Hardware.  Where the target has a square-root instruction that rounds
 * correctly, it is used through inline assembly: x86-64 and i686 with SSE
 * math (sqrtsd), aarch64 (fsqrt), s390x (sqdbr), powerpc with the optional
 * instruction (fsqrt, when the compiler says _ARCH_PPCSQ), sparc64 (fsqrtd) and
 * riscv with a double-precision FPU (fsqrt.d).  Assembly rather than
 * __builtin_sqrt because the builtin is a call to libm unless the compiler is
 * told -fno-math-errno, and at -O0 it often is one anyway; an instruction
 * cannot become a call (AD-22; tools/check-libm.sh refuses every libm symbol).
 * The instruction gives the sign and payload of a NaN of its own choosing (x86
 * a negative one), so a NaN result is replaced by the library's quiet NaN.
 * -DGMATH_SQRT_PORTABLE turns the hardware path off, so a build can be gated
 * with each variant on every host.
 *
 * Portable.  Integer and double arithmetic only.  The argument is scaled by an
 * even power of two to m in [1, 4) (a subnormal first by 2^54, exactly), and
 * y = sqrt(m) is found in three parts (Muller, Elementary Functions, chapter 5;
 * Markstein's use of the exact residual):
 *
 *   r ~ 1/sqrt(m)     the table start (within 2^-10), then two Newton steps
 *                     (2^-19, 2^-38)
 *   s0 = m r          sqrt(m) to 2^-37
 *   c = s0 with 26 bits, so c^2 is one exact product, R = m - c^2 is exact
 *                     (a quantity of 2^-24), and
 *   y = c + R t       sqrt(c^2 + R) = c + R / (c + sqrt(c^2 + R)) exactly, and
 *                     t = (r / 2) (1 + (s0 - c) r / 2) is 1 / (c + s0) to
 *                     2^-52 (c is not s0: c + s0 is 2 s0 less 2^-26), so y
 *                     is the square root to within 0.5 ulp + 2^-61 y, and the
 *                     correctly rounded value is y or one of its neighbours;
 *   the choice        by the exact residual rho = m - y^2 = (m - p) - e with
 *                     p + e = y^2 (Dekker; y split into two halves of 26 bits
 *                     by rounding, so every partial product is exact).  m is
 *                     a multiple of 2^-52 and y^2 of 2^-104, so rho is a
 *                     multiple of 2^-104 of magnitude below 2^-51, exactly
 *                     representable, and with u = 2^-52 the spacing of y:
 *                       y rounds up   iff m > (y + u/2)^2  iff  rho >  y u
 *                       y rounds down iff m < (y - u/2)^2  iff  rho <= -y u
 *                     (the u^2/4 = 2^-106 in each is below the granularity of
 *                     rho and moves only the equality, which is what makes the
 *                     two asymmetric).  There are no ties: (y + u/2)^2 has 107
 *                     bits and m has 53.
 *
 * The result is y with the exponent restored: a square root is always normal.
 */

#ifndef GHOTI_IO_GMATH_SQRT_IMPL_H
#define GHOTI_IO_GMATH_SQRT_IMPL_H

#include <ghoti.io/math/macros.h>

#include "elem_common.h"
#include "hypot_table.h"

#if !defined(GMATH_SQRT_PORTABLE)
#if (defined(__x86_64__) || defined(__SSE2_MATH__)) && (defined(__GNUC__) || defined(__clang__))
#define GMATH_HW_SQRT 1
static inline double gmath_sqrt_instruction(double x) {
  double r;
  __asm__("sqrtsd %1, %0" : "=x"(r) : "x"(x));
  return r;
}
#elif defined(__aarch64__) && (defined(__GNUC__) || defined(__clang__))
#define GMATH_HW_SQRT 1
static inline double gmath_sqrt_instruction(double x) {
  double r;
  __asm__("fsqrt %d0, %d1" : "=w"(r) : "w"(x));
  return r;
}
#elif defined(__s390x__) && defined(__GNUC__)
#define GMATH_HW_SQRT 1
static inline double gmath_sqrt_instruction(double x) {
  double r;
  __asm__("sqdbr %0, %1" : "=f"(r) : "f"(x));
  return r;
}
#elif defined(_ARCH_PPCSQ) && defined(__GNUC__)
#define GMATH_HW_SQRT 1
static inline double gmath_sqrt_instruction(double x) {
  double r;
  __asm__("fsqrt %0, %1" : "=f"(r) : "f"(x));
  return r;
}
#elif defined(__sparc__) && defined(__sparc_v9__) && defined(__GNUC__)
#define GMATH_HW_SQRT 1
static inline double gmath_sqrt_instruction(double x) {
  double r;
  __asm__("fsqrtd %1, %0" : "=e"(r) : "e"(x));
  return r;
}
#elif defined(__riscv) && defined(__riscv_flen) && __riscv_flen >= 64 && defined(__GNUC__)
#define GMATH_HW_SQRT 1
static inline double gmath_sqrt_instruction(double x) {
  double r;
  __asm__("fsqrt.d %0, %1" : "=f"(r) : "f"(x));
  return r;
}
#endif
#endif /* !GMATH_SQRT_PORTABLE */

/* The low 27 stored bits cleared leave 26 significant bits. */
#define GMATH_SQRT_LOW27 0x7ffffffull

/* The estimate of sqrt(m) for m in [1, 4): y within 0.5 ulp + 2^-61 y of the root (see above). */
static inline double gmath_sqrt_estimate(double m) {
  double r = gmath_hypot_rsqrt[(gmath_bits(m) >> 44) & ((1u << GMATH_HYPOT_ROW_BITS) - 1u)];
  double hm = 0.5 * m;
  r = r * (1.5 - hm * (r * r));
  r = r * (1.5 - hm * (r * r));
  double s0 = m * r;
  double c = gmath_double(gmath_bits(s0) & ~GMATH_SQRT_LOW27);
  double hr = 0.5 * r;
  /* 1 / (c + sqrt m) = (r / 2) (1 + (s0 - c) r / 2) to 2^-52 */
  return c + (m - c * c) * (hr * (1.0 + (s0 - c) * hr));
}

/* The correctly rounded sqrt(m), m in [1, 4), from any y in [1, 2] that is the root or its neighbour either side
 * (both directions are used by the tests, though the estimate in practice only falls short).  y = 2 is allowed:
 * for m = 4 - 2^-51 the estimate may be 2, and the residual -2^-51 = -y u lowers it. */
static inline double gmath_sqrt_correct(double m, double y) {
  /* rho = m - y^2 exactly: y = yh + yl with yh the leading 26 bits rounded */
  double yh = gmath_double((gmath_bits(y) + 0x4000000ull) & ~GMATH_SQRT_LOW27);
  double yl = y - yh;
  double p = y * y;
  double e = ((yh * yh - p) + 2.0 * (yh * yl)) + yl * yl;
  double rho = (m - p) - e;
  double yu = y * 0x1p-52;
  if (rho > yu) {
    y += 0x1p-52;
  } else if (rho <= -yu) {
    y -= 0x1p-52;
  }
  return y;
}

/* The portable square root. */
static inline double gmath_sqrt_portable_impl(double x) {
  uint64_t b = gmath_bits(x);
  uint64_t a = b & GMATH_ABS_MASK;
  if (a >= GMATH_INF_BITS) {
    if (a > GMATH_INF_BITS) {
      return gmath_nan_of(x);
    }
    return (b & GMATH_SIGN_BIT) ? gmath_invalid() : x; /* sqrt(-inf) is invalid, sqrt(+inf) is +inf */
  }
  if (a == 0) {
    return x; /* sqrt(+-0) is +-0 */
  }
  if (b & GMATH_SIGN_BIT) {
    return gmath_invalid();
  }
  int64_t shift = 0; /* the exponent of the result is half + shift */
  if (a < 0x0010000000000000ull) {
    /* subnormal: 2^54 x is exact and normal, and its root is 2^27 the root of x */
    a = gmath_bits(x * 0x1p54) & GMATH_ABS_MASK;
    shift = -27;
  }
  /* m in [1, 4): the exponent of a made 0 or 1, by its parity. */
  int64_t ex = (int64_t)(a >> 52);
  int64_t half = (ex - 1023) >> 1; /* floor((ex - 1023) / 2), an arithmetic shift */
  uint64_t field = 1024u - ((uint64_t)ex & 1u); /* an odd biased exponent is an even one: m in [1, 2) */
  uint64_t mb = (a & 0x000fffffffffffffull) | (field << 52);
  double m = gmath_double(mb);
  double y = gmath_sqrt_correct(m, gmath_sqrt_estimate(m));
  return gmath_double(gmath_bits(y) + (((uint64_t)(half + shift)) << 52));
}

#ifdef GMATH_HW_SQRT
static inline double gmath_sqrt_hardware_impl(double x) {
  double r = gmath_sqrt_instruction(x);
  if (r != r) {
    /* NaN: the instruction's own (the sign and payload differ by target); the invalid exception it raised stands */
    return gmath_double(GMATH_QNAN_BITS);
  }
  return r;
}
#define gmath_sqrt_impl gmath_sqrt_hardware_impl
#else
#define gmath_sqrt_impl gmath_sqrt_portable_impl
#endif

#endif /* GHOTI_IO_GMATH_SQRT_IMPL_H */
