# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exclusive, verified reference writes; never repair an existing artifact."""
import os
from pathlib import Path
def write_new(path,payload):
 path=Path(path);descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
 try:
  offset=0
  while offset<len(payload):
   count=os.write(descriptor,payload[offset:])
   if count<=0:raise OSError('seventeen corpus short write')
   offset+=count
  os.fsync(descriptor);written=os.fstat(descriptor)
 finally:os.close(descriptor)
 descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  before=os.fstat(descriptor)
  if(before.st_dev,before.st_ino,before.st_size)!=(written.st_dev,written.st_ino,len(payload)):raise OSError('seventeen corpus output changed before verification')
  data=b''
  while len(data)<=len(payload):
   chunk=os.read(descriptor,min(65536,len(payload)+1-len(data)))
   if not chunk:break
   data+=chunk
  after=os.fstat(descriptor)
  named=os.stat(path,follow_symlinks=False)
  if(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(named.st_dev,named.st_ino,named.st_size,named.st_mtime_ns,named.st_ctime_ns):raise OSError('seventeen corpus output path changed during verification')
  if(before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns)or data!=payload:raise OSError('seventeen corpus write verification failed (no repair performed)')
 finally:os.close(descriptor)
