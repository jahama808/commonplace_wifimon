"""Polling worker entry point (SPEC §5.2 / §6.2).

Run as a separate process from the FastAPI web tier:

    PYTHONPATH=. .venv/bin/python -m app.worker

Schedules four jobs via APScheduler. A single Postgres advisory lock
(`pg_try_advisory_lock`) is acquired at startup so a second worker process
won't fire jobs concurrently — it'll log and exit.
"""
from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import _ensure_engine, dispose_engine, get_engine
from app.eero.client import EeroClient
from app.services.notifier import get_notifier
from app.services.polling import (
    check_all_devices,
    check_all_networks,
    record_device_counts,
    update_firmware_versions,
)

log = structlog.get_logger(__name__)

# Arbitrary 64-bit constant — anyone running pg_advisory_lock with this same
# value contends with us. Pick a value unlikely to collide with another app.
WORKER_ADVISORY_LOCK_KEY = 0x_C0DE_1A55_E5_AAAA  # "code lass eaaaa"

HST = "Pacific/Honolulu"


@asynccontextmanager
async def _hold_advisory_lock():
    """`pg_try_advisory_lock` so only one worker schedules jobs at a time.

    Held for the lifetime of the connection. We grab a dedicated connection
    (not pulled from the pool) so it's not yanked under us.
    """
    engine = get_engine()
    conn = await engine.connect()
    try:
        got = (
            await conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": WORKER_ADVISORY_LOCK_KEY})
        ).scalar()
        if not got:
            log.error("worker.lock_busy", key=hex(WORKER_ADVISORY_LOCK_KEY))
            await conn.close()
            raise SystemExit("another worker holds the advisory lock")
        log.info("worker.lock_acquired", key=hex(WORKER_ADVISORY_LOCK_KEY))
        yield
    finally:
        try:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": WORKER_ADVISORY_LOCK_KEY}
            )
        finally:
            await conn.close()


async def _run_job(label: str, runner) -> None:
    """Wrap a polling job in a fresh session + httpx client.

    Each job gets its own session so a long-running tick doesn't pin a
    connection from the pool, and isolated try/except so one tick's failure
    doesn't kill the scheduler. `runner(session, client)` returns the count.
    Reports the run to Prometheus.
    """
    from app.api.metrics import POLLING_JOB_LAST_RESULT, POLLING_JOB_RUNS

    _, sm = _ensure_engine()
    try:
        async with EeroClient() as client, sm() as session:
            session: AsyncSession
            result = await runner(session, client)
            log.info("worker.job_ok", job=label, result=result)
            POLLING_JOB_RUNS.labels(job=label, outcome="ok").inc()
            if isinstance(result, (int, float)):
                POLLING_JOB_LAST_RESULT.labels(job=label).set(float(result))
    except Exception as e:  # noqa: BLE001
        log.exception("worker.job_failed", job=label, error=str(e))
        POLLING_JOB_RUNS.labels(job=label, outcome="fail").inc()


def _build_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=HST)
    notifier = get_notifier()

    async def _networks(s, c):
        return await check_all_networks(s, client=c, notifier=notifier)

    async def _devices(s, c):
        return await check_all_devices(s, client=c, notifier=notifier)

    async def _counts(s, c):
        return await record_device_counts(s, client=c)

    async def _firmware(s, c):
        return await update_firmware_versions(s, client=c)

    schedule = (
        # SPEC §5.2: every 15 min
        ("check_all_networks", _networks, CronTrigger(minute="*/15", timezone=HST)),
        ("check_all_devices", _devices, CronTrigger(minute="*/15", timezone=HST)),
        # day 06–22 HST every 15 min
        ("record_device_counts.day", _counts, CronTrigger(minute="*/15", hour="6-21", timezone=HST)),
        # night 22–06 HST every 30 min
        ("record_device_counts.night", _counts, CronTrigger(minute="*/30", hour="22,23,0,1,2,3,4,5", timezone=HST)),
        # daily 03:00 HST
        ("update_firmware_versions", _firmware, CronTrigger(hour=3, minute=0, timezone=HST)),
    )

    for job_id, runner, trigger in schedule:
        # bind via default arg to avoid late-binding closure pitfalls
        sched.add_job(
            (lambda label=job_id, r=runner: asyncio.create_task(_run_job(label, r))),
            trigger=trigger,
            id=job_id,
            max_instances=1,
            coalesce=True,
        )

    return sched


async def amain() -> None:
    configure_logging()
    log.info(
        "worker.starting",
        eero_base=settings.EERO_API_BASE_URL,
        notifier=type(get_notifier()).__name__,
    )

    async with _hold_advisory_lock():
        scheduler = _build_scheduler()
        scheduler.start()
        log.info(
            "worker.scheduler_started",
            jobs=[j.id for j in scheduler.get_jobs()],
        )

        # Block forever; SIGTERM/SIGINT triggers a clean shutdown.
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        await stop.wait()

        log.info("worker.shutting_down")
        scheduler.shutdown(wait=False)


def main() -> None:
    try:
        asyncio.run(amain())
    finally:
        asyncio.run(dispose_engine())


if __name__ == "__main__":
    main()
