"""测试模拟数据流"""

import pytest
import time
from newstreamer.streams.fake_stream import FakeMarketDataStream, FakeLiveDataStream
from newstreamer.models.orderbook import OrderBook
from newstreamer.models.market_data import MarketData


class TestFakeMarketDataStream:
    """测试FakeMarketDataStream"""
    
    def test_init(self):
        """测试初始化"""
        stream = FakeMarketDataStream(
            symbols=['000001', '600000'],
            initial_price=100.0,
            max_ticks=10
        )
        
        assert stream.symbols == ['000001', '600000']
        assert stream.max_ticks == 10
        assert len(stream.generators) == 2
    
    def test_connect_disconnect(self):
        """测试连接和断开"""
        stream = FakeMarketDataStream(symbols=['000001'])
        
        assert not stream._connected
        
        stream.connect()
        assert stream._connected
        
        stream.disconnect()
        assert not stream._connected
    
    def test_get_orderbook(self):
        """测试获取订单簿数据"""
        stream = FakeMarketDataStream(
            symbols=['000001'],
            max_ticks=5,
            tick_interval=0.0,
            seed=42
        )
        
        stream.connect()
        
        orderbooks = list(stream.get_orderbook('000001'))
        
        assert len(orderbooks) == 5
        
        for book in orderbooks:
            assert isinstance(book, OrderBook)
            assert book.symbol == '000001'
            assert book.check_last_n_book(5)
            assert book.get_mid_price() >= 0
        
        stream.shutdown()
    
    def test_get_orderbook_not_connected(self):
        """测试未连接时获取数据"""
        stream = FakeMarketDataStream(symbols=['000001'])
        
        with pytest.raises(ConnectionError):
            list(stream.get_orderbook('000001'))
    
    def test_get_orderbook_invalid_symbol(self):
        """测试无效股票代码"""
        stream = FakeMarketDataStream(symbols=['000001'])
        stream.connect()
        
        with pytest.raises(ValueError):
            list(stream.get_orderbook('999999'))
        
        stream.shutdown()
    
    def test_reproducible_with_seed(self):
        """测试使用相同种子生成相同数据"""
        stream1 = FakeMarketDataStream(
            symbols=['000001'],
            max_ticks=5,
            tick_interval=0.0,
            seed=42
        )
        stream1.connect()
        books1 = list(stream1.get_orderbook('000001'))
        stream1.shutdown()
        
        stream2 = FakeMarketDataStream(
            symbols=['000001'],
            max_ticks=5,
            tick_interval=0.0,
            seed=42
        )
        stream2.connect()
        books2 = list(stream2.get_orderbook('000001'))
        stream2.shutdown()
        
        # 比较第一个订单簿
        assert books1[0].get_bid(0) == books2[0].get_bid(0)
        assert books1[0].get_ask(0) == books2[0].get_ask(0)


class TestFakeLiveDataStream:
    """测试FakeLiveDataStream"""
    
    def test_init(self):
        """测试初始化"""
        stream = FakeLiveDataStream(
            initial_price=100.0,
            volatility=0.02,
            return_type='dict'
        )
        
        assert stream.return_type == 'dict'
        assert stream.callbacks == []
        assert not stream._is_running
    
    def test_subscribe_unsubscribe(self):
        """测试订阅和取消订阅"""
        stream = FakeLiveDataStream()
        
        stream.subscribe(['000001', '600000'])
        assert stream.subscribe_symbols == ['000001', '600000']
        assert len(stream.generators) == 2
        
        stream.unsubscribe()
        assert stream.subscribe_symbols == []
        assert len(stream.generators) == 0
    
    def test_add_remove_callback(self):
        """测试添加和移除回调"""
        stream = FakeLiveDataStream()
        
        def callback(data):
            pass
        
        stream.add_callback(callback)
        assert callback in stream.callbacks
        
        stream.remove_callback(callback)
        assert callback not in stream.callbacks
    
    def test_start_streaming_dict_mode(self):
        """测试流式传输(字典模式)"""
        stream = FakeLiveDataStream(
            return_type='dict',
            seed=42
        )
        
        received_data = []
        
        def callback(data_list):
            received_data.extend(data_list)
            if len(received_data) >= 2:
                stream.stop()
        
        stream.subscribe(['000001'])
        stream.add_callback(callback)
        
        # 在单独线程中运行
        import threading
        thread = threading.Thread(
            target=lambda: stream.start_streaming(interval=0.1),
            daemon=True
        )
        thread.start()
        thread.join(timeout=2)
        
        assert len(received_data) >= 1
        
        # 验证数据格式
        for data in received_data:
            assert isinstance(data, dict)
            assert 'symbol' in data
            assert 'price' in data
            assert 'volume' in data
    
    def test_start_streaming_object_mode(self):
        """测试流式传输(对象模式)"""
        stream = FakeLiveDataStream(
            return_type='object',
            seed=42
        )
        
        received_data = []
        
        def callback(data_list):
            received_data.extend(data_list)
            if len(received_data) >= 2:
                stream.stop()
        
        stream.subscribe(['000001'])
        stream.add_callback(callback)
        
        import threading
        thread = threading.Thread(
            target=lambda: stream.start_streaming(interval=0.1),
            daemon=True
        )
        thread.start()
        thread.join(timeout=2)
        
        assert len(received_data) >= 1
        
        # 验证数据格式
        for data in received_data:
            assert isinstance(data, MarketData)
            assert data.symbol == '000001'
            assert data.price > 0
    
    def test_get_latest_data(self):
        """测试获取最新数据"""
        stream = FakeLiveDataStream(seed=42)
        
        stream.subscribe(['000001', '600000'])
        
        # 模拟生成一些数据
        for symbol in stream.subscribe_symbols:
            generator = stream.generators[symbol]
            data = generator.generate(symbol)
            stream.latest_data[symbol] = data
        
        latest = stream.get_latest_data()
        
        assert latest is not None
        assert '000001' in latest
        assert '600000' in latest
    
    def test_stop(self):
        """测试停止数据流"""
        stream = FakeLiveDataStream()
        stream.subscribe(['000001'])
        
        stream._is_running = True
        assert stream.is_running()
        
        stream.stop()
        assert not stream.is_running()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

