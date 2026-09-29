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
