/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Bounded complete-record parser shared by the two seventeen probes. */
#ifndef GMATH_SEVENTEEN_PROBE_INPUT_H
#define GMATH_SEVENTEEN_PROBE_INPUT_H
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
static int lds17_probe_record(char *line,size_t capacity) {
  size_t count=0;int ch;
  while((ch=fgetc(stdin))!=EOF) {
    if(ch==0 || count+1>=capacity)return -1;
    line[count++]=(char)ch;
    if(ch=='\n')break;
  }
  if(ferror(stdin) || (count && line[count-1]!='\n'))return -1;
  line[count]=0;return count?1:0;
}
static int lds17_probe_fields(char *line,uint64_t *fields,unsigned count,int decimal_prefix) {
  char *cursor=line,*end;
  for(unsigned i=0;i<count;++i) {
    while(isspace((unsigned char)*cursor))++cursor;
    int base=decimal_prefix && i<2?10:16;
    if(base==10?!isdigit((unsigned char)*cursor):!isxdigit((unsigned char)*cursor))return 0;
    errno=0;uintmax_t value=strtoumax(cursor,&end,base);
    if(errno==ERANGE || value>UINT64_MAX || end==cursor || (*end && !isspace((unsigned char)*end)))return 0;
    fields[i]=(uint64_t)value;cursor=end;
  }
  while(isspace((unsigned char)*cursor))++cursor;
  return !*cursor;
}
#endif
