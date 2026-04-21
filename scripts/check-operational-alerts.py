from __future__ import annotations

import argparse
import json
import urllib.request


def fetch_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check public beta health and task metrics against alert thresholds")
    parser.add_argument("--java-base-url", default="http://127.0.0.1:8080", help="Java backend base url")
    parser.add_argument("--python-base-url", default="http://127.0.0.1:8000", help="Python worker base url")
    parser.add_argument("--timeout", type=float, default=5.0, help="request timeout in seconds")
    parser.add_argument("--max-java-queue-depth", type=int, default=50)
    parser.add_argument("--max-python-queue-depth", type=int, default=50)
    parser.add_argument("--max-stale-running", type=int, default=3)
    parser.add_argument("--max-manual-review", type=int, default=20)
    parser.add_argument("--max-failed", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    java_metrics = fetch_json(f"{args.java_base_url.rstrip('/')}/api/health/metrics", args.timeout)
    python_metrics = fetch_json(f"{args.python_base_url.rstrip('/')}/health/metrics", args.timeout)

    breaches: list[str] = []
    if java_metrics.get("status") != "ok":
        breaches.append("java health degraded")
    if python_metrics.get("status") != "ok":
        breaches.append("python health degraded")

    java_tasks = java_metrics.get("tasks", {})
    python_tasks = python_metrics.get("tasks", {})

    if int(java_tasks.get("queueDepth", 0)) > args.max_java_queue_depth:
        breaches.append("java queue depth exceeded")
    if int(python_tasks.get("queueDepth", 0)) > args.max_python_queue_depth:
        breaches.append("python queue depth exceeded")
    if int(java_tasks.get("staleRunningTasks", 0)) > args.max_stale_running:
        breaches.append("java stale running tasks exceeded")
    if int(python_tasks.get("staleRunningTasks", 0)) > args.max_stale_running:
        breaches.append("python stale running tasks exceeded")
    if int(java_tasks.get("manualReview", 0)) > args.max_manual_review:
        breaches.append("java manual review backlog exceeded")
    if int(java_tasks.get("failed", 0)) > args.max_failed:
        breaches.append("java failed task count exceeded")

    report = {
        "java": java_metrics,
        "python": python_metrics,
        "breaches": breaches,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if breaches else 0


if __name__ == "__main__":
    raise SystemExit(main())
