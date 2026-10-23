"""Long operations (switching a backend, a backup, a restore) run here, one
at a time, in a background thread.

A request starts a job and gets its id back at once; the page then polls
GET /api/job. A reload does not lose the progress, and a second browser
cannot start a second switch while the first one runs: start() refuses.

A job is a function that takes a Progress. It reports steps by code, adds
warnings by code, and fails by raising JobFailed with a code. The page turns
the codes into text; nothing here is shown to a person as written.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


class JobFailed(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass
class JobState:
    id: str
    kind: str
    target: str
    step: str = "queued"
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    ok: bool | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    result: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "target": self.target,
            "step": self.step, "running": self.finished_at is None,
            "ok": self.ok, "error": self.error, "warnings": list(self.warnings),
            "result": dict(self.result),
            "started_at": self.started_at, "finished_at": self.finished_at,
        }


class Progress:
    """What a job function sees of its own state."""

    def __init__(self, state: JobState, lock: threading.Lock):
        self._state = state
        self._lock = lock

    def step(self, code: str) -> None:
        with self._lock:
            self._state.step = code
        log.info("Job %s %s: %s", self._state.kind, self._state.target, code)

    def warn(self, code: str) -> None:
        with self._lock:
            self._state.warnings.append(code)
        log.warning("Job %s %s: warning %s", self._state.kind, self._state.target, code)

    def set_result(self, **values) -> None:
        with self._lock:
            self._state.result.update(values)


class JobRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._current: JobState | None = None

    def busy(self) -> bool:
        with self._lock:
            return self._current is not None and self._current.finished_at is None

    def start(self, kind: str, target: str, fn) -> dict | None:
        """Starts fn(progress) in a thread. None when a job is still running."""
        with self._lock:
            if self._current is not None and self._current.finished_at is None:
                return None
            state = JobState(id=uuid.uuid4().hex[:12], kind=kind, target=target)
            self._current = state
        thread = threading.Thread(target=self._run, args=(state, fn),
                                  name=f"job-{kind}", daemon=True)
        thread.start()
        return state.as_dict()

    def _run(self, state: JobState, fn) -> None:
        progress = Progress(state, self._lock)
        ok, error = True, None
        try:
            fn(progress)
        except JobFailed as e:
            ok, error = False, e.code
            log.error("Job %s %s failed: %s", state.kind, state.target, e)
        except Exception:  # outer boundary of the thread: never die silently
            ok, error = False, "internal_error"
            log.exception("Job %s %s crashed", state.kind, state.target)
        with self._lock:
            state.ok, state.error = ok, error
            state.step = "done" if ok else "failed"
            state.finished_at = time.time()

    def current(self) -> dict | None:
        with self._lock:
            return self._current.as_dict() if self._current else None


# The one runner of the process. One job at a time across every kind is the
# point: a backup must not read a backend's data while a switch stops it.
RUNNER = JobRunner()
