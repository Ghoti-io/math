/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Integer-byte native80 caller, independently compiled without LTO. */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_ELEVEN_ABI_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_ELEVEN_ABI_H
#include <ghoti.io/math/elementary.h>
#if LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384 && defined(__x86_64__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDE_BYTE_CALLER 1
#define LDE_ASM_STRING_(x) #x
#define LDE_ASM_STRING(x) LDE_ASM_STRING_(x)
__attribute__((naked,noinline)) static void lde_native80_bytes(
 int op __attribute__((unused)),const void *x __attribute__((unused)),
 const void *y __attribute__((unused)),void *out __attribute__((unused))) {
 __asm__(
 "subq $56,%rsp\n\t.cfi_adjust_cfa_offset 56\n\tmovq %rcx,32(%rsp)\n\t"
 "movq (%rsi),%rax\n\tmovq %rax,(%rsp)\n\tmovq 8(%rsi),%rax\n\tmovq %rax,8(%rsp)\n\t"
 "movq (%rdx),%rax\n\tmovq %rax,16(%rsp)\n\tmovq 8(%rdx),%rax\n\tmovq %rax,24(%rsp)\n\t"
 "cmpl $0,%edi\n\tje .Llde_r0\n\t"
 "cmpl $1,%edi\n\tje .Llde_r1\n\t"
 "cmpl $2,%edi\n\tje .Llde_r2\n\t"
 "cmpl $3,%edi\n\tje .Llde_r3\n\t"
 "cmpl $4,%edi\n\tje .Llde_r4\n\t"
 "cmpl $5,%edi\n\tje .Llde_r5\n\t"
 "cmpl $6,%edi\n\tje .Llde_r6\n\t"
 "cmpl $7,%edi\n\tje .Llde_r7\n\t"
 "cmpl $8,%edi\n\tje .Llde_r8\n\t"
 "cmpl $9,%edi\n\tje .Llde_r9\n\t"
 "cmpl $10,%edi\n\tje .Llde_r10\n\t"
 "ud2\n\t"
 ".Llde_r0:\n\tcall " LDE_ASM_STRING(gmath_sqrtl) "\n\tjmp .Llde_return\n\t"
 ".Llde_r1:\n\tcall " LDE_ASM_STRING(gmath_cbrtl) "\n\tjmp .Llde_return\n\t"
 ".Llde_r2:\n\tcall " LDE_ASM_STRING(gmath_hypotl) "\n\tjmp .Llde_return\n\t"
 ".Llde_r3:\n\tcall " LDE_ASM_STRING(gmath_expl) "\n\tjmp .Llde_return\n\t"
 ".Llde_r4:\n\tcall " LDE_ASM_STRING(gmath_exp2l) "\n\tjmp .Llde_return\n\t"
 ".Llde_r5:\n\tcall " LDE_ASM_STRING(gmath_expm1l) "\n\tjmp .Llde_return\n\t"
 ".Llde_r6:\n\tcall " LDE_ASM_STRING(gmath_logl) "\n\tjmp .Llde_return\n\t"
 ".Llde_r7:\n\tcall " LDE_ASM_STRING(gmath_log2l) "\n\tjmp .Llde_return\n\t"
 ".Llde_r8:\n\tcall " LDE_ASM_STRING(gmath_log10l) "\n\tjmp .Llde_return\n\t"
 ".Llde_r9:\n\tcall " LDE_ASM_STRING(gmath_log1pl) "\n\tjmp .Llde_return\n\t"
 ".Llde_r10:\n\tcall " LDE_ASM_STRING(gmath_powl) "\n\tjmp .Llde_return\n\t"
 ".Llde_return:\n\tmovq 32(%rsp),%r11\n\tfstpt (%r11)\n\t"
 "addq $56,%rsp\n\t.cfi_adjust_cfa_offset -56\n\tret");
#if !defined(__clang__)
 __builtin_unreachable();
#endif
}
#elif LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384 && defined(__i386__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDE_BYTE_CALLER 1
#define LDE_ASM_STRING_(x) #x
#define LDE_ASM_STRING(x) LDE_ASM_STRING_(x)
__attribute__((naked,noinline)) static void lde_native80_bytes(
 int op __attribute__((unused)),const void *x __attribute__((unused)),
 const void *y __attribute__((unused)),void *out __attribute__((unused))) {
 __asm__(
 "subl $44,%esp\n\t.cfi_adjust_cfa_offset 44\n\tmovl 60(%esp),%eax\n\tmovl %eax,24(%esp)\n\t"
 "movl 52(%esp),%eax\n\tmovl (%eax),%edx\n\tmovl %edx,(%esp)\n\tmovl 4(%eax),%edx\n\tmovl %edx,4(%esp)\n\tmovl 8(%eax),%edx\n\tmovl %edx,8(%esp)\n\t"
 "movl 56(%esp),%eax\n\tmovl (%eax),%edx\n\tmovl %edx,12(%esp)\n\tmovl 4(%eax),%edx\n\tmovl %edx,16(%esp)\n\tmovl 8(%eax),%edx\n\tmovl %edx,20(%esp)\n\t"
 "movl 48(%esp),%ecx\n\t"
 "cmpl $0,%ecx\n\tje .Lldei_r0\n\t"
 "cmpl $1,%ecx\n\tje .Lldei_r1\n\t"
 "cmpl $2,%ecx\n\tje .Lldei_r2\n\t"
 "cmpl $3,%ecx\n\tje .Lldei_r3\n\t"
 "cmpl $4,%ecx\n\tje .Lldei_r4\n\t"
 "cmpl $5,%ecx\n\tje .Lldei_r5\n\t"
 "cmpl $6,%ecx\n\tje .Lldei_r6\n\t"
 "cmpl $7,%ecx\n\tje .Lldei_r7\n\t"
 "cmpl $8,%ecx\n\tje .Lldei_r8\n\t"
 "cmpl $9,%ecx\n\tje .Lldei_r9\n\t"
 "cmpl $10,%ecx\n\tje .Lldei_r10\n\t"
 "ud2\n\t"
 ".Lldei_r0:\n\tcall " LDE_ASM_STRING(gmath_sqrtl) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r1:\n\tcall " LDE_ASM_STRING(gmath_cbrtl) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r2:\n\tcall " LDE_ASM_STRING(gmath_hypotl) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r3:\n\tcall " LDE_ASM_STRING(gmath_expl) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r4:\n\tcall " LDE_ASM_STRING(gmath_exp2l) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r5:\n\tcall " LDE_ASM_STRING(gmath_expm1l) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r6:\n\tcall " LDE_ASM_STRING(gmath_logl) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r7:\n\tcall " LDE_ASM_STRING(gmath_log2l) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r8:\n\tcall " LDE_ASM_STRING(gmath_log10l) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r9:\n\tcall " LDE_ASM_STRING(gmath_log1pl) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_r10:\n\tcall " LDE_ASM_STRING(gmath_powl) "\n\tjmp .Lldei_return\n\t"
 ".Lldei_return:\n\tmovl 24(%esp),%edx\n\tfstpt (%edx)\n\t"
 "addl $44,%esp\n\t.cfi_adjust_cfa_offset -44\n\tret");
#if !defined(__clang__)
 __builtin_unreachable();
#endif
}
#endif
#endif
