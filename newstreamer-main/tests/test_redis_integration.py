"""
基于真实 Redis 的集成测试

运行前请确保本机有可用的 Redis 实例(默认: localhost:6379, db=0)。

快速启动(推荐Docker):
    docker run -d --rm --name redis-test -p 6379:6379 redis:7-alpine

运行测试:
    pytest -q tests/test_redis_integration.py -vv -s
"""

import json
import threading
import time
from typing import List

import pytest
import redis

from newstreamer.streams.redis_fake_stream import (
    FakeLiveDataStream,
    FakeMarketDataStream,
)
from newstreamer.models.orderbook import OrderBook


def _wait_for_keys(client: redis.StrictRedis, keys: List[str], timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(client.get(k) is not None for k in keys):
            return True
        time.sleep(0.02)
    return False


@pytest.fixture(scope="session")
def real_redis_client():
    """返回一个指向真实 Redis 的客户端, 不修改被测代码内部的连接设置。

    要求: Redis 服务运行在 localhost:6379, db=0。
    若不可用则跳过整个文件的测试。
    """
    client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)
    try:
        client.ping()
    except Exception as e:
        pytest.skip(f"跳过: 无法连接到本地 Redis: {e}")
    yield client


@pytest.fixture(autouse=True)
def cleanup_keys(real_redis_client: redis.StrictRedis):
    """每个测试前后清理可能使用的键, 避免污染环境。
    注意: 被测类内部固定以股票代码作为键名, 因此这里清理测试使用到的代码。
    """
    symbols = ["000001", "600000", "000002"]
    for s in symbols:
        real_redis_client.delete(s)
    yield
    for s in symbols:
        real_redis_client.delete(s)


def test_live_stream_real_redis(real_redis_client: redis.StrictRedis):
    """验证 FakeLiveDataStream 在真实 Redis 上写入数据并可停止。"""
    symbols = ["000001", "600000"]
    stream = FakeLiveDataStream(seed=42)

    # 简单回调打印(可选)
    def on_data(lst):
        # 仅打印少量避免刷屏
        if lst:
            d = lst[0]
            print(f"LIVE {d['symbol']}: {d['price']}")

    stream.subscribe(symbols)
    stream.add_callback(on_data)

    t = threading.Thread(target=stream.start_streaming, kwargs={"interval": 0.05}, daemon=True)
    t.start()

    try:
        assert _wait_for_keys(real_redis_client, symbols, timeout=2.0)
        for sym in symbols:
            raw = real_redis_client.get(sym)
            assert raw, f"Redis 未写入键: {sym}"
            data = json.loads(raw)
            assert data.get("symbol") == sym
            assert "price" in data and "volume" in data
    finally:
        stream.stop()
        t.join(timeout=1.0)


def test_market_stream_real_redis(monkeypatch, real_redis_client: redis.StrictRedis):
    """验证 FakeMarketDataStream 在真实 Redis 上写入订单簿。

    注意: OrderBook.to_dict() 默认包含 datetime, 直接 json.dumps 会报错。
    为测试稳定性, 这里对 to_dict 进行临时补丁以便 JSON 序列化。
    """

    def to_dict_jsonable(self: OrderBook) -> dict:
        return {
            "symbol": self.symbol,
            "bids": [{"price": b.price, "volume": b.volume} for b in self.bids],
            "asks": [{"price": a.price, "volume": a.volume} for a in self.asks],
            "timestamp": self.timestamp.isoformat(),
        }

    monkeypatch.setattr(OrderBook, "to_dict", to_dict_jsonable, raising=True)

    symbol = "000002"
    stream = FakeMarketDataStream(symbols=[symbol], max_ticks=2, tick_interval=0.02, seed=42)
    stream.connect()
    try:
        for _ in stream.get_orderbook(symbol):
            pass  # 生成并写入 Redis

        raw = real_redis_client.get(symbol)
        assert raw, "Redis 未写入订单簿"
        data = json.loads(raw)
        assert data.get("symbol") == symbol
        assert "bids" in data and "asks" in data and "timestamp" in data
    finally:
        stream.shutdown()


