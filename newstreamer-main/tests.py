#!/usr/bin/env python
"""
快速验证脚本

验证newstreamer包的所有核心功能是否正常工作。
"""

import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_imports():
    """测试所有导入"""
    logger.info("=" * 60)
    logger.info("测试1: 检查导入")
    logger.info("=" * 60)
    
    try:
        from newstreamer.models.orderbook import OrderBook, OrderBookLevel
        from newstreamer.models.market_data import MarketData, BookSnapshotData
        from newstreamer.streams.base import DataStreamBase, LiveDataStreamBase
        from newstreamer.streams.fake_stream import FakeMarketDataStream, FakeLiveDataStream
        from newstreamer.streams.csv_stream import CSVMarketDataStream
        from newstreamer.utils.generators import (
            RandomWalkPriceGenerator,
            RandomOrderBookGenerator,
            RandomMarketDataGenerator
        )
        logger.info("✓ 所有模块导入成功")
        return True
    except Exception as e:
        logger.error(f"✗ 导入失败: {str(e)}")
        return False


def test_fake_generator_stream():
    """测试Fake生成器数据流"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: Fake生成器数据流")
    logger.info("=" * 60)
    
    try:
        from newstreamer.streams.fake_stream import FakeMarketDataStream
        
        stream = FakeMarketDataStream(
            symbols=['TEST001'],
            max_ticks=5,
            tick_interval=0,
            seed=42
        )
        
        stream.connect()
        orderbooks = list(stream.get_orderbook('TEST001'))
        stream.shutdown()
        
        assert len(orderbooks) == 5, "应该生成5个tick"
        assert orderbooks[0].symbol == 'TEST001', "股票代码应该是TEST001"
        assert orderbooks[0].get_mid_price() > 0, "中间价应该大于0"
        
        logger.info(f"✓ 生成了 {len(orderbooks)} 个订单簿")
        logger.info(f"  - 第一个tick中间价: {orderbooks[0].get_mid_price():.2f}")
        logger.info(f"  - 最佳买价: {orderbooks[0].get_bid(0):.2f}")
        logger.info(f"  - 最佳卖价: {orderbooks[0].get_ask(0):.2f}")
        
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_fake_live_stream():
    """测试Fake实时数据流"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: Fake实时数据流")
    logger.info("=" * 60)
    
    try:
        from newstreamer.streams.fake_stream import FakeLiveDataStream
        import threading
        import time
        
        received_count = [0]
        
        def callback(data_list):
            received_count[0] += len(data_list)
            if received_count[0] >= 2:
                stream.stop()
        
        stream = FakeLiveDataStream(seed=42)
        stream.subscribe(['TEST001', 'TEST002'])
        stream.add_callback(callback)
        
        # 在线程中运行
        thread = threading.Thread(
            target=lambda: stream.start_streaming(interval=0.5),
            daemon=True
        )
        thread.start()
        thread.join(timeout=3)
        
        stream.stop()
        
        assert received_count[0] >= 2, f"应该至少收到2条数据，实际: {received_count[0]}"
        
        logger.info(f"✓ 收到 {received_count[0]} 条数据")
        
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_generators():
    """测试数据生成器"""
    logger.info("\n" + "=" * 60)
    logger.info("测试4: 数据生成器")
    logger.info("=" * 60)
    
    try:
        from newstreamer.utils.generators import (
            RandomWalkPriceGenerator,
            RandomOrderBookGenerator,
            RandomMarketDataGenerator
        )
        
        # 测试价格生成器
        price_gen = RandomWalkPriceGenerator(initial_price=100.0, seed=42)
        prices = [price_gen.next_price() for _ in range(10)]
        assert len(prices) == 10
        assert all(p > 0 for p in prices)
        
        # 测试订单簿生成器
        book_gen = RandomOrderBookGenerator()
        book_data = book_gen.generate('TEST001')
        assert 'bids' in book_data
        assert 'asks' in book_data
        assert len(book_data['bids']) == 5
        
        # 测试市场数据生成器
        market_gen = RandomMarketDataGenerator()
        market_data = market_gen.generate('TEST001')
        assert market_data['symbol'] == 'TEST001'
        assert market_data['price'] > 0
        
        logger.info("✓ 所有生成器工作正常")
        logger.info(f"  - 价格序列: {prices[:3]}...")
        logger.info(f"  - 订单簿档位: {len(book_data['bids'])}档")
        logger.info(f"  - 市场数据价格: {market_data['price']:.2f}")
        
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_models():
    """测试数据模型"""
    logger.info("\n" + "=" * 60)
    logger.info("测试5: 数据模型")
    logger.info("=" * 60)
    
    try:
        from newstreamer.models.orderbook import OrderBook, OrderBookLevel
        from newstreamer.models.market_data import MarketData, BookSnapshotData
        from datetime import datetime
        import time
        
        # 测试OrderBook
        bids = [OrderBookLevel(price=100.0, volume=1000)]
        asks = [OrderBookLevel(price=100.1, volume=1500)]
        book = OrderBook(
            symbol='TEST001',
            timestamp=datetime.now(),
            bids=bids,
            asks=asks
        )
        
        assert book.get_bid(0) == 100.0
        assert book.get_ask(0) == 100.1
        assert book.get_mid_price() == 100.05
        
        # 测试MarketData
        market_data = MarketData(
            symbol='TEST001',
            trade_date='20250101',
            timestamp=int(time.time() * 1e9),
            price=100.0,
            pre_close=99.0
        )
        
        assert market_data.symbol == 'TEST001'
        assert abs(market_data.get_change_pct() - 1.01) < 0.01
        
        # 测试BookSnapshotData
        snapshot = BookSnapshotData(
            symbol='TEST001',
            trade_date='20250101',
            timestamp=int(time.time() * 1e9),
            volume=1000000,
            last=100.0,
            book=book
        )
        
        assert snapshot.get_mid() == 100.05
        assert snapshot.check_last_n_book(1)
        
        logger.info("✓ 所有数据模型工作正常")
        logger.info(f"  - OrderBook中间价: {book.get_mid_price():.2f}")
        logger.info(f"  - MarketData涨跌幅: {market_data.get_change_pct():.2f}%")
        logger.info(f"  - BookSnapshot有效深度: {snapshot.check_last_n_book(1)}")
        
        return True
    except Exception as e:
        logger.error(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    logger.info("\n" + "=" * 60)
    logger.info("NewStreamer 包验证脚本")
    logger.info("=" * 60 + "\n")
    
    results = []
    
    # 运行所有测试
    results.append(("导入测试", test_imports()))
    results.append(("Fake生成器流", test_fake_generator_stream()))
    results.append(("Fake实时流", test_fake_live_stream()))
    results.append(("数据生成器", test_generators()))
    results.append(("数据模型", test_models()))
    
    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("测试汇总")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{name:20s} {status}")
    
    logger.info("=" * 60)
    logger.info(f"总计: {passed}/{total} 通过")
    logger.info("=" * 60)
    
    if passed == total:
        logger.info("\n🎉 所有测试通过！NewStreamer包工作正常。")
        return 0
    else:
        logger.error(f"\n❌ {total - passed} 个测试失败。")
        return 1


if __name__ == '__main__':
    sys.exit(main())

