import asyncio
import sys

import uvicorn


def main() -> None:
    # Python 3.13 + Windows 下使用 Selector 事件循环，避免 uvicorn accept WinError 10014
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        loop="app.core.uvicorn_loop:win_selector_loop",
        http="h11",
        log_level="info",
    )


if __name__ == "__main__":
    main()
