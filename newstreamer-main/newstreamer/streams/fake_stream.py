"""模拟数据流实现

提供fake数据用于开发、测试和回测。
"""

from typing import Generator, List, Optional, Dict, Any
import time
import logging
from datetime import datetime
from newstreamer.streams.base import DataStreamBase, LiveDataStreamBase
from newstreamer.models.orderbook import OrderBook, OrderBookLevel
from newstreamer.models.market_data import MarketData, BookSnapshotData
from newstreamer.utils.generators import (
    RandomOrderBookGenerator,
    RandomMarketDataGenerator,
    RandomWalkPriceGenerator
)

logger = logging.getLogger(__name__)


class FakeMarketDataStream(DataStreamBase):
    """
    模拟市场数据流 - 生成器模式
    
    使用随机数据生成器产生订单簿数据，适用于：
    - 开发调试
    - 单元测试
    - 回测系统
    
    示例:
        >>> stream = FakeMarketDataStream(symbols=['000001', '600000'])
        >>> stream.connect()
        >>> for orderbook in stream.get_orderbook('000001'):
        ...     print(orderbook.get_mid_price())
        >>> stream.shutdown()
    """
    
    def __init__(
        self,
        symbols: List[str],
        initial_price: float = 100.0,
        volatility: float = 0.02,
        max_ticks: int = 100,
        tick_interval: float = 1.0,
        seed: Optional[int] = None
    ):
        """
        初始化模拟数据流
        
        Args:
            symbols: 股票代码列表
            initial_price: 初始价格
            volatility: 波动率
            max_ticks: 最大tick数量(None表示无限)
            tick_interval: tick间隔(秒)
            seed: 随机种子
        """
        super().__init__(market_type='stock')
        self.symbols = symbols
        self.max_ticks = max_ticks
        self.tick_interval = tick_interval
        
        # 为每个股票创建独立的生成器
        self.generators = {}
        for symbol in symbols:
            price_gen = RandomWalkPriceGenerator(
                initial_price=initial_price,
                volatility=volatility,
                seed=seed
            )
            self.generators[symbol] = RandomOrderBookGenerator(price_gen)
    
    def connect(self):
        """建立连接(模拟)"""
        self._connected = True
        logger.info(f"FakeMarketDataStream 已连接，共 {len(self.symbols)} 个股票")
    
    def disconnect(self):
        """断开连接(模拟)"""
        self._connected = False
        logger.info("FakeMarketDataStream 已断开")
    
    def get_orderbook(self, symbol: str) -> Generator[OrderBook, None, None]:
        """
        获取订单簿数据流
        
        Args:
            symbol: 股票代码
            
        Yields:
            OrderBook对象
            
        Raises:
            ConnectionError: 如果未连接
            ValueError: 如果股票代码不在订阅列表中
        """
        if not self._connected:
            raise ConnectionError("数据流未连接，请先调用connect()")
        
        if symbol not in self.symbols:
            raise ValueError(f"股票代码 {symbol} 不在订阅列表中")
        
        generator = self.generators[symbol]
        tick_count = 0
        
        try:
            while True:
                # 检查是否达到最大tick数
                if self.max_ticks is not None and tick_count >= self.max_ticks:
                    logger.info(f"{symbol} 数据流已完成，共 {tick_count} 个tick")
                    break
                
                # 生成订单簿数据
                data = generator.generate(symbol)
                
                # 创建OrderBook对象(使用OrderBookLevel)
                bids = [OrderBookLevel(price=p, volume=v) 
                       for p, v in zip(data['bids'], data['bid_vols'])]
                asks = [OrderBookLevel(price=p, volume=v) 
                       for p, v in zip(data['asks'], data['ask_vols'])]
                
                orderbook = OrderBook(
                    symbol=data['symbol'],
                    timestamp=data['timestamp'],
                    bids=bids,
                    asks=asks
                )
                
                yield orderbook
                
                tick_count += 1
                
                # 等待下一个tick
                if self.tick_interval > 0:
                    time.sleep(self.tick_interval)
                    
        except Exception as e:
            self._handle_error(e)
            raise


class FakeLiveDataStream(LiveDataStreamBase):
    """
    模拟实时数据流 - 回调模式
    
    使用随机数据生成器产生市场数据，支持订阅和回调机制。
    
    示例:
        >>> def on_data(data_list):
        ...     for data in data_list:
        ...         print(f"{data['symbol']}: {data['price']}")
        >>> 
        >>> stream = FakeLiveDataStream()
        >>> stream.subscribe(['000001', '600000'])
        >>> stream.add_callback(on_data)
        >>> stream.start_streaming(interval=5)
    """
    
    def __init__(
        self,
        initial_price: float = 100.0,
        volatility: float = 0.02,
        return_type: str = 'dict',
        seed: Optional[int] = None
    ):
        """
        初始化模拟实时数据流
        
        Args:
            initial_price: 初始价格
            volatility: 波动率
            return_type: 返回类型，'dict'或'object'
            seed: 随机种子
        """
        super().__init__()
        self.initial_price = initial_price
        self.volatility = volatility
        self.return_type = return_type
        self.seed = seed
        self.generators = {}
        self.latest_data = {}
    
    def subscribe(self, subscribe_symbols: List[str]):
        """
        订阅股票代码列表
        
        Args:
            subscribe_symbols: 股票代码列表
        """
        self.subscribe_symbols = subscribe_symbols
        
        # 为每个股票创建生成器
        for symbol in subscribe_symbols:
            price_gen = RandomWalkPriceGenerator(
                initial_price=self.initial_price,
                volatility=self.volatility,
                seed=self.seed
            )
            self.generators[symbol] = RandomMarketDataGenerator(price_gen)
        
        logger.info(f"已订阅 {len(subscribe_symbols)} 只股票: {subscribe_symbols}")
    
    def unsubscribe(self):
        """取消所有订阅"""
        self.subscribe_symbols = []
        self.generators = {}
        self.latest_data = {}
        logger.info("已取消所有订阅")
    
    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """
        获取最新数据
        
        Returns:
            以股票代码为键的最新数据字典
        """
        return self.latest_data.copy() if self.latest_data else None
    
    def start_streaming(self, interval: int = 30):
        """
        开始流式传输数据
        
        Args:
            interval: 数据刷新间隔(秒)
        """
        if not self.subscribe_symbols:
            logger.warning("未订阅任何股票，无法启动数据流")
            return
        
        self._is_running = True
        logger.info(f"开始模拟数据流，刷新间隔: {interval}秒")
        
        try:
            while self._is_running:
                # 生成所有订阅股票的数据
                data_list = []
                for symbol in self.subscribe_symbols:
                    generator = self.generators[symbol]
                    data = generator.generate(symbol)
                    
                    # 更新最新数据
                    self.latest_data[symbol] = data
                    
                    # 根据返回类型转换
                    if self.return_type == 'object':
                        data_obj = MarketData(**data)
                        data_list.append(data_obj)
                    else:
                        data_list.append(data)
                
                # 触发回调
                self.on_market_data(data_list)
                logger.debug(f"已生成 {len(data_list)} 条市场数据")
                
                # 等待下一次更新
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("收到中断信号，停止数据流")
            self.stop()
        except Exception as e:
            logger.error(f"数据流出错: {str(e)}")
            self.stop()
            raise
    
    def stop(self):
        """停止数据流"""
        self._is_running = False
        logger.info("模拟数据流已停止")

if __name__ == "__main__":
    stream = FakeMarketDataStream(symbols=['000001', '600000'])
    stream.connect()
    for orderbook in stream.get_orderbook('000001'):
        print(orderbook)
    stream.shutdown()
    def on_data(data_list):
        for data in data_list:
            print(f"{data['symbol']}: {data['price']}")
    stream = FakeLiveDataStream()
    stream.subscribe(['000001', '600000'])
    stream.add_callback(on_data)
    stream.start_streaming(interval=5)