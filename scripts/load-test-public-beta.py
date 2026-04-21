from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class TaskRunResult:
    task_id: int | None
    latency_ms: float
    ok: bool
    status: str
    message: str


def request_json(
    method: str,
    url: str,
    *,
    timeout: float,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    accept: str = "application/json",
) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": accept,
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def login(base_url: str, username: str, password: str, timeout: float) -> str:
    payload = request_json(
        "POST",
        f"{base_url.rstrip('/')}/api/user/login",
        timeout=timeout,
        payload={"username": username, "password": password},
    )
    if payload.get("code") != 200 or not payload.get("data", {}).get("token"):
        raise RuntimeError(f"login failed: {payload.get('message')}")
    return str(payload["data"]["token"])


def create_task(base_url: str, token: str, product_id: int, strategy_goal: str, constraints: str, timeout: float) -> TaskRunResult:
    started_at = time.perf_counter()
    try:
        payload = request_json(
            "POST",
            f"{base_url.rstrip('/')}/api/pricing/tasks",
            timeout=timeout,
            token=token,
            payload={
                "productId": product_id,
                "strategyGoal": strategy_goal,
                "constraints": constraints,
            },
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        ok = payload.get("code") == 200 and payload.get("data") is not None
        return TaskRunResult(
            task_id=int(payload["data"]) if ok else None,
            latency_ms=latency_ms,
            ok=ok,
            status="accepted" if ok else "rejected",
            message=str(payload.get("message") or ""),
        )
    except urllib.error.HTTPError as exc:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return TaskRunResult(task_id=None, latency_ms=latency_ms, ok=False, status=f"http_{exc.code}", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return TaskRunResult(task_id=None, latency_ms=latency_ms, ok=False, status="error", message=str(exc))


def consume_sse(base_url: str, token: str, task_id: int, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/pricing/tasks/{task_id}/events",
        method="GET",
        headers={
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {token}",
        },
    )

    terminal_event: dict[str, Any] = {
        "taskId": task_id,
        "terminalType": "timeout",
        "status": "UNKNOWN",
        "message": "",
    }
    with urllib.request.urlopen(request, timeout=timeout) as response:
        buffer = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            chunk = response.readline().decode("utf-8")
            if not chunk:
                break
            if chunk.startswith("data:"):
                buffer += chunk[5:].strip()
                continue
            if chunk.strip():
                continue
            if not buffer:
                continue
            payload = json.loads(buffer)
            buffer = ""
            event_type = str(payload.get("type") or "")
            if event_type in {"task_completed", "task_failed"}:
                terminal_event["terminalType"] = event_type
                terminal_event["status"] = str(payload.get("status") or "")
                terminal_event["message"] = str(payload.get("message") or "")
                break
    return terminal_event


def write_report(report_file: str | None, payload: dict[str, Any]) -> None:
    if not report_file:
        return
    path = Path(report_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Public beta pricing task load test helper")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="Java public API base url")
    parser.add_argument("--username", required=True, help="login username")
    parser.add_argument("--password", required=True, help="login password")
    parser.add_argument("--product-id", type=int, required=True, help="product id used to create tasks")
    parser.add_argument("--strategy-goal", default="MAX_PROFIT", help="strategy goal payload")
    parser.add_argument("--constraints", default="压测任务，请勿应用结果", help="constraints payload")
    parser.add_argument("--requests", type=int, default=20, help="number of task creation requests")
    parser.add_argument("--concurrency", type=int, default=10, help="parallel workers")
    parser.add_argument("--timeout", type=float, default=20.0, help="per request timeout in seconds")
    parser.add_argument("--sse-watchers", type=int, default=3, help="number of created tasks to attach SSE readers to")
    parser.add_argument("--report-file", help="optional json report output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = login(args.base_url, args.username, args.password, args.timeout)

    started_at = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(args.concurrency, 1)) as executor:
        futures = [
            executor.submit(
                create_task,
                args.base_url,
                token,
                args.product_id,
                args.strategy_goal,
                args.constraints,
                args.timeout,
            )
            for _ in range(max(args.requests, 1))
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    successful = [item for item in results if item.ok and item.task_id is not None]
    latencies = [item.latency_ms for item in results]
    sse_results: list[dict[str, Any]] = []
    for item in successful[: max(args.sse_watchers, 0)]:
        sse_results.append(consume_sse(args.base_url, token, int(item.task_id), args.timeout))

    report = {
        "baseUrl": args.base_url,
        "requests": len(results),
        "concurrency": max(args.concurrency, 1),
        "successful": len(successful),
        "failed": len(results) - len(successful),
        "totalElapsedMs": elapsed_ms,
        "latency": {
            "minMs": min(latencies) if latencies else 0,
            "avgMs": round(statistics.mean(latencies), 2) if latencies else 0,
            "p95Ms": round(sorted(latencies)[max(int(len(latencies) * 0.95) - 1, 0)], 2) if latencies else 0,
            "maxMs": max(latencies) if latencies else 0,
        },
        "taskIds": [item.task_id for item in successful],
        "sse": sse_results,
        "results": [asdict(item) for item in results],
    }

    write_report(args.report_file, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
