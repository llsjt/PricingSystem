import redis
import json
from typing import Any, Optional
from app.core.config import settings

class RedisClient:
    """
    RedisClient
    用于管理 Redis 连接，提供任务状态缓存、Agent 结果缓存和消息发布/订阅能力。
    """

    def __init__(self):
        # 暂时使用 Mock 连接或惰性连接
        self._client = None
        self._connected = False

    @property
    def client(self) -> redis.Redis:
        """
        获取 Redis 客户端实例（惰性加载）
        """
        if not self._client:
            try:
                self._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=True
                )
                # 尝试 ping 确认连接
                # self._client.ping()
                self._connected = True
            except Exception as e:
                print(f"[Redis] Connection warning: {e}. Using mock mode.")
                self._connected = False
        return self._client

    def cache_task_status(self, task_id: str, status: str, expire: int = 3600):
        """
        缓存任务状态
        :param task_id: 任务ID
        :param status: 状态 (processing/completed/failed)
        :param expire: 过期时间(秒)
        """
        if not self._connected: return
        key = f"task:status:{task_id}"
        self.client.set(key, status, ex=expire)

    def get_task_status(self, task_id: str) -> Optional[str]:
        """
        获取任务状态
        """
        if not self._connected: return None
        key = f"task:status:{task_id}"
        return self.client.get(key)

    def cache_agent_result(self, product_id: str, result: Dict[str, Any], expire: int = 86400):
        """
        缓存 Agent 分析结果
        :param product_id: 商品ID
        :param result: 结果字典
        :param expire: 过期时间(秒)
        """
        if not self._connected: return
        key = f"agent:result:{product_id}"
        self.client.set(key, json.dumps(result), ex=expire)

    def get_agent_result(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 Agent 分析结果缓存
        """
        if not self._connected: return None
        key = f"agent:result:{product_id}"
        data = self.client.get(key)
        return json.loads(data) if data else None

    def publish_task_event(self, channel: str, message: Dict[str, Any]):
        """
        发布任务事件消息
        """
        if not self._connected: return
        self.client.publish(channel, json.dumps(message))

    def subscribe_task_event(self, channel: str):
        """
        订阅任务事件消息 (生成器)
        """
        if not self._connected: return
        pubsub = self.client.pubsub()
        pubsub.subscribe(channel)
        for message in pubsub.listen():
            if message['type'] == 'message':
                yield json.loads(message['data'])

# 单例导出
redis_client = RedisClient()
