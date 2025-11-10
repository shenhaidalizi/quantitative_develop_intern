import os
import json
import logging
from typing import Any, Optional, Dict, Iterable
from datetime import datetime, date

import redis
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        username: Optional[str] = None,
        password: Optional[str] = None,
        prefix: str = "",
    ):
        """
        Args:
            host: Redis 主机
            port: Redis 端口
            db:   数据库索引
            username: ACL 用户名（Redis 6+）
            password: 密码/令牌
            prefix:   键前缀（如 'teamPublic:'）
        """
        self.username = username
        self.client = redis.StrictRedis(
            host=host,
            port=port,
            db=db,
            username=username,
            password=password,
            decode_responses=True,
        )
        # 规范化前缀：自动补冒号，避免 'teamPublichc' 这种不匹配 ACL 的键
        self.prefix = prefix or ""
        if self.prefix and not self.prefix.endswith(":"):
            self.prefix += ":"
        self._check_connection(host, port, db, username)

    def _check_connection(self, host: str, port: int, db: int, username: Optional[str]):
        try:
            self.client.ping()
            who = f"{username or 'default'}@{host}:{port}/{db}"
            logger.info(f"成功连接到 Redis ({who})")
        except redis.ConnectionError:
            logger.error("无法连接到 Redis")
            raise

    def _json_default(self, obj: Any):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return str(obj)

    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}" if self.prefix and not key.startswith(self.prefix) else key

    def whoami(self) -> str:
        # 不使用 ACL WHOAMI（很多受限用户无权限）；直接返回连接使用的用户名
        return self.username or "default"

    # String: SET/GET
    def write_data(self, key: str, data: Any):
        try:
            payload = json.dumps(data, ensure_ascii=False, default=self._json_default)
            self.client.set(self._k(key), payload)
            logger.info(f"数据成功写入 Redis，key: {self._k(key)}")
        except Exception as e:
            logger.error(f"写入数据到 Redis 失败: {str(e)}")

    def get_data(self, key: str) -> Any:
        try:
            data = self.client.get(self._k(key))
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"从 Redis 获取数据失败: {str(e)}")
            return None

    # Hash: HSET/HGETALL
    def write_hash_field(self, key: str, field: str, data: Any) -> None:
        try:
            payload = json.dumps(data, ensure_ascii=False, default=self._json_default)
            self.client.hset(self._k(key), field, payload)
        except Exception as e:
            logger.error(f"HSET 失败: {str(e)}")
            raise

    def read_hash_all(self, key: str) -> Dict[str, Any]:
        try:
            raw = self.client.hgetall(self._k(key))
            return {k: json.loads(v) for k, v in raw.items()}
        except Exception as e:
            logger.error(f"HGETALL 失败: {str(e)}")
            return {}

    # Key 遍历
    def scan_iter(self, pattern: str = "*") -> Iterable[str]:
        pat = self._k(pattern)
        for k in self.client.scan_iter(pat):
            yield k

    def keys(self, pattern: str = "*") -> list:
        return self.client.keys(self._k(pattern))

