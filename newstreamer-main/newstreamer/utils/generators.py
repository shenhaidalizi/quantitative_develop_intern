"""随机数据生成器

用于生成模拟的市场数据，支持回测和策略开发。
"""

import numpy as np
import pandas as pd
from typing import List, Optional
import time
from datetime import datetime


class RandomWalkPriceGenerator:
    """
    随机游走价格生成器
    
    使用几何布朗运动(GBM)模型生成价格序列
    """
    
    def __init__(
        self,
        initial_price: float = 100.0,
        drift: float = 0.0001,
        volatility: float = 0.02,
        seed: Optional[int] = None
    ):
        """
        初始化价格生成器
        
        Args:
            initial_price: 初始价格
            drift: 漂移率(均值收益率)
            volatility: 波动率(标准差)
            seed: 随机种子，用于可重复的结果
        """
        self.current_price = initial_price
        self.initial_price = initial_price
        self.drift = drift
        self.volatility = volatility
        
        if seed is not None:
            np.random.seed(seed)
    
    def next_price(self) -> float:
        """
        生成下一个价格点
        
        Returns:
            新的价格
        """
        # 几何布朗运动: dS = μS*dt + σS*dW
        random_shock = np.random.normal(0, 1)
        price_change = (self.drift * self.current_price + 
                       self.volatility * self.current_price * random_shock)
        self.current_price += price_change
        
        # 确保价格为正
        self.current_price = max(self.current_price, 0.01)
        
        return round(self.current_price, 2)
    
    def generate_sequence(self, n: int) -> List[float]:
        """
        生成价格序列
        
        Args:
            n: 序列长度
            
        Returns:
            价格列表
        """
        return [self.next_price() for _ in range(n)]
    
    def reset(self):
        """重置价格到初始值"""
        self.current_price = self.initial_price


class RandomOrderBookGenerator:
    """
    随机订单簿生成器
    
    生成逼真的五档行情数据
    """
    
    def __init__(
        self,
        price_generator: Optional[RandomWalkPriceGenerator] = None,
        spread_bps: float = 10.0,
        depth_levels: int = 5,
        volume_range: tuple = (100, 10000)
    ):
        """
        初始化订单簿生成器
        
        Args:
            price_generator: 价格生成器，如果为None则创建默认生成器
            spread_bps: 买卖价差(基点，1bp = 0.01%)
            depth_levels: 订单簿深度档位
            volume_range: 成交量范围(最小值, 最大值)
        """
        self.price_gen = price_generator or RandomWalkPriceGenerator()
        self.spread_bps = spread_bps
        self.depth_levels = depth_levels
        self.volume_range = volume_range
    
    def generate(self, symbol: str, timestamp: Optional[int] = None) -> dict:
        """
        生成订单簿数据（字典格式，用于构建OrderBook）
        
        Args:
            symbol: 股票代码
            timestamp: 时间戳，如果为None则使用当前时间
            
        Returns:
            订单簿字典，包含bids/asks/timestamp等
        """
        # 获取中间价
        mid_price = self.price_gen.next_price()
        spread = mid_price * (self.spread_bps / 10000)
        
        # 生成买卖价格和成交量
        bids = []
        asks = []
        bid_vols = []
        ask_vols = []
        
        for i in range(self.depth_levels):
            # 买价从高到低
            bid_price = mid_price - spread / 2 - i * spread * 0.5
            bids.append(round(bid_price, 2))
            bid_vols.append(np.random.randint(*self.volume_range))
            
            # 卖价从低到高
            ask_price = mid_price + spread / 2 + i * spread * 0.5
            asks.append(round(ask_price, 2))
            ask_vols.append(np.random.randint(*self.volume_range))
        
        return {
            'symbol': symbol,
            'timestamp': timestamp or datetime.now(),
            'bids': bids,
            'bid_vols': bid_vols,
            'asks': asks,
            'ask_vols': ask_vols
        }


class RandomMarketDataGenerator:
    """
    随机市场数据生成器
    
    生成完整的市场数据，包括OHLCV等字段
    """
    
    def __init__(
        self,
        price_generator: Optional[RandomWalkPriceGenerator] = None,
        volume_range: tuple = (1000000, 50000000),
        amplitude_range: tuple = (0.01, 0.05)
    ):
        """
        初始化市场数据生成器
        
        Args:
            price_generator: 价格生成器
            volume_range: 成交量范围
            amplitude_range: 振幅范围(比例)
        """
        self.price_gen = price_generator or RandomWalkPriceGenerator()
        self.volume_range = volume_range
        self.amplitude_range = amplitude_range
        self._last_close = None
    
    def generate(
        self,
        symbol: str,
        timestamp: Optional[int] = None,
        name: Optional[str] = None
    ) -> dict:
        """
        生成市场数据
        
        Args:
            symbol: 股票代码
            timestamp: 时间戳
            name: 股票名称
            
        Returns:
            市场数据字典
        """
        # 生成基准价格
        current_price = self.price_gen.next_price()
        
        # 生成振幅
        amplitude = np.random.uniform(*self.amplitude_range)
        price_range = current_price * amplitude
        
        # 生成OHLC
        high = current_price + np.random.uniform(0, price_range)
        low = current_price - np.random.uniform(0, price_range)
        open_price = np.random.uniform(low, high)
        close_price = current_price
        
        # 生成成交量和成交额
        volume = np.random.randint(*self.volume_range)
        avg_price = (high + low) / 2
        amount = volume * avg_price
        
        # 计算昨收价
        if self._last_close is None:
            pre_close = current_price * (1 - np.random.uniform(-0.02, 0.02))
        else:
            pre_close = self._last_close
        
        self._last_close = close_price
        
        # 计算涨跌幅和涨跌额
        chg_amount = current_price - pre_close
        chg_pct = (chg_amount / pre_close) * 100 if pre_close > 0 else 0.0
        
        # 计算换手率(假设流通股本)
        turnover_rate = np.random.uniform(0.5, 10.0)
        
        return {
            'symbol': symbol,
            'name': name or f'股票{symbol}',
            'timestamp': timestamp or int(time.time() * 1e9),
            'price': round(current_price, 2),
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close_price, 2),
            'pre_close': round(pre_close, 2),
            'volume': volume,
            'amount': round(amount, 2),
            'chg_pct': round(chg_pct, 2),
            'chg_amount': round(chg_amount, 2),
            'amplitude': round((high - low) / pre_close * 100, 2),
            'turnover_rate': round(turnover_rate, 2),
            'trade_date': pd.Timestamp.now().strftime('%Y%m%d')
        }
    
    def reset(self):
        """重置生成器状态"""
        self.price_gen.reset()
        self._last_close = None
