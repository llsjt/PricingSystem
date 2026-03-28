import asyncio


def win_selector_loop() -> asyncio.AbstractEventLoop:
    """
    自定义 uvicorn loop factory（无参数）：
    Windows 下强制创建 SelectorEventLoop，规避 Proactor accept WinError 10014。
    """
    return asyncio.SelectorEventLoop()
