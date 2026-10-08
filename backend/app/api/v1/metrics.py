import time
from collections import defaultdict
from fastapi import APIRouter, Response

_request_counts: dict[str, int] = defaultdict(int)
_error_counts: dict[str, int] = defaultdict(int)
_total_latency_ms: dict[str, float] = defaultdict(float)
_active_requests: int = 0
_start_time: float = time.time()

router = APIRouter(tags=["metrics"])

def _fmt(v): return str(int(v)) if v == int(v) else f"{v:.3f}"

@router.get("/metrics")
async def prometheus_metrics() -> Response:
    uptime = time.time() - _start_time
    lines = [
        "# HELP db_explorer_requests_total Total HTTP requests by path.",
        "# TYPE db_explorer_requests_total counter",
    ]
    for p, c in sorted(_request_counts.items()):
        lines.append(f'db_explorer_requests_total{{path="{p}"}} {c}')
    lines += [
        "# HELP db_explorer_request_errors_total Total HTTP errors.",
        "# TYPE db_explorer_request_errors_total counter",
    ]
    for p, c in sorted(_error_counts.items()):
        lines.append(f'db_explorer_request_errors_total{{path="{p}"}} {c}')
    lines += [
        "# HELP db_explorer_request_latency_ms_sum Cumulative latency (ms).",
        "# TYPE db_explorer_request_latency_ms_sum counter",
    ]
    for p, l in sorted(_total_latency_ms.items()):
        lines.append(f'db_explorer_request_latency_ms_sum{{path="{p}"}} {_fmt(l)}')
    lines += [
        "# HELP db_explorer_active_requests Active requests.",
        "# TYPE db_explorer_active_requests gauge",
        f"db_explorer_active_requests {_active_requests}",
        "# HELP db_explorer_uptime_seconds Uptime (s).",
        "# TYPE db_explorer_uptime_seconds gauge",
        f"db_explorer_uptime_seconds {_fmt(uptime)}",
    ]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4; charset=utf-8")
