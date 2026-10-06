import json
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# Allow requests from every origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add the required CORS header to every response.
@app.middleware("http")
async def force_cors(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


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
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError("Invalid telemetry.json format")


def get_field(record: dict[str, Any], *names: str):
    for name in names:
        if name in record:
            return record[name]
    return None


def calculate_metrics(request: TelemetryRequest):
    records = load_telemetry()
    result = {}

    for region in request.regions:

        region_records = [
            r
            for r in records
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
                "response_time_ms",
            )

            uptime = get_field(
                record,
                "uptime",
                "uptime_pct",
                "uptime_percent",
            )

            if latency is not None:
                latencies.append(float(latency))

            if uptime is not None:
                uptimes.append(float(uptime))

        result[region] = {
            "avg_latency": float(np.mean(latencies)) if latencies else 0,
            "p95_latency": (
                float(np.percentile(latencies, 95))
                if latencies
                else 0
            ),
            "avg_uptime": float(np.mean(uptimes)) if uptimes else 0,
            "breaches": sum(
                1 for value in latencies
                if value > request.threshold_ms
            ),
        }

    return result


@app.get("/")
def root():
    return {"status": "ok"}


# Support the likely endpoint paths.
@app.post("/")
def telemetry_root(request: TelemetryRequest):
    return JSONResponse(
        content=calculate_metrics(request),
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/api")
def telemetry_api(request: TelemetryRequest):
    return JSONResponse(
        content=calculate_metrics(request),
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/api/telemetry")
def telemetry_api_path(request: TelemetryRequest):
    return JSONResponse(
        content=calculate_metrics(request),
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/telemetry")
def telemetry_path(request: TelemetryRequest):
    return JSONResponse(
        content=calculate_metrics(request),
        headers={"Access-Control-Allow-Origin": "*"},
    )