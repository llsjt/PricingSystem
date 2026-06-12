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
    parser.add_argument("--max-consumer-retry", type=int, default=10)
    parser.add_argument("--max-cas-conflicts", type=int, default=0)
    parser.add_argument("--max-retry-publish-failures", type=int, default=0)
    parser.add_argument("--max-progress-publish-failures", type=int, default=0)
    parser.add_argument("--max-llm-timeouts", type=int, default=5)
    parser.add_argument("--max-manual-review-without-result", type=int, default=0)
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
    python_runtime = python_metrics.get("runtime", {})

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
    if int(python_tasks.get("consumerRetryCount", 0)) > args.max_consumer_retry:
        breaches.append("python consumer retry count exceeded")
    if int(python_runtime.get("casConflictCount", 0)) > args.max_cas_conflicts:
        breaches.append("python CAS conflict count exceeded")
    if int(python_runtime.get("retryPublishFailureCount", 0)) > args.max_retry_publish_failures:
        breaches.append("python retry publish failure count exceeded")
    if int(python_runtime.get("progressPublishFailureCount", 0)) > args.max_progress_publish_failures:
        breaches.append("python progress publish failure count exceeded")
    if int(python_runtime.get("llmTimeoutCount", 0)) > args.max_llm_timeouts:
        breaches.append("python LLM timeout count exceeded")
    if int(python_runtime.get("manualReviewWithoutResultCount", 0)) > args.max_manual_review_without_result:
        breaches.append("python manual review without result count exceeded")

    report = {
        "java": java_metrics,
        "python": python_metrics,
        "breaches": breaches,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if breaches else 0


if __name__ == "__main__":
    raise SystemExit(main())
