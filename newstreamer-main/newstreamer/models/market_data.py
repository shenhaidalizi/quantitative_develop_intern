"""
市场数据模型

简化版本的市场数据结构，兼容trader_data但不依赖其他包。
参考: trader_data.streams.historical.market.bookSnapshotData
"""

from typing import Optional
from dataclasses import dataclass
import pandas as pd
from newstreamer.models.orderbook import OrderBook


@dataclass
class MarketData:
    """
    基础市场数据结构
    
    包含股票的基本行情数据
    """
    
    symbol: str                    # 股票代码
    trade_date: str                # 交易日期(YYYYMMDD)
    timestamp: int                 # 时间戳(纳秒)
    price: float                   # 最新价
    volume: int = 0                # 成交量
    amount: float = 0.0            # 成交额
    open: float = 0.0              # 开盘价
    high: float = 0.0              # 最高价
    low: float = 0.0               # 最低价
    close: float = 0.0             # 收盘价
    pre_close: float = 0.0         # 昨收价
    
    # 可选字段
    name: Optional[str] = None             # 股票名称
    chg_pct: Optional[float] = None        # 涨跌幅
    chg_amount: Optional[float] = None     # 涨跌额
    turnover_rate: Optional[float] = None  # 换手率
    
    def get_change_pct(self) -> Optional[float]:
        """
        计算涨跌幅
        
        Returns:
            涨跌幅(百分比)，如果昨收价为0则返回None
        """
        if self.pre_close > 0:
            return ((self.price - self.pre_close) / self.pre_close) * 100
        return None
    
    def get_change_amount(self) -> float:
        """
        计算涨跌额
        
        Returns:
            涨跌额
        """
        return self.price - self.pre_close
    
    def get_amplitude(self) -> Optional[float]:
        """
        计算振幅
        
        Returns:
            振幅(百分比)，如果昨收价为0或高低价无效则返回None
        """
        if self.pre_close > 0 and self.high > 0 and self.low > 0:
            return ((self.high - self.low) / self.pre_close) * 100
        return None
    
    def is_limit_up(self, threshold: float = 9.9) -> bool:
        """判断是否涨停"""
        chg = self.get_change_pct()
        return chg is not None and chg >= threshold
    
    def is_limit_down(self, threshold: float = -9.9) -> bool:
        """判断是否跌停"""
        chg = self.get_change_pct()
        return chg is not None and chg <= threshold
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            'symbol': self.symbol,
            'trade_date': self.trade_date,
            'timestamp': self.timestamp,
            'price': self.price,
            'volume': self.volume,
            'amount': self.amount,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'pre_close': self.pre_close,
            'name': self.name,
            'chg_pct': self.chg_pct or self.get_change_pct(),
            'chg_amount': self.chg_amount or self.get_change_amount(),
            'turnover_rate': self.turnover_rate,
            'amplitude': self.get_amplitude()
        }


@dataclass
class BookSnapshotData:
    """
    订单簿快照数据
    
    简化版本，兼容trader_data.streams.historical.market.bookSnapshotData
    包含完整的订单簿和市场数据
    """
    
    symbol: str
    trade_date: str                # 交易日期
    timestamp: int                 # 时间戳(纳秒)
    volume: int                    # 成交量
    last: float                    # 最新价
    book: OrderBook                # 订单簿
    open: float = 0.0
    close: float = 0.0
    high: float = 0.0
    low: float = 0.0
    
    # 缓存的一档数据(从book提取)
    bid1: Optional[float] = None
    bid_vol1: Optional[float] = None
    ask1: Optional[float] = None
    ask_vol1: Optional[float] = None
    
    def __post_init__(self):
        """初始化后从book提取一档数据"""
        if self.book is not None:
            self.bid1 = self.book.get_bid(0)
            self.bid_vol1 = self.book.get_bid_vol(0)
            self.ask1 = self.book.get_ask(0)
            self.ask_vol1 = self.book.get_ask_vol(0)
    
    def get_mid(self) -> float:
        """获取中间价"""
        if self.book:
            return self.book.get_mid_price()
        return 0.0
    
    def get_book(self) -> OrderBook:
        """获取订单簿"""
        return self.book
    
    def get_weightedtop(self) -> float:
        """获取加权顶部价格"""
        if self.book:
            return self.book.get_weighted_top_price()
        return 0.0
    
    def check_last_n_book(self, n: int = 1) -> bool:
        """检查订单簿深度"""
        if self.book is None:
            return False
        return self.book.check_last_n_book(n)
    
    def get_timestamp(self, unit: str = 'ms') -> int:
        """
        获取时间戳
        
        Args:
            unit: 时间单位 ('s', 'ms', 'us', 'ns')
            
        Returns:
            指定单位的时间戳
        """
        if unit == 's':
            return self.timestamp // 1_000_000_000
        elif unit == 'ms':
            return self.timestamp // 1_000_000
        elif unit == 'us':
            return self.timestamp // 1_000
        elif unit == 'ns':
            return self.timestamp
        else:
            raise ValueError(f"不支持的时间单位: {unit}")
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        result = {
            'symbol': self.symbol,
            'trade_date': self.trade_date,
            'timestamp': self.timestamp,
            'last': self.last,
            'volume': self.volume,
            'open': self.open,
            'close': self.close,
            'high': self.high,
            'low': self.low
        }
        
        # 添加五档数据
        if self.book:
            for i in range(1, 6):
                result[f'bid_price{i}'] = self.book.get_bid(i-1)
                result[f'ask_price{i}'] = self.book.get_ask(i-1)
                result[f'bid_vol{i}'] = self.book.get_bid_vol(i-1)
                result[f'ask_vol{i}'] = self.book.get_ask_vol(i-1)
            
            result['mid'] = self.get_mid()
        
        return result
    
    def __str__(self) -> str:
        """字符串表示"""
        if self.book is None:
            return f"{self.timestamp};{self.symbol};{self.last};{self.volume}"
        else:
            return (f"{self.timestamp};{self.symbol};{self.last};{self.volume};"
                    f"{self.bid1};{self.bid_vol1};{self.ask1};{self.ask_vol1}")
