import json
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# CORS
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
    path = Path(__file__).resolve().parent.parent / "telemetry.json"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("data", "records", "telemetry", "readings", "pings"):
            if key in data and isinstance(data[key], list):
                return data[key]

    raise ValueError("Invalid telemetry.json format")


def get_field(record: dict[str, Any], *names: str):
    for name in names:
        if name in record:
            return record[name]
    return None


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/api/telemetry")
@app.post("/telemetry")
def telemetry(request: TelemetryRequest):

    records = load_telemetry()
    result = {}

    for region in request.regions:

        region_records = [
            r for r in records
            if get_field(r, "region", "regions") == region
        ]

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

        result[region] = {
            "avg_latency": float(np.mean(latencies)) if latencies else 0,
            "p95_latency": float(np.percentile(latencies, 95)) if latencies else 0,
            "avg_uptime": float(np.mean(uptimes)) if uptimes else 0,
            "breaches": sum(
                1 for x in latencies
                if x > request.threshold_ms
            )
        }

    return result