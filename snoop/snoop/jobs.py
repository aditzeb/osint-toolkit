"""Case job runner: reconnectable background investigations with event replay.

One investigation job per case. Events are buffered with sequence numbers so
a reconnecting web client (or a CLI reattaching) replays history and then
follows live. A per-case lock protects the saved dossier from conflicting
writes while a job is running.
"""

from __future__ import annotations

import asyncio

from snoop.core import Bus, Event
from snoop.pipeline import Dossier
from snoop.workflow import Workflow

JOBS: dict[str, Job] = {}


def recover_interrupted_cases() -> int:
    """Turn stale on-disk running states into resumable paused cases.

    Jobs live in this process, so a case marked running before the web app has
    created any jobs can only be residue from a crash or forced shutdown.
    """
    recovered = 0
    for row in Dossier.list_cases():
        if row.get("workflow_status") != "running":
            continue
        dossier = Dossier.load(row["id"])
        if not dossier:
            continue
        for lead in dossier.leads:
            if lead.get("status") == "running":
                lead["status"] = "pending"
                lead["reason"] = "interrupted by process exit; ready to resume"
        dossier.workflow.pop("current_action", None)
        dossier.workflow["status"] = "paused"
        dossier.workflow["stop_reason"] = "previous run was interrupted; ready to continue"
        dossier.save()
        recovered += 1
    return recovered


class Job:
    def __init__(self, dossier: Dossier):
        self.id = dossier.id
        self.dossier = dossier
        self.bus = Bus()
        self.events: list[dict] = []
        self.seq = 0
        self.lock = asyncio.Lock()
        self.subscribers: list[asyncio.Queue] = []
        self.workflow: Workflow | None = None
        self.task: asyncio.Task | None = None
        self.bus.on(self._record)

    def _record(self, ev) -> None:
        self.seq += 1
        row = {"seq": self.seq, "kind": ev.kind, "payload": ev.payload}
        self.events.append(row)
        if len(self.events) > 2000:
            self.events = self.events[-1000:]
        for queue in list(self.subscribers):
            queue.put_nowait(row)

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def status(self) -> dict:
        return {
            "id": self.id,
            "running": self.running,
            "events": self.seq,
            "workflow": self.workflow.status() if self.workflow else None,
            "target": self.dossier.target,
        }


async def _drive(job: Job, preset: str | None, mode: str | None) -> None:
    job.workflow = Workflow(job.dossier, job.bus, preset=preset, mode=mode)
    try:
        status = await job.workflow.run()
        if status.get("status") == "done":
            await job.workflow.finalize_analysis()
            job.dossier.save()
            await job.bus.emit(
                "done",
                id=job.dossier.id,
                status="done",
                reason=status.get("stop_reason", ""),
                stats=job.dossier.stats,
                analysis=job.dossier.analysis,
            )
        elif status.get("status") == "needs_input":
            # Workflow already emitted the question. This explicit terminal
            # event lets reconnecting web clients stop their busy state.
            await job.bus.emit("needs_input", id=job.dossier.id)
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # boundary: surface failure honestly, keep the case
        detail = f"{type(exc).__name__}: {exc}"
        job.dossier.workflow.update({"status": "failed", "stop_reason": detail})
        job.dossier.save()
        job._record(Event("error", {"detail": detail}))
        job._record(
            Event(
                "done",
                {"id": job.dossier.id, "status": "failed", "reason": detail},
            )
        )


async def _drive_agent(job: Job, goal: str, steps: int | None) -> None:
    from snoop.agent import Agent

    agent = Agent(job.dossier, job.bus, max_steps=steps, goal=goal)
    job.workflow = agent.wf
    try:
        result = await agent.run()
        await job.bus.emit("agent_done", **result)
        if result["status"] == "needs_input":
            await job.bus.emit("needs_input", id=job.dossier.id)
        else:
            await job.bus.emit("done", id=job.dossier.id, status=result["status"], reason=result["reason"],
                               stats=job.dossier.stats)
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # boundary: surface failure honestly, keep the case
        detail = f"{type(exc).__name__}: {exc}"
        job.dossier.workflow.update({"status": "failed", "stop_reason": detail})
        job.dossier.save()
        job._record(Event("error", {"detail": detail}))
        job._record(Event("done", {"id": job.dossier.id, "status": "failed", "reason": detail}))


def start_agent_job(dossier: Dossier, *, goal: str = "", steps: int | None = None) -> Job:
    existing = JOBS.get(dossier.id)
    if existing and existing.running:
        return existing
    job = existing or Job(dossier)
    job.events.clear()
    job.dossier = dossier
    JOBS[dossier.id] = job
    job.task = asyncio.create_task(_drive_agent(job, goal, steps))
    return job


def start_job(dossier: Dossier, *, preset: str | None = None, mode: str | None = None) -> Job:
    existing = JOBS.get(dossier.id)
    if existing and existing.running:
        return existing
    job = existing or Job(dossier)
    # Completed rounds live in the case history. Replaying an old terminal
    # event during a new round would make clients disconnect immediately.
    job.events.clear()
    job.dossier = dossier
    JOBS[dossier.id] = job
    job.task = asyncio.create_task(_drive(job, preset, mode))
    return job


def get_job(case_id: str) -> Job | None:
    job = JOBS.get(case_id)
    return job


async def control(case_id: str, action: str) -> str:
    job = JOBS.get(case_id)
    if action in {"continue", "resume"} and (not job or not job.workflow):
        dossier = Dossier.load(case_id)
        if not dossier:
            return f"case {case_id!r} was not found"
        start_job(dossier)
        return "continued the investigation from the saved frontier"
    if not job or not job.workflow:
        return f"no running job for case {case_id!r}"
    if action == "pause":
        job.workflow.pause()
        return "pause requested; the current step finishes first"
    if action in {"continue", "resume"}:
        job.workflow.resume_loop()
        if not job.running:
            start_job(job.dossier)
            return "continued the investigation from the saved frontier"
        return "continued"
    if action in {"stop", "cancel"}:
        job.workflow.cancel()
        if job.task:
            job.task.cancel()
        return "cancellation requested; completed work is saved"
    return f"unknown control {action!r}"


def subscribe(case_id: str, since: int = 0) -> asyncio.Queue | None:
    job = JOBS.get(case_id)
    if not job:
        return None
    queue: asyncio.Queue = asyncio.Queue()
    for row in job.events:
        if row["seq"] > since:
            queue.put_nowait(row)
    job.subscribers.append(queue)
    return queue


def unsubscribe(case_id: str, queue: asyncio.Queue) -> None:
    job = JOBS.get(case_id)
    if job and queue in job.subscribers:
        job.subscribers.remove(queue)
