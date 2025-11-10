"""Redis 写入/读取流水线示例。

演示: 使用 FakeLiveDataStream 写入 Redis，然后用 RedisMarketDataStreamReader 读取并消费。

运行:
    python examples/example_redis_pipeline.py
前置:
    - 安装依赖: pip install -r requirements.txt
    - 确保本机 Redis 可用(或使用 docker run -d --rm -p 6379:6379 redis:7-alpine)
"""

import logging
import threading
import time

from newstreamer.streams.redis_fake_stream import FakeLiveDataStream
from newstreamer.streams.redis_stream import RedisMarketDataStreamReader


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    symbols = ["000001", "600000"]

    # 写入端: 伪实时数据 -> Redis
    writer = FakeLiveDataStream(seed=42)
    writer.subscribe(symbols)

    def writer_log(data_list):
        if data_list:
            d0 = data_list[0]
            logger.info("Writer: %s %s", d0.get("symbol"), d0.get("price"))

    writer.add_callback(writer_log)
    
    
    
    
    # 读取端: 从 Redis 读 -> 回调消费
    reader = RedisMarketDataStreamReader(return_type="dict")
    reader.subscribe(symbols)

    def reader_log(data_list):
        if data_list:
            d0 = data_list[0]
            logger.info("Reader: %s %s", d0.get("symbol"), d0.get("price"))

    reader.add_callback(reader_log)

    wt = threading.Thread(target=writer.start_streaming, kwargs={"interval": 0.2}, daemon=True)
    rt = threading.Thread(target=reader.start_streaming, kwargs={"interval": 0.2}, daemon=True)

    wt.start()
    rt.start()
    
    time.sleep(5)  # 演示运行 5 秒
    writer.stop()
    reader.stop()
    wt.join(timeout=1.0)
    rt.join(timeout=1.0)


if __name__ == "__main__":
    main()


