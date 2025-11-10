# tests/test_redis_fake_stream.py
import json
import threading
import time
from typing import List

import pytest

# 被测模块与模型
from newstreamer.streams.redis_fake_stream import (
    FakeLiveDataStream,
    FakeMarketDataStream,
)
import newstreamer.streams.redis_fake_stream as rfs
from newstreamer.models.orderbook import OrderBook


@pytest.fixture(autouse=True)
def patch_redis_to_fakeredis(monkeypatch):
    """
    使用 fakeredis 替换 redis.StrictRedis，避免依赖真实 Redis 服务。
    需要: pip install fakeredis
    """
    import fakeredis

    monkeypatch.setattr(rfs.redis, "StrictRedis", fakeredis.FakeStrictRedis)


def _wait_for_keys(client, keys: List[str], timeout: float = 2.0) -> bool:
    """在超时时间内轮询等待 Redis 中出现指定键。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(client.get(k) is not None for k in keys):
            return True
        time.sleep(0.02)
    return False


def test_live_stream_writes_to_redis_and_latest_data():
    """
    验证 FakeLiveDataStream:
    - 正常启动并推送一次数据
    - 将数据写入 Redis
    - latest_data 返回最新内存数据
    """
    symbols = ["000001", "600000"]
    stream = FakeLiveDataStream(seed=42)
    stream.subscribe(symbols)

    t = threading.Thread(target=stream.start_streaming, kwargs={"interval": 0.01}, daemon=True)
    t.start()

    try:
        assert _wait_for_keys(stream.redis_client, symbols, timeout=1.5)
        for sym in symbols:
            raw = stream.redis_client.get(sym)
            assert raw, f"Redis 未找到键: {sym}"
            data = json.loads(raw)
            assert data["symbol"] == sym
            assert "price" in data and "volume" in data

        latest = stream.get_latest_data()
        assert isinstance(latest, dict) and set(symbols).issubset(latest.keys())
    finally:
        stream.stop()
        t.join(timeout=1.0)


def test_market_stream_writes_orderbook_to_redis(monkeypatch):
    """
    验证 FakeMarketDataStream:
    - 生成一个订单簿并写入 Redis
    - 补丁 OrderBook.to_dict 使其 JSON 可序列化(将 datetime 转为字符串)
    """
    def to_dict_jsonable(self: OrderBook) -> dict:
        return {
            "symbol": self.symbol,
            "bids": [{"price": b.price, "volume": b.volume} for b in self.bids],
            "asks": [{"price": a.price, "volume": a.volume} for a in self.asks],
            "timestamp": self.timestamp.isoformat(),
        }

    monkeypatch.setattr(OrderBook, "to_dict", to_dict_jsonable, raising=True)

    symbol = "000001"
    stream = FakeMarketDataStream(
        symbols=[symbol],
        max_ticks=1,
        tick_interval=0.0,
        seed=42,
    )
    stream.connect()
    try:
        gen = stream.get_orderbook(symbol)
        ob = next(gen)  # 触发一次生成与写入 Redis
        assert isinstance(ob, OrderBook)

        raw = stream.redis_client.get(symbol)
        assert raw, "Redis 未写入订单簿数据"
        data = json.loads(raw)
        assert data["symbol"] == symbol
        assert "bids" in data and "asks" in data and "timestamp" in data
    finally:
        stream.disconnect()