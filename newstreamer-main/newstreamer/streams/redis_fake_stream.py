import redis
import time
from typing import List, Dict, Any, Optional, Generator
from newstreamer.models.orderbook import OrderBook, OrderBookLevel
from newstreamer.models.market_data import MarketData
from newstreamer.utils.generators import (
    RandomOrderBookGenerator,
    RandomMarketDataGenerator,
    RandomWalkPriceGenerator
)
from newstreamer.streams.base import DataStreamBase, LiveDataStreamBase
from newstreamer.streams.to_redis import RedisClient

# 设置日志
import logging
logger = logging.getLogger(__name__)

class FakeMarketDataStream(DataStreamBase):
    """
    模拟市场数据流 - 生成器模式
    
    使用随机数据生成器产生订单簿数据，适用于：
    - 开发调试
    - 单元测试
    - 回测系统
    """
    
    def __init__(self, symbols: List[str], initial_price: float = 100.0, volatility: float = 0.02, 
                 max_ticks: int = 100, tick_interval: float = 1.0, seed: Optional[int] = None):
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
       
        # 初始化 Redis 客户端
        try:
            self.redis_client = RedisClient(host='localhost', port=6379, db=0)
            logger.info(f"Redis连接成功，连接到 'localhost':{6379}")
        except redis.ConnectionError as e:
            logger.error(f"无法连接到 Redis: {e}")
            raise

    
    def connect(self):
        """建立连接(模拟)"""
        self._connected = True
        logger.info(f"FakeMarketDataStream 已连接，共 {len(self.symbols)} 个股票")
    
    def disconnect(self):
        """断开连接(模拟)"""
        self._connected = False
        logger.info("FakeMarketDataStream 已断开")
    
    def get_orderbook(self, symbol: str) -> Generator[OrderBook, None, None]:
        """获取订单簿数据流"""
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

                # 将订单簿数据写入 Redis
                try:
                    payload = orderbook.to_dict()
                    self.redis_client.write_data(symbol, payload)
                    logger.info(f"数据已写入 Redis：{symbol} -> {payload}")
                except Exception as e:
                    logger.error(f"写入 Redis 失败: {str(e)}")
                    raise

                # 将 OrderBook 数据 yield 给调用方
                yield orderbook
                
                tick_count += 1
                if self.tick_interval > 0:
                    time.sleep(self.tick_interval)
        except Exception as e:
            self._handle_error(e)
            raise


class FakeLiveDataStream(LiveDataStreamBase):
    """
    模拟实时数据流 - 回调模式
    
    使用随机数据生成器产生市场数据，支持订阅和回调机制。
    """
    
    def __init__(self, initial_price: float = 100.0, volatility: float = 0.02, 
                 return_type: str = 'dict', seed: Optional[int] = None):
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

        # 初始化 Redis 客户端
        try:
            self.redis_client = RedisClient(host='localhost', port=6379, db=0)
            logger.info(f"Redis连接成功，连接到 'localhost':{6379}")
        except redis.ConnectionError as e:
            logger.error(f"无法连接到 Redis: {e}")
            raise


    def subscribe(self, subscribe_symbols: List[str]):
        """订阅股票代码列表"""
        self.subscribe_symbols = subscribe_symbols
        
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
        """获取最新数据"""
        return self.latest_data.copy() if self.latest_data else None

    def start_streaming(self, interval: int = 30):
        """开始流式传输数据"""
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

                    # 写入 Redis (以股票代码为 key)
                    try:
                        self.redis_client.write_data(symbol, data)  # 保存市场数据到 Redis
                        logger.info(f"数据已写入 Redis：{symbol} -> {data}")
                    except Exception as e:
                        logger.error(f"写入 Redis 失败: {str(e)}")
                        raise

                # 触发回调
                self.on_market_data(data_list)
                logger.debug(f"已生成 {len(data_list)} 条市场数据")
                
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
 