/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * External native80 ABI caller. Copy argument bytes with integer instructions,
 * so even an O0 caller passes signaling/malformed operands unchanged. */
#ifndef GMATH_LONG_DOUBLE_NINE_ABI_H
#define GMATH_LONG_DOUBLE_NINE_ABI_H
#include <ghoti.io/math/basic.h>
#include <stdint.h>
#if LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384 && defined(__x86_64__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LD9_BYTE_CALLER 1
#define LD9_ASM_STRING_(x) #x
#define LD9_ASM_STRING(x) LD9_ASM_STRING_(x)
__attribute__((naked,noinline)) static void ld9_native80_bytes(
  int op __attribute__((unused)),const void *x __attribute__((unused)),
  const void *y __attribute__((unused)),const void *z __attribute__((unused)),
  void *out __attribute__((unused)),int *q __attribute__((unused)),
  uint64_t *integer __attribute__((unused))) {
  __asm__(
    "subq $72,%rsp\n\t.cfi_adjust_cfa_offset 72\n\t"
    "movl %edi,%r10d\n\tmovq %r8,48(%rsp)\n\tmovq 80(%rsp),%rax\n\tmovq %rax,56(%rsp)\n\t"
    "movq (%rsi),%rax\n\tmovq %rax,(%rsp)\n\tmovq 8(%rsi),%rax\n\tmovq %rax,8(%rsp)\n\t"
    "movq (%rdx),%rax\n\tmovq %rax,16(%rsp)\n\tmovq 8(%rdx),%rax\n\tmovq %rax,24(%rsp)\n\t"
    "movq (%rcx),%rax\n\tmovq %rax,32(%rsp)\n\tmovq 8(%rcx),%rax\n\tmovq %rax,40(%rsp)\n\t"
    "movq %r9,%rdi\n\t"
    "cmpl $0,%r10d\n\tje .Lld9_i0\n\tcmpl $1,%r10d\n\tje .Lld9_i1\n\t"
    "cmpl $2,%r10d\n\tje .Lld9_i2\n\tcmpl $3,%r10d\n\tje .Lld9_i3\n\t"
    "cmpl $4,%r10d\n\tje .Lld9_r4\n\tcmpl $5,%r10d\n\tje .Lld9_r5\n\t"
    "cmpl $6,%r10d\n\tje .Lld9_r6\n\tcmpl $7,%r10d\n\tje .Lld9_r7\n\t"
    "cmpl $8,%r10d\n\tje .Lld9_r8\n\txorl %edi,%edi\n\tjmp .Lld9_r6\n\t"
    ".Lld9_i0:\n\tcall " LD9_ASM_STRING(gmath_lroundl) "\n\tjmp .Lld9_integer\n\t"
    ".Lld9_i1:\n\tcall " LD9_ASM_STRING(gmath_llroundl) "\n\tjmp .Lld9_integer\n\t"
    ".Lld9_i2:\n\tcall " LD9_ASM_STRING(gmath_lrintl) "\n\tjmp .Lld9_integer\n\t"
    ".Lld9_i3:\n\tcall " LD9_ASM_STRING(gmath_llrintl) "\n\tjmp .Lld9_integer\n\t"
    ".Lld9_r4:\n\tcall " LD9_ASM_STRING(gmath_fmodl) "\n\tjmp .Lld9_real\n\t"
    ".Lld9_r5:\n\tcall " LD9_ASM_STRING(gmath_remainderl) "\n\tjmp .Lld9_real\n\t"
    ".Lld9_r6:\n\tcall " LD9_ASM_STRING(gmath_remquol) "\n\tjmp .Lld9_real\n\t"
    ".Lld9_r7:\n\tcall " LD9_ASM_STRING(gmath_fdiml) "\n\tjmp .Lld9_real\n\t"
    ".Lld9_r8:\n\tcall " LD9_ASM_STRING(gmath_fmal) "\n\t"
    ".Lld9_real:\n\tmovq 48(%rsp),%r11\n\tfstpt (%r11)\n\tjmp .Lld9_return\n\t"
    ".Lld9_integer:\n\tmovq 56(%rsp),%r11\n\tmovq %rax,(%r11)\n\tmovq 48(%rsp),%r11\n\t"
    "movq $0,(%r11)\n\tmovq $0,8(%r11)\n\t"
    ".Lld9_return:\n\taddq $72,%rsp\n\t.cfi_adjust_cfa_offset -72\n\tret");
#if !defined(__clang__)
  __builtin_unreachable();
#endif
}
#endif
#endif
