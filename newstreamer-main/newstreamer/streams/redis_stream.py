"""Redis 读取流实现。

提供基于 Redis 的市场数据读取流，按订阅的股票列表轮询 Redis 并通过回调输出数据。
"""

from typing import List, Optional, Dict, Any
import logging
import time

from newstreamer.streams.base import LiveDataStreamBase
from newstreamer.streams.to_redis import RedisClient
from newstreamer.models.market_data import MarketData


logger = logging.getLogger(__name__)


class RedisMarketDataStreamReader(LiveDataStreamBase):
    """基于 Redis 的市场数据读取流(回调模式)。

    周期性从 Redis 读取订阅股票的最新数据，触发回调。
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        return_type: str = "dict",
    ):
        super().__init__()
        self.redis_client = RedisClient(host=host, port=port, db=db)
        self.return_type = return_type
        self.latest_data: Dict[str, Any] = {}

    def subscribe(self, subscribe_symbols: List[str]):
        self.subscribe_symbols = subscribe_symbols
        logger.info("RedisReader 已订阅: %s", subscribe_symbols)

    def unsubscribe(self):
        self.subscribe_symbols = []
        self.latest_data = {}
        logger.info("RedisReader 已取消所有订阅")

    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        return self.latest_data.copy() if self.latest_data else None

    def start_streaming(self, interval: int = 1):
        if not self.subscribe_symbols:
            logger.warning("RedisReader 未订阅任何股票，无法启动")
            return

        self._is_running = True
        logger.info("RedisReader 开始读取，间隔: %s 秒", interval)

        try:
            while self._is_running:
                data_list: List[Any] = []
                for symbol in self.subscribe_symbols:
                    item = self.redis_client.get_data(symbol)
                    if not item:
                        continue

                    self.latest_data[symbol] = item
                    if self.return_type == "object":
                        try:
                            md = MarketData(**item)
                            data_list.append(md)
                        except Exception:
                            # 字段不匹配等情况下回退为原始字典
                            data_list.append(item)
                    else:
                        data_list.append(item)

                if data_list:
                    self.on_market_data(data_list)

                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("RedisReader 收到中断信号，停止")
            self.stop()
        except Exception as e:
            logger.error("RedisReader 发生错误: %s", str(e))
            self.stop()
            raise

    def stop(self):
        self._is_running = False
        logger.info("RedisReader 已停止")


