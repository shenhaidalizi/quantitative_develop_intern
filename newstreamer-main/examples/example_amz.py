# examples/example_amz.py
# 用 Amazing_data_stream -> 写入 Redis -> 用 RedisMarketDataStreamReader 读取
import logging
import threading
import time
import os
from dotenv import load_dotenv

from newstreamer.streams.Amazing_data_stream import AmazingDataStream  # 真实数据源
from newstreamer.streams.redis_stream import RedisMarketDataStreamReader  # 从 Redis 读

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
USERNAME = os.getenv("AMZ_USERNAME")
PASSWORD = os.getenv("AMZ_PWD")
HOST = os.getenv("AMZ_HOST")
PORT = int(os.getenv("AMZ_PORT") or "80")


def main():
    symbols = ["000001", "600000"]

    # 1) Amazing 实时流：订阅 + 回调里写 Redis
    data_stream = AmazingDataStream(username=USERNAME, password=PASSWORD, host=HOST, port=PORT)
    data_stream.subscribe(symbols)


    # 2) Redis Reader：从 Redis 拉取并消费
    print("reader = RedisMarketDataStreamReader(return_type=\"dict\")")
    reader = RedisMarketDataStreamReader(return_type="dict")
    reader.subscribe(symbols)

    def reader_on_data(batch):
        # Redis 读取端得到的是 list[dict]，每个元素为写入的 payload
        if batch:
            d0 = batch[0]
            logger.info(f"Redis Reader -> {d0.get('symbol', 'N/A')}: {d0.get('price', 'N/A')}")

    reader.add_callback(reader_on_data)
    rt = threading.Thread(target=reader.start_streaming, kwargs={"interval": 0.5}, daemon=True)


    # 启动
    print("rt.start()")
    rt.start()
    time.sleep(10)

    # 停止
    reader.stop()
    data_stream.stop()
    wt.join(timeout=1.0)
    rt.join(timeout=1.0)


if __name__ == "__main__":
    main()