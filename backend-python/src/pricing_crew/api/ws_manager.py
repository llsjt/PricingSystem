"""WebSocket 连接管理模块，负责按任务广播智能体流式消息。"""

from __future__ import annotations

from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(task_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str) -> None:
        sockets = self.active_connections.get(task_id)
        if not sockets:
            return
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            self.active_connections.pop(task_id, None)

    async def broadcast(self, message: str, task_id: str) -> None:
        sockets = list(self.active_connections.get(task_id, []))
        for socket in sockets:
            try:
                await socket.send_text(message)
            except Exception:
                self.disconnect(socket, task_id)


manager = ConnectionManager()
