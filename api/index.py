import json
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


app = FastAPI()


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Expose-Headers": "Access-Control-Allow-Origin",
}


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return JSONResponse(
            content={"ok": True},
            headers=CORS_HEADERS,
        )

    response = await call_next(request)

    for key, value in CORS_HEADERS.items():
        response.headers[key] = value

    return response


# ============================================================
# Request model
# ============================================================

class TelemetryRequest(BaseModel):
    regions: list[str]
    threshold_ms: float


# ============================================================
# Load telemetry
# ============================================================

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


# ============================================================
# Helpers
# ============================================================

def get_field(record: dict[str, Any], *names: str):
    for name in names:
        if name in record:
            return record[name]
    return None


# ============================================================
# Calculate metrics
# ============================================================

def calculate_metrics(request: TelemetryRequest):

    records = load_telemetry()

    result = {}

    for region in request.regions:

        region_records = [
            record
            for record in records
            if get_field(record, "region", "regions") == region
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
            "avg_latency": (
                float(np.mean(latencies))
                if latencies
                else 0
            ),

            "p95_latency": (
                float(np.percentile(latencies, 95))
                if latencies
                else 0
            ),

            "avg_uptime": (
                float(np.mean(uptimes))
                if uptimes
                else 0
            ),

            "breaches": sum(
                1
                for value in latencies
                if value > request.threshold_ms
            ),
        }

    return result


# ============================================================
# Routes
# ============================================================

@app.get("/")
def root():
    return JSONResponse(
        content={"status": "ok"},
        headers=CORS_HEADERS,
    )


@app.post("/api/telemetry")
def telemetry_api(request: TelemetryRequest):

    metrics = calculate_metrics(request)

    return JSONResponse(
        content={
            "regions": metrics
        },
        headers=CORS_HEADERS,
    )


@app.post("/telemetry")
def telemetry(request: TelemetryRequest):

    metrics = calculate_metrics(request)

    return JSONResponse(
        content={
            "regions": metrics
        },
        headers=CORS_HEADERS,
    )


@app.post("/")
def telemetry_root(request: TelemetryRequest):

    metrics = calculate_metrics(request)

    return JSONResponse(
        content={
            "regions": metrics
        },
        headers=CORS_HEADERS,
    )