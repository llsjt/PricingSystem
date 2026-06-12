from __future__ import annotations

import argparse
import math
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def int_value(mapping: dict[str, Any], key: str) -> int:
    try:
        return int(mapping.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def threshold_breaches(args: argparse.Namespace, java_metrics: dict[str, Any], python_metrics: dict[str, Any]) -> list[str]:
    breaches: list[str] = []
    java_tasks = java_metrics.get("tasks", {}) if isinstance(java_metrics.get("tasks"), dict) else {}
    python_tasks = python_metrics.get("tasks", {}) if isinstance(python_metrics.get("tasks"), dict) else {}
    python_runtime = python_metrics.get("runtime", {}) if isinstance(python_metrics.get("runtime"), dict) else {}

    if java_metrics.get("status") != "ok":
        breaches.append("java health degraded")
    if python_metrics.get("status") != "ok":
        breaches.append("python health degraded")
    if int_value(java_tasks, "queueDepth") > args.max_java_queue_depth:
        breaches.append("java queue depth exceeded")
    if int_value(python_tasks, "queueDepth") > args.max_python_queue_depth:
        breaches.append("python queue depth exceeded")
    if int_value(java_tasks, "staleRunningTasks") > args.max_stale_running:
        breaches.append("java stale running tasks exceeded")
    if int_value(python_tasks, "staleRunningTasks") > args.max_stale_running:
        breaches.append("python stale running tasks exceeded")
    if int_value(java_tasks, "manualReview") > args.max_manual_review:
        breaches.append("java manual review backlog exceeded")
    if int_value(java_tasks, "failed") > args.max_failed:
        breaches.append("java failed task count exceeded")
    if int_value(python_tasks, "consumerRetryCount") > args.max_consumer_retry:
        breaches.append("python consumer retry count exceeded")
    if int_value(python_runtime, "casConflictCount") > args.max_cas_conflicts:
        breaches.append("python CAS conflict count exceeded")
    if int_value(python_runtime, "retryPublishFailureCount") > args.max_retry_publish_failures:
        breaches.append("python retry publish failure count exceeded")
    if int_value(python_runtime, "progressPublishFailureCount") > args.max_progress_publish_failures:
        breaches.append("python progress publish failure count exceeded")
    if int_value(python_runtime, "llmTimeoutCount") > args.max_llm_timeouts:
        breaches.append("python LLM timeout count exceeded")
    if int_value(python_runtime, "manualReviewWithoutResultCount") > args.max_manual_review_without_result:
        breaches.append("python manual review without result count exceeded")
    return breaches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observe gray rollout metrics and write an auditable report")
    parser.add_argument("--java-base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--python-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--duration-minutes", type=float, default=30.0)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--samples", type=int, default=0, help="override duration with an exact sample count")
    parser.add_argument("--output-dir", default="ops/reports/runtime")
    parser.add_argument("--max-java-queue-depth", type=int, default=50)
    parser.add_argument("--max-python-queue-depth", type=int, default=50)
    parser.add_argument("--max-stale-running", type=int, default=3)
    parser.add_argument("--max-manual-review", type=int, default=20)
    parser.add_argument("--max-failed", type=int, default=20)
    parser.add_argument("--max-consumer-retry", type=int, default=10)
    parser.add_argument("--max-cas-conflicts", type=int, default=0)
    parser.add_argument("--max-retry-publish-failures", type=int, default=0)
    parser.add_argument("--max-progress-publish-failures", type=int, default=0)
    parser.add_argument("--max-llm-timeouts", type=int, default=5)
    parser.add_argument("--max-manual-review-without-result", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    samples_path = output_dir / f"gray-rollout-samples-{stamp}.jsonl"
    summary_path = output_dir / f"gray-rollout-summary-{stamp}.json"

    sample_count = args.samples if args.samples > 0 else max(1, math.ceil((args.duration_minutes * 60) / max(args.interval_seconds, 1)) + 1)
    all_breaches: list[dict[str, Any]] = []
    samples_written = 0

    with samples_path.open("w", encoding="utf-8") as fh:
        for index in range(sample_count):
            observed_at = datetime.now(timezone.utc).isoformat()
            try:
                java_metrics = fetch_json(f"{args.java_base_url.rstrip('/')}/api/health/metrics", args.timeout)
                python_metrics = fetch_json(f"{args.python_base_url.rstrip('/')}/health/metrics", args.timeout)
                breaches = threshold_breaches(args, java_metrics, python_metrics)
                sample = {
                    "index": index + 1,
                    "observedAt": observed_at,
                    "java": java_metrics,
                    "python": python_metrics,
                    "breaches": breaches,
                }
            except Exception as exc:  # noqa: BLE001
                breaches = [f"metrics fetch failed: {exc}"]
                sample = {
                    "index": index + 1,
                    "observedAt": observed_at,
                    "error": str(exc),
                    "breaches": breaches,
                }
            fh.write(json.dumps(sample, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            samples_written += 1
            if breaches:
                all_breaches.append({"index": index + 1, "observedAt": observed_at, "breaches": breaches})
            if index < sample_count - 1:
                time.sleep(max(args.interval_seconds, 0))

    finished = datetime.now(timezone.utc)
    summary = {
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
        "durationSeconds": round((finished - started).total_seconds(), 3),
        "samples": samples_written,
        "samplesPath": str(samples_path),
        "breachCount": len(all_breaches),
        "breaches": all_breaches,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if all_breaches else 0


if __name__ == "__main__":
    raise SystemExit(main())
