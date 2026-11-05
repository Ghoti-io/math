/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Integer-byte native80 caller, independently compiled without LTO. */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_SEVENTEEN_ABI_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_SEVENTEEN_ABI_H
#include <ghoti.io/math/elementary.h>
#if LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384 && defined(__x86_64__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDS17_BYTE_CALLER 1
#define LDS17_ASM_STRING_(x) #x
#define LDS17_ASM_STRING(x) LDS17_ASM_STRING_(x)
__attribute__((naked,noinline)) static void lds17_native80_bytes(
 int op __attribute__((unused)),const void *x __attribute__((unused)),
 const void *y __attribute__((unused)),void *out __attribute__((unused))) {
 __asm__(
 "subq $56,%rsp\n\t.cfi_adjust_cfa_offset 56\n\tmovq %rcx,32(%rsp)\n\t"
 "movq (%rsi),%rax\n\tmovq %rax,(%rsp)\n\tmovq 8(%rsi),%rax\n\tmovq %rax,8(%rsp)\n\t"
 "movq (%rdx),%rax\n\tmovq %rax,16(%rsp)\n\tmovq 8(%rdx),%rax\n\tmovq %rax,24(%rsp)\n\t"
 "cmpl $0,%edi\n\tje .Llds17_r0\n\t"
 "cmpl $1,%edi\n\tje .Llds17_r1\n\t"
 "cmpl $2,%edi\n\tje .Llds17_r2\n\t"
 "cmpl $3,%edi\n\tje .Llds17_r3\n\t"
 "cmpl $4,%edi\n\tje .Llds17_r4\n\t"
 "cmpl $5,%edi\n\tje .Llds17_r5\n\t"
 "cmpl $6,%edi\n\tje .Llds17_r6\n\t"
 "cmpl $7,%edi\n\tje .Llds17_r7\n\t"
 "cmpl $8,%edi\n\tje .Llds17_r8\n\t"
 "cmpl $9,%edi\n\tje .Llds17_r9\n\t"
 "cmpl $10,%edi\n\tje .Llds17_r10\n\t"
 "cmpl $11,%edi\n\tje .Llds17_r11\n\t"
 "cmpl $12,%edi\n\tje .Llds17_r12\n\t"
 "cmpl $13,%edi\n\tje .Llds17_r13\n\t"
 "cmpl $14,%edi\n\tje .Llds17_r14\n\t"
 "cmpl $15,%edi\n\tje .Llds17_r15\n\t"
 "cmpl $16,%edi\n\tje .Llds17_r16\n\t"
 "ud2\n\t"
 ".Llds17_r0:\n\tcall " LDS17_ASM_STRING(gmath_sinl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r1:\n\tcall " LDS17_ASM_STRING(gmath_cosl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r2:\n\tcall " LDS17_ASM_STRING(gmath_tanl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r3:\n\tcall " LDS17_ASM_STRING(gmath_asinl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r4:\n\tcall " LDS17_ASM_STRING(gmath_acosl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r5:\n\tcall " LDS17_ASM_STRING(gmath_atanl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r6:\n\tcall " LDS17_ASM_STRING(gmath_atan2l) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r7:\n\tcall " LDS17_ASM_STRING(gmath_sinhl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r8:\n\tcall " LDS17_ASM_STRING(gmath_coshl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r9:\n\tcall " LDS17_ASM_STRING(gmath_tanhl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r10:\n\tcall " LDS17_ASM_STRING(gmath_asinhl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r11:\n\tcall " LDS17_ASM_STRING(gmath_acoshl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r12:\n\tcall " LDS17_ASM_STRING(gmath_atanhl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r13:\n\tcall " LDS17_ASM_STRING(gmath_erfl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r14:\n\tcall " LDS17_ASM_STRING(gmath_erfcl) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r15:\n\tcall " LDS17_ASM_STRING(gmath_tgammal) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_r16:\n\tcall " LDS17_ASM_STRING(gmath_lgammal) "\n\tjmp .Llds17_return\n\t"
 ".Llds17_return:\n\tmovq 32(%rsp),%r11\n\tfstpt (%r11)\n\t"
 "addq $56,%rsp\n\t.cfi_adjust_cfa_offset -56\n\tret");
#if !defined(__clang__)
 __builtin_unreachable();
#endif
}
#elif LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384 && defined(__i386__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDS17_BYTE_CALLER 1
#define LDS17_ASM_STRING_(x) #x
#define LDS17_ASM_STRING(x) LDS17_ASM_STRING_(x)
__attribute__((naked,noinline)) static void lds17_native80_bytes(
 int op __attribute__((unused)),const void *x __attribute__((unused)),
 const void *y __attribute__((unused)),void *out __attribute__((unused))) {
 __asm__(
 "subl $44,%esp\n\t.cfi_adjust_cfa_offset 44\n\tmovl 60(%esp),%eax\n\tmovl %eax,24(%esp)\n\t"
 "movl 52(%esp),%eax\n\tmovl (%eax),%edx\n\tmovl %edx,(%esp)\n\tmovl 4(%eax),%edx\n\tmovl %edx,4(%esp)\n\tmovl 8(%eax),%edx\n\tmovl %edx,8(%esp)\n\t"
 "movl 56(%esp),%eax\n\tmovl (%eax),%edx\n\tmovl %edx,12(%esp)\n\tmovl 4(%eax),%edx\n\tmovl %edx,16(%esp)\n\tmovl 8(%eax),%edx\n\tmovl %edx,20(%esp)\n\t"
 "movl 48(%esp),%ecx\n\t"
 "cmpl $0,%ecx\n\tje .Llds17i_r0\n\t"
 "cmpl $1,%ecx\n\tje .Llds17i_r1\n\t"
 "cmpl $2,%ecx\n\tje .Llds17i_r2\n\t"
 "cmpl $3,%ecx\n\tje .Llds17i_r3\n\t"
 "cmpl $4,%ecx\n\tje .Llds17i_r4\n\t"
 "cmpl $5,%ecx\n\tje .Llds17i_r5\n\t"
 "cmpl $6,%ecx\n\tje .Llds17i_r6\n\t"
 "cmpl $7,%ecx\n\tje .Llds17i_r7\n\t"
 "cmpl $8,%ecx\n\tje .Llds17i_r8\n\t"
 "cmpl $9,%ecx\n\tje .Llds17i_r9\n\t"
 "cmpl $10,%ecx\n\tje .Llds17i_r10\n\t"
 "cmpl $11,%ecx\n\tje .Llds17i_r11\n\t"
 "cmpl $12,%ecx\n\tje .Llds17i_r12\n\t"
 "cmpl $13,%ecx\n\tje .Llds17i_r13\n\t"
 "cmpl $14,%ecx\n\tje .Llds17i_r14\n\t"
 "cmpl $15,%ecx\n\tje .Llds17i_r15\n\t"
 "cmpl $16,%ecx\n\tje .Llds17i_r16\n\t"
 "ud2\n\t"
 ".Llds17i_r0:\n\tcall " LDS17_ASM_STRING(gmath_sinl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r1:\n\tcall " LDS17_ASM_STRING(gmath_cosl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r2:\n\tcall " LDS17_ASM_STRING(gmath_tanl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r3:\n\tcall " LDS17_ASM_STRING(gmath_asinl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r4:\n\tcall " LDS17_ASM_STRING(gmath_acosl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r5:\n\tcall " LDS17_ASM_STRING(gmath_atanl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r6:\n\tcall " LDS17_ASM_STRING(gmath_atan2l) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r7:\n\tcall " LDS17_ASM_STRING(gmath_sinhl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r8:\n\tcall " LDS17_ASM_STRING(gmath_coshl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r9:\n\tcall " LDS17_ASM_STRING(gmath_tanhl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r10:\n\tcall " LDS17_ASM_STRING(gmath_asinhl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r11:\n\tcall " LDS17_ASM_STRING(gmath_acoshl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r12:\n\tcall " LDS17_ASM_STRING(gmath_atanhl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r13:\n\tcall " LDS17_ASM_STRING(gmath_erfl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r14:\n\tcall " LDS17_ASM_STRING(gmath_erfcl) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r15:\n\tcall " LDS17_ASM_STRING(gmath_tgammal) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_r16:\n\tcall " LDS17_ASM_STRING(gmath_lgammal) "\n\tjmp .Llds17i_return\n\t"
 ".Llds17i_return:\n\tmovl 24(%esp),%edx\n\tfstpt (%edx)\n\t"
 "addl $44,%esp\n\t.cfi_adjust_cfa_offset -44\n\tret");
#if !defined(__clang__)
 __builtin_unreachable();
#endif
}
#endif
#endif
