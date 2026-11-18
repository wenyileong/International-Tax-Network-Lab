"""Background execution of runs with progress and cancellation (plan s 11).

A job wraps :func:`taxnetlab.runs.execute` in a worker thread. Jobs live in memory only: a job is a
convenience for the interface, while the run record (written atomically when the engine finishes) is the
durable result. Cancelling a job stops the engine at its next checkpoint and stores nothing.
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from typing import Any, Callable

from taxnetlab.progress import Cancelled, Tracker, tracking
from taxnetlab.validation import ValidationError

MAX_JOBS = 200
MAX_PARALLEL = 2


class JobManager:
    def __init__(self, execute: Callable[[dict[str, Any]], dict[str, Any]]):
        self._execute = execute
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(MAX_PARALLEL)

    def submit_task(self, kind: str, task: Callable[[], Any], label: str = "") -> dict[str, Any]:
        """Run any callable as a job (for example an A-share import), with the same progress and cancellation."""
        return self.submit({"engine_id": None, "dataset_id": None, "kind": kind, "label": label}, task)

    def submit(self, spec: dict[str, Any], task: Callable[[], Any] | None = None) -> dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        tracker = Tracker()
        job = {"job_id": job_id, "state": "queued", "engine_id": spec.get("engine_id"), "dataset_id": spec.get("dataset_id"),
               "submitted": time.time(), "finished": None, "run_id": None, "outcome": None, "error": None,
               "validation": None, "kind": spec.get("kind", "run"), "label": spec.get("label"), "result": None,
               "_tracker": tracker}
        with self._lock:
            if len(self._jobs) >= MAX_JOBS:  # forget the oldest finished jobs
                for old in sorted((j for j in self._jobs.values() if j["finished"]), key=lambda j: j["finished"])[:50]:
                    self._jobs.pop(old["job_id"], None)
            self._jobs[job_id] = job
        threading.Thread(target=self._work, args=(job, spec, task), daemon=True, name=f"job-{job_id}").start()
        return self.get(job_id)

    def _work(self, job: dict[str, Any], spec: dict[str, Any], task: Callable[[], Any] | None = None) -> None:
        tracker: Tracker = job["_tracker"]
        with self._slots:
            if tracker.cancel_event.is_set():
                self._finish(job, "cancelled")
                return
            job["state"] = "running"
            if task is not None:
                self._work_task(job, task)
                return
            try:
                with tracking(tracker):
                    out = self._execute(spec)
                if out.get("executed"):
                    job["run_id"] = out["record"]["run_id"]
                    job["outcome"] = out["record"]["outcome"]
                    self._finish(job, "done")
                else:
                    job["validation"] = out.get("validation")
                    self._finish(job, "blocked")
            except Cancelled:
                self._finish(job, "cancelled")
            except ValidationError as exc:
                job["validation"] = exc.report.to_dict()
                self._finish(job, "blocked")
            except Exception as exc:  # reported to the interface; the console and the log keep the traceback
                traceback.print_exc()
                logging.getLogger("taxnetlab").exception("background run %s failed", job["job_id"])
                job["error"] = f"{type(exc).__name__}: {exc}"
                self._finish(job, "failed")

    def _work_task(self, job: dict[str, Any], task: Callable[[], Any]) -> None:
        try:
            with tracking(job["_tracker"]):
                job["result"] = task()
            self._finish(job, "done")
        except Cancelled:
            self._finish(job, "cancelled")
        except (ValueError, KeyError, OSError) as exc:  # the user's to fix (a wrong path, a malformed release)
            job["error"] = str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)
            self._finish(job, "failed")
        except Exception as exc:
            traceback.print_exc()
            logging.getLogger("taxnetlab").exception("background task %s failed", job["job_id"])
            job["error"] = f"{type(exc).__name__}: {exc}"
            self._finish(job, "failed")

    @staticmethod
    def _finish(job: dict[str, Any], state: str) -> None:
        job["state"] = state
        job["finished"] = time.time()
        if state == "done":
            job["_tracker"].fraction = 1.0

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"unknown job '{job_id}'")
        tracker: Tracker = job["_tracker"]
        return {**{k: v for k, v in job.items() if not k.startswith("_")}, "progress": round(tracker.fraction, 4),
                "message": tracker.message, "cancel_requested": tracker.cancel_event.is_set()}

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(self._jobs)
        return [self.get(i) for i in reversed(ids)]

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"unknown job '{job_id}'")
        job["_tracker"].cancel()
        return self.get(job_id)

    def wait(self, job_id: str, timeout: float = 60.0) -> dict[str, Any]:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            j = self.get(job_id)
            if j["state"] not in ("queued", "running"):
                return j
            time.sleep(0.02)
        return self.get(job_id)
