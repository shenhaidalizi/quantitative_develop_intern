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
        self.client = redis.StrictRedis(
            host=host,
            port=port,
            db=db,
            username=username,
            password=password,
            decode_responses=True,
        )
        self.prefix = prefix or ""
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
        try:
            return self.client.acl_whoami()  # 便于确认当前 ACL 用户
        except Exception:
            return "unknown"

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

    # Key 遍历（生产建议使用 scan_iter）
    def scan_iter(self, pattern: str = "*") -> Iterable[str]:
        pat = self._k(pattern)
        for k in self.client.scan_iter(pat):
            yield k

    def keys(self, pattern: str = "*") -> list:
        return self.client.keys(self._k(pattern))


# 加载 .env（注意包含 # 的密码必须加引号）
load_dotenv()

# 连接参数
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "")

# 兼容：既支持单账号，也支持读写分离账号
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_WRITE_USERNAME = os.getenv("REDIS_WRITE_USERNAME", REDIS_USERNAME)
REDIS_WRITE_PASSWORD = os.getenv("REDIS_WRITE_PASSWORD", REDIS_PASSWORD)
REDIS_READ_USERNAME = os.getenv("REDIS_READ_USERNAME", REDIS_USERNAME)
REDIS_READ_PASSWORD = os.getenv("REDIS_READ_PASSWORD", REDIS_PASSWORD)


def main() -> None:
    # 用写账号写入，用读账号读取（与 CLI 行为一致）
    writer = RedisClient(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        username=REDIS_WRITE_USERNAME,
        password=REDIS_WRITE_PASSWORD,
        prefix=REDIS_PREFIX,
    )
    reader = RedisClient(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        username=REDIS_READ_USERNAME,
        password=REDIS_READ_PASSWORD,
        prefix=REDIS_PREFIX,
    )

    key = "hc"  # 实际键为 prefix + "hc"，例如 "teamPublic:hc"
    writer.write_data(key, 1)
    print(f"write whoami={writer.whoami()}, key={writer._k(key)}")

    val = reader.get_data(key)
    print(f"read  whoami={reader.whoami()}, value={val}")


if __name__ == "__main__":
    main()