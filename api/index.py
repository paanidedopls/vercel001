import json
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI()

# Allow POST requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


class TelemetryRequest(BaseModel):
    regions: list[str]
    threshold_ms: float


def load_telemetry() -> list[dict[str, Any]]:
    """
    Load the telemetry bundle from telemetry.json.

    The function accepts either:
    - a top-level list of records
    - an object containing records under a common key
    """

    data_path = Path(__file__).resolve().parent.parent / "telemetry.json"

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("data", "records", "telemetry", "readings", "pings"):
            if key in data and isinstance(data[key], list):
                return data[key]

    raise ValueError("Could not find telemetry records in telemetry.json")


def get_field(record: dict[str, Any], *names: str):
    """Return the first matching field name."""
    for name in names:
        if name in record:
            return record[name]
    return None


def percentile_95(values: list[float]) -> float:
    """Calculate the 95th percentile using NumPy's default method."""
    return float(np.percentile(values, 95))


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/api/telemetry")
@app.post("/telemetry")
def telemetry_metrics(request: TelemetryRequest):

    records = load_telemetry()

    requested_regions = set(request.regions)

    result = {}

    for region in request.regions:

        region_records = []

        for record in records:

            record_region = get_field(
                record,
                "region",
                "regions"
            )

            if record_region == region:
                region_records.append(record)

        if not region_records:
            result[region] = {
                "avg_latency": 0,
                "p95_latency": 0,
                "avg_uptime": 0,
                "breaches": 0
            }
            continue

        latencies = []
        uptimes = []

        for record in region_records:

            latency = get_field(
                record,
                "latency",
                "latency_ms",
                "response_time",
                "response_time_ms"
            )

            uptime = get_field(
                record,
                "uptime",
                "uptime_pct",
                "uptime_percent"
            )

            if latency is not None:
                latencies.append(float(latency))

            if uptime is not None:
                uptimes.append(float(uptime))

        avg_latency = float(np.mean(latencies)) if latencies else 0
        p95_latency = percentile_95(latencies) if latencies else 0
        avg_uptime = float(np.mean(uptimes)) if uptimes else 0

        breaches = sum(
            1 for value in latencies
            if value > request.threshold_ms
        )

        result[region] = {
            "avg_latency": avg_latency,
            "p95_latency": p95_latency,
            "avg_uptime": avg_uptime,
            "breaches": breaches
        }

    return result