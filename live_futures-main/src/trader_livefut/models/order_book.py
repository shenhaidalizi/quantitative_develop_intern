from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import numpy as np
from datetime import datetime

@dataclass
class OrderBookLevel:
    """订单簿单个价位"""
    price: float
    volume: float
    count: Optional[int] = None  # 订单数量(可选)

@dataclass
class OrderBook:
    """订单簿结构"""
    asks: List[OrderBookLevel]  # 卖单(升序排列)
    bids: List[OrderBookLevel]  # 买单(降序排列)
    timestamp: datetime         # 订单簿时间戳
    
    def get_bid(self, index: int) -> float:
        """获取指定层级的买价"""
        if 0 <= index < len(self.bids):
            return self.bids[index].price
        return 0.0
    
    def get_ask(self, index: int) -> float:
        """获取指定层级的卖价"""
        if 0 <= index < len(self.asks):
            return self.asks[index].price
        return 0.0
    
    def get_bid_vol(self, index: int) -> float:
        """获取指定层级的买量"""
        if 0 <= index < len(self.bids):
            return self.bids[index].volume
        return 0.0
    
    def get_ask_vol(self, index: int) -> float:
        """获取指定层级的卖量"""
        if 0 <= index < len(self.asks):
            return self.asks[index].volume
        return 0.0
    
    def check_last_n_book(self, n: int = 5) -> bool:
        """检查前n层订单簿是否完整"""
        return len(self.bids) >= n and len(self.asks) >= n
    
    def get_weighted_top_price(self) -> float:
        """获取加权顶部价格（通常是基于最优买卖价和量的加权平均）"""
        if not self.bids or not self.asks:
            return 0.0
        
        bid_price = self.bids[0].price
        bid_vol = self.bids[0].volume
        ask_price = self.asks[0].price
        ask_vol = self.asks[0].volume
        
        total_vol = bid_vol + ask_vol
        if total_vol <= 0:
            return (bid_price + ask_price) / 2
        
        return (bid_price * ask_vol + ask_price * bid_vol) / total_vol