"""测试CSV数据流"""

import pytest
import pandas as pd
from pathlib import Path
from newstreamer.streams.csv_stream import CSVMarketDataStream
from newstreamer.models.orderbook import OrderBook
from newstreamer.models.market_data import MarketData


@pytest.fixture
def sample_orderbook_csv(tmp_path):
    """创建示例订单簿CSV文件"""
    data = {
        'symbol': ['000001'] * 10,
        'timestamp': list(range(1000000000, 1000000000 + 10 * 1000000000, 1000000000)),
        'bid1': [100.0 + i * 0.1 for i in range(10)],
        'bid_vol1': [1000] * 10,
        'ask1': [100.5 + i * 0.1 for i in range(10)],
        'ask_vol1': [1000] * 10,
        'bid2': [99.9 + i * 0.1 for i in range(10)],
        'bid_vol2': [1000] * 10,
        'ask2': [100.6 + i * 0.1 for i in range(10)],
        'ask_vol2': [1000] * 10,
    }
    
    df = pd.DataFrame(data)
    csv_path = tmp_path / "orderbook.csv"
    df.to_csv(csv_path, index=False)
    
    return csv_path


@pytest.fixture
def sample_market_csv(tmp_path):
    """创建示例市场数据CSV文件"""
    data = {
        'symbol': ['000001'] * 10,
        'timestamp': list(range(1000000000, 1000000000 + 10 * 1000000000, 1000000000)),
        'trade_date': ['20250101'] * 10,
        'price': [100.0 + i for i in range(10)],
        'open': [99.0 + i for i in range(10)],
        'high': [101.0 + i for i in range(10)],
        'low': [98.0 + i for i in range(10)],
        'close': [100.0 + i for i in range(10)],
        'pre_close': [99.5 + i for i in range(10)],
        'volume': [1000000] * 10,
        'amount': [100000000.0] * 10,
    }
    
    df = pd.DataFrame(data)
    csv_path = tmp_path / "market.csv"
    df.to_csv(csv_path, index=False)
    
    return csv_path


class TestCSVMarketDataStream:
    """测试CSVMarketDataStream"""
    
    def test_init(self, sample_orderbook_csv):
        """测试初始化"""
        stream = CSVMarketDataStream(
            csv_path=str(sample_orderbook_csv),
            data_type='orderbook'
        )
        
        assert stream.csv_path == Path(sample_orderbook_csv)
        assert stream.data_type == 'orderbook'
        assert not stream._connected
    
    def test_connect(self, sample_orderbook_csv):
        """测试连接"""
        stream = CSVMarketDataStream(
            csv_path=str(sample_orderbook_csv),
            data_type='orderbook'
        )
        
        stream.connect()
        
        assert stream._connected
        assert stream.data_df is not None
        assert len(stream.data_df) == 10
        
        stream.shutdown()
    
    def test_get_orderbook(self, sample_orderbook_csv):
        """测试获取订单簿数据"""
        stream = CSVMarketDataStream(
            csv_path=str(sample_orderbook_csv),
            data_type='orderbook'
        )
        
        stream.connect()
        
        orderbooks = list(stream.get_orderbook('000001'))
        
        assert len(orderbooks) == 10
        
        for book in orderbooks:
            assert isinstance(book, OrderBook)
            assert book.symbol == '000001'
        
        stream.shutdown()
    
    def test_get_market_data(self, sample_market_csv):
        """测试获取市场数据"""
        stream = CSVMarketDataStream(
            csv_path=str(sample_market_csv),
            data_type='market'
        )
        
        stream.connect()
        
        market_data_list = list(stream.get_market_data('000001'))
        
        assert len(market_data_list) == 10
        
        for data in market_data_list:
            assert isinstance(data, MarketData)
            assert data.symbol == '000001'
            assert data.price > 0
        
        stream.shutdown()
    
    def test_get_symbols(self, sample_orderbook_csv):
        """测试获取股票列表"""
        stream = CSVMarketDataStream(
            csv_path=str(sample_orderbook_csv),
            data_type='orderbook'
        )
        
        stream.connect()
        
        symbols = stream.get_symbols()
        assert '000001' in symbols
        
        stream.shutdown()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
