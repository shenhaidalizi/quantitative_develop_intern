"""CSV数据流实现

从CSV文件读取历史数据，支持回测和数据分析。
"""

from typing import Generator, Optional, Dict, Any
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from newstreamer.streams.base import DataStreamBase
from newstreamer.models.orderbook import OrderBook, OrderBookLevel
from newstreamer.models.market_data import MarketData, BookSnapshotData

logger = logging.getLogger(__name__)


class CSVMarketDataStream(DataStreamBase):
    """
    CSV市场数据流
    
    从CSV文件读取历史市场数据，支持：
    - 订单簿数据
    - OHLCV数据
    - 自定义字段映射
    
    CSV格式要求：
    1. 订单簿格式: symbol, timestamp, bid1, bid_vol1, ask1, ask_vol1, ...
    2. 市场数据格式: symbol, timestamp, price, open, high, low, close, volume, ...
    
    示例:
        >>> stream = CSVMarketDataStream('data/orderbook.csv', data_type='orderbook')
        >>> stream.connect()
        >>> for book in stream.get_orderbook('000001'):
        ...     print(book.get_mid_price())
        >>> stream.shutdown()
    """
    
    def __init__(
        self,
        csv_path: str,
        data_type: str = 'orderbook',
        symbol_column: str = 'symbol',
        timestamp_column: str = 'timestamp',
        encoding: str = 'utf-8'
    ):
        """
        初始化CSV数据流
        
        Args:
            csv_path: CSV文件路径
            data_type: 数据类型，'orderbook'或'market'
            symbol_column: 股票代码列名
            timestamp_column: 时间戳列名
            encoding: 文件编码
        """
        super().__init__(market_type='stock')
        self.csv_path = Path(csv_path)
        self.data_type = data_type
        self.symbol_column = symbol_column
        self.timestamp_column = timestamp_column
        self.encoding = encoding
        self.data_df: Optional[pd.DataFrame] = None
    
    def connect(self):
        """加载CSV文件"""
        try:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"CSV文件不存在: {self.csv_path}")
            
            self.data_df = pd.read_csv(
                self.csv_path,
                encoding=self.encoding
            )
            
            # 验证必要列
            required_columns = [self.symbol_column, self.timestamp_column]
            missing_columns = [col for col in required_columns 
                             if col not in self.data_df.columns]
            
            if missing_columns:
                raise ValueError(f"CSV文件缺少必要列: {missing_columns}")
            
            self._connected = True
            logger.info(f"CSV数据流已加载: {self.csv_path}, 共 {len(self.data_df)} 条记录")
            
        except Exception as e:
            self._handle_error(e)
            raise
    
    def disconnect(self):
        """断开连接(释放数据)"""
        self.data_df = None
        self._connected = False
        logger.info("CSV数据流已断开")
    
    def get_orderbook(self, symbol: str) -> Generator[OrderBook, None, None]:
        """
        获取订单簿数据流
        
        Args:
            symbol: 股票代码
            
        Yields:
            OrderBook对象
            
        Raises:
            ConnectionError: 如果未连接
            ValueError: 如果数据类型不是orderbook
        """
        if not self._connected or self.data_df is None:
            raise ConnectionError("数据流未连接，请先调用connect()")
        
        if self.data_type != 'orderbook':
            raise ValueError(f"数据类型错误: {self.data_type}，期望: orderbook")
        
        # 筛选指定股票的数据
        symbol_data = self.data_df[
            self.data_df[self.symbol_column] == symbol
        ]
        
        if symbol_data.empty:
            logger.warning(f"未找到股票 {symbol} 的数据")
            return
        
        logger.info(f"开始读取 {symbol} 的订单簿数据，共 {len(symbol_data)} 条")
        
        try:
            for _, row in symbol_data.iterrows():
                # 提取五档数据
                bids = []
                bid_vols = []
                asks = []
                ask_vols = []
                
                for i in range(1, 6):  # 5档
                    # 买价买量
                    bid_key = f'bid{i}'
                    bid_vol_key = f'bid_vol{i}'
                    if bid_key in row and bid_vol_key in row:
                        bids.append(float(row[bid_key]))
                        bid_vols.append(int(row[bid_vol_key]))
                    
                    # 卖价卖量
                    ask_key = f'ask{i}'
                    ask_vol_key = f'ask_vol{i}'
                    if ask_key in row and ask_vol_key in row:
                        asks.append(float(row[ask_key]))
                        ask_vols.append(int(row[ask_vol_key]))
                
                # 创建订单簿对象
                bid_levels = [OrderBookLevel(price=p, volume=v) 
                             for p, v in zip(bids, bid_vols)]
                ask_levels = [OrderBookLevel(price=p, volume=v) 
                             for p, v in zip(asks, ask_vols)]
                
                orderbook = OrderBook(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(int(row[self.timestamp_column]) / 1e9),
                    bids=bid_levels,
                    asks=ask_levels
                )
                
                yield orderbook
                
        except Exception as e:
            self._handle_error(e)
            raise
    
    def get_market_data(self, symbol: str) -> Generator[MarketData, None, None]:
        """
        获取市场数据流
        
        Args:
            symbol: 股票代码
            
        Yields:
            MarketData对象
            
        Raises:
            ConnectionError: 如果未连接
            ValueError: 如果数据类型不是market
        """
        if not self._connected or self.data_df is None:
            raise ConnectionError("数据流未连接，请先调用connect()")
        
        if self.data_type != 'market':
            raise ValueError(f"数据类型错误: {self.data_type}，期望: market")
        
        # 筛选指定股票的数据
        symbol_data = self.data_df[
            self.data_df[self.symbol_column] == symbol
        ]
        
        if symbol_data.empty:
            logger.warning(f"未找到股票 {symbol} 的数据")
            return
        
        logger.info(f"开始读取 {symbol} 的市场数据，共 {len(symbol_data)} 条")
        
        try:
            for _, row in symbol_data.iterrows():
                # 构建市场数据
                market_data = MarketData(
                    symbol=symbol,
                    trade_date=row.get('trade_date', ''),
                    timestamp=int(row[self.timestamp_column]),
                    price=float(row.get('price', 0)),
                    volume=int(row.get('volume', 0)),
                    amount=float(row.get('amount', 0)),
                    open=float(row.get('open', 0)),
                    high=float(row.get('high', 0)),
                    low=float(row.get('low', 0)),
                    close=float(row.get('close', 0)),
                    pre_close=float(row.get('pre_close', 0)),
                    name=row.get('name'),
                    chg_pct=float(row['chg_pct']) if 'chg_pct' in row else None,
                    chg_amount=float(row['chg_amount']) if 'chg_amount' in row else None,
                    turnover_rate=float(row['turnover_rate']) if 'turnover_rate' in row else None
                )
                
                yield market_data
                
        except Exception as e:
            self._handle_error(e)
            raise
    
    def get_symbols(self) -> list:
        """
        获取CSV中所有的股票代码
        
        Returns:
            股票代码列表
        """
        if not self._connected or self.data_df is None:
            raise ConnectionError("数据流未连接，请先调用connect()")
        
        return self.data_df[self.symbol_column].unique().tolist()
    
    def get_date_range(self) -> tuple:
        """
        获取数据的时间范围
        
        Returns:
            (最早时间戳, 最晚时间戳)
        """
        if not self._connected or self.data_df is None:
            raise ConnectionError("数据流未连接，请先调用connect()")
        
        min_ts = self.data_df[self.timestamp_column].min()
        max_ts = self.data_df[self.timestamp_column].max()
        return (min_ts, max_ts)


class CSVLiveDataStream(CSVMarketDataStream):
    """
    CSV实时数据流(模拟)
    
    从CSV读取数据但按照实时数据流的方式提供，支持回调模式。
    适用于回测场景下的实时数据模拟。
    """
    
    def __init__(
        self,
        csv_path: str,
        data_type: str = 'market',
        playback_speed: float = 1.0,
        **kwargs
    ):
        """
        初始化CSV实时数据流
        
        Args:
            csv_path: CSV文件路径
            data_type: 数据类型
            playback_speed: 回放速度倍数(1.0为正常速度)
            **kwargs: 其他参数传递给父类
        """
        super().__init__(csv_path, data_type, **kwargs)
        self.playback_speed = playback_speed
        self.callbacks = []
    
    def add_callback(self, callback):
        """添加回调函数"""
        self.callbacks.append(callback)
    
    def replay(self, symbol: str):
        """
        回放指定股票的数据
        
        Args:
            symbol: 股票代码
        """
        import time
        
        if self.data_type == 'orderbook':
            for orderbook in self.get_orderbook(symbol):
                # 触发回调
                for callback in self.callbacks:
                    callback(orderbook)
                
                # 模拟时间延迟
                if self.playback_speed > 0:
                    time.sleep(1.0 / self.playback_speed)
        
        elif self.data_type == 'market':
            for market_data in self.get_market_data(symbol):
                # 触发回调
                for callback in self.callbacks:
                    callback(market_data)
                
                # 模拟时间延迟
                if self.playback_speed > 0:
                    time.sleep(1.0 / self.playback_speed)

