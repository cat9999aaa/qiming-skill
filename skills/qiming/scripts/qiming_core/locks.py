"""Cooperating-process lock; stale locks require explicit investigation."""

from __future__ import annotations

import json
import os
import socket
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class LockHeld(Exception):
    pass


@contextmanager
def operation_lock(directory: Path, run_id: str) -> Iterator[Path]:
    if directory.is_symlink():
        raise ValueError("Operations directory must not be a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / ".lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise LockHeld(str(path)) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"host": socket.gethostname(), "pid": os.getpid(), "run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        yield path
    finally:
        path.unlink(missing_ok=True)


def lock_status(manifest_path: Path) -> dict:
    import hashlib
    path=manifest_path.parent/'operations/.lock'
    if not path.exists() and not path.is_symlink():
        return {'status':'ok','result':{'state':'unlocked'},'changed':[]}
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        return {'status':'ok','result':{'state':'unknown','reason':'not-regular-file'},'changed':[]}
    raw=path.read_bytes()
    state='unknown'
    try:
        lock=json.loads(raw)
        pid=lock.get('pid')
        if lock.get('host')==socket.gethostname() and isinstance(pid,int) and not isinstance(pid,bool) and pid>0:
            if os.name=='nt':
                import ctypes
                from ctypes import wintypes
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
                kernel.OpenProcess.restype=wintypes.HANDLE
                kernel.CloseHandle.argtypes=[wintypes.HANDLE]
                handle=kernel.OpenProcess(0x1000,False,pid)
                if handle:
                    kernel.CloseHandle(handle); state='alive'
                elif ctypes.get_last_error()==87:
                    state='stale'
            else:
                try: os.kill(pid,0); state='alive'
                except ProcessLookupError: state='stale'
                except PermissionError: state='alive'
                except OSError: pass
    except (ValueError,AttributeError):
        lock={}
    return {'status':'ok','result':{'state':state,'lock':lock,'sha256':hashlib.sha256(raw).hexdigest(),'path':str(path)},'changed':[]}


def lock_conflict(manifest_path: Path) -> dict:
    info=lock_status(manifest_path)['result']
    return {'status':'conflict','result':info,'diagnostics':[{'code':'STALE_LOCK' if info['state']=='stale' else 'LOCKED','message':'Operation lock is held; age alone never proves that its owner is dead.','hint':'Call lock_status. Only a proven dead local owner can be cleared with lock_break using run_id and expected_sha256. Then inspect the transaction journal.','details':info,'retryable':False}],'changed':[]}


@contextmanager
def _break_guard(directory):
    """OS-held advisory gate is released on process death; marker is reusable."""
    gate=directory/'.lock-break'
    if directory.is_symlink() or gate.is_symlink():
        raise ValueError('Lock paths must not be symlinks')
    descriptor=os.open(gate,os.O_CREAT|os.O_RDWR,0o600)
    acquired=False
    try:
        if os.name=='nt':
            import msvcrt
            if os.fstat(descriptor).st_size==0: os.write(descriptor,b'0')
            os.lseek(descriptor,0,os.SEEK_SET)
            try: msvcrt.locking(descriptor,msvcrt.LK_NBLCK,1)
            except OSError as error: raise LockHeld(str(gate)) from error
        else:
            import fcntl
            try: fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as error: raise LockHeld(str(gate)) from error
        acquired=True
        yield
    finally:
        if acquired:
            if os.name=='nt':
                os.lseek(descriptor,0,os.SEEK_SET)
                msvcrt.locking(descriptor,msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(descriptor,fcntl.LOCK_UN)
        os.close(descriptor)


def lock_break(manifest_path: Path, run_id: str, expected_sha256: str) -> dict:
    directory=manifest_path.parent/'operations'
    try:
        with _break_guard(directory):
            info=lock_status(manifest_path)['result']
            if info['state']!='stale' or info.get('sha256')!=expected_sha256 or info.get('lock',{}).get('run_id')!=run_id:
                return lock_conflict(manifest_path)
            path=directory/'.lock'
            if lock_status(manifest_path)['result']!=info:
                return lock_conflict(manifest_path)
            path.unlink()
            return {'status':'ok','result':{'removed_lock':info,'next':'reconcile inspect, then resume or rollback'},'changed':[{'path':str(path),'action':'removed-stale-lock'}]}
    except LockHeld:
        return lock_conflict(manifest_path)
