"""
LLM 连通性测试脚本
==================
独立测试 DashScope API 是否可用，不依赖 CrewAI 框架。
用法: python -m tests.test_llm_connectivity
"""

import json
import sys
import time
from pathlib import Path

import httpx

# 加载 .env 配置
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings


def test_llm_connectivity() -> None:
    """直接调用 DashScope API，验证 API key、base_url、model 是否可用。"""
    settings = get_settings()

    api_key = settings.llm_api_key
    base_url = settings.llm_base_url.rstrip("/")
    model = settings.llm_model

    print("=" * 60)
    print("LLM 连通性测试")
    print("=" * 60)
    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"  API Key: {api_key}")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  Timeout: {settings.crewai_llm_timeout_seconds}s")
    print()

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请回复两个字：成功"}],
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print(f"正在发送请求到 {url} ...")
    t0 = time.time()
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0, read=50.0)) as client:
            resp = client.post(url, json=payload, headers=headers)
        elapsed = time.time() - t0

        print(f"HTTP 状态码: {resp.status_code} (耗时 {elapsed:.1f}s)")
        print()

        if resp.status_code != 200:
            print(f"[失败] 响应体: {resp.text[:500]}")
            return

        data = resp.json()
        # 打印 token 用量
        usage = data.get("usage", {})
        print(f"Token 用量: {json.dumps(usage, ensure_ascii=False)}")

        # 打印模型响应
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            print(f"模型响应: {content}")
        print()
        print("[成功] LLM API 连通正常！")

    except httpx.TimeoutException as exc:
        elapsed = time.time() - t0
        print(f"[失败] 请求超时 (耗时 {elapsed:.1f}s): {exc}")
    except httpx.RequestError as exc:
        elapsed = time.time() - t0
        print(f"[失败] 请求错误 (耗时 {elapsed:.1f}s): {exc}")
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"[失败] 未知错误 (耗时 {elapsed:.1f}s): {exc}")


if __name__ == "__main__":
    test_llm_connectivity()
