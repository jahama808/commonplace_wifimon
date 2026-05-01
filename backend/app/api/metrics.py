"""`/metrics` Prometheus endpoint (SPEC §6.3, optional).

Module-level metric singletons so importing the polling jobs from another
process won't double-register them. Worker increments them via the same
imports; web tier exposes them.
"""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
)

# Use a dedicated registry rather than the global default so test harnesses
# (which import the module multiple times) don't fight over duplicate names.
REGISTRY = CollectorRegistry()

POLLING_JOB_RUNS = Counter(
    "wifimon_polling_job_runs_total",
    "Number of polling jobs that have completed (by job id and outcome)",
    labelnames=("job", "outcome"),
    registry=REGISTRY,
)

POLLING_JOB_LAST_RESULT = Gauge(
    "wifimon_polling_job_last_result",
    "Number of items processed by the most recent run of each polling job",
    labelnames=("job",),
    registry=REGISTRY,
)

DASHBOARD_REQUESTS = Counter(
    "wifimon_dashboard_requests_total",
    "Number of GET /api/v1/dashboard requests served",
    labelnames=("mode",),  # "mock" | "db"
    registry=REGISTRY,
)

router = APIRouter()


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
