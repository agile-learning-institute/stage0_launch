from __future__ import annotations

import io
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TextIO


@dataclass
class Job:
    id: str
    name: str
    status: str  # running | done | error
    log: io.StringIO = field(default_factory=io.StringIO)
    error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: Job | None = None

    def start(self, name: str, work: Callable[[TextIO], None]) -> Job:
        job = Job(id=str(uuid.uuid4()), name=name, status="running")

        def _run() -> None:
            try:
                work(job.log)
                job.status = "done"
            except Exception as e:
                job.status = "error"
                job.error = str(e)
                with job._lock:
                    job.log.write(f"\n[error] {e}\n")
            finally:
                with job._lock:
                    job.log.flush()

        with self._lock:
            if self._current and self._current.status == "running":
                raise RuntimeError("A job is already running")
            self._current = job
        threading.Thread(target=_run, daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            if self._current and self._current.id == job_id:
                return self._current
        return None

    def current_running(self) -> Job | None:
        with self._lock:
            if self._current and self._current.status == "running":
                return self._current
        return None
