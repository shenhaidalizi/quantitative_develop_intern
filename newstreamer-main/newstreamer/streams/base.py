"""数据流基类定义"""

from abc import ABC, abstractmethod
from typing import Generator, List, Optional, Callable, Union, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DataStreamBase(ABC):
    """
    数据流基类 - 简单生成器模式
    
    适用场景：
    - 历史数据回放
    - 批量数据处理
    - 回测系统
    
    参考实现: data/src/trader_data/streams/marketDataStream.py
    """
    
    def __init__(self, market_type: str = 'stock'):
        """
        初始化数据流
        
        Args:
            market_type: 市场类型，如'stock', 'futures'等
        """
        self.market_type = market_type
        self._connected = False
    
    @abstractmethod
    def connect(self):
        """建立数据连接"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """断开数据连接"""
        pass
    
    @abstractmethod
    def get_orderbook(self, symbol: str) -> Generator[Any, None, None]:
        """
        获取订单簿数据流
        
        Args:
            symbol: 股票代码
            
        Yields:
            订单簿数据对象
        """
        pass
    
    def shutdown(self):
        """关闭数据流并清理资源"""
        self.disconnect()
        logger.info(f"{self.__class__.__name__} 已关闭")
    
    def _handle_error(self, error: Exception):
        """
        统一的错误处理逻辑
        
        Args:
            error: 异常对象
        """
        logger.error(f"{self.__class__.__name__} 错误: {str(error)}")
        self.disconnect()


class LiveDataStreamBase(ABC):
    """
    实时数据流基类 - 回调模式
    
    适用场景：
    - 实时行情订阅
    - 在线交易系统
    - 实时监控系统
    
    参考实现: data/src/trader_data/streams/realtime/market/guguLiveDataStream.py
    """
    
    def __init__(self):
        """初始化实时数据流"""
        self.callbacks: List[Callable] = []
        self._is_running = False
        self.subscribe_symbols: List[str] = []
    
    @abstractmethod
    def subscribe(self, subscribe_symbols: List[str]):
        """
        订阅股票代码列表
        
        Args:
            subscribe_symbols: 股票代码列表
        """
        pass
    
    @abstractmethod
    def unsubscribe(self):
        """取消所有订阅"""
        pass
    
    def add_callback(self, callback: Callable):
        """
        添加数据回调函数
        
        Args:
            callback: 回调函数，接收数据列表作为参数
        """
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            logger.info(f"已添加回调函数: {callback.__name__}")
    
    def remove_callback(self, callback: Callable):
        """
        移除数据回调函数
        
        Args:
            callback: 要移除的回调函数
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            logger.info(f"已移除回调函数: {callback.__name__}")
    
    @abstractmethod
    def get_latest_data(self) -> Optional[Union[Dict, Any]]:
        """
        获取最新数据
        
        Returns:
            最新的市场数据
        """
        pass
    
    @abstractmethod
    def start_streaming(self, interval: int = 30):
        """
        开始流式传输数据
        
        Args:
            interval: 数据刷新间隔(秒)
        """
        pass
    
    @abstractmethod
    def stop(self):
        """停止数据流"""
        pass
    
    def on_market_data(self, data: Any):
        """
        市场数据回调处理
        
        Args:
            data: 市场数据
        """
        for callback in self.callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"回调函数执行失败: {callback.__name__}, 错误: {str(e)}")
    
    def is_running(self) -> bool:
        """
        检查数据流是否正在运行
        
        Returns:
            如果正在运行返回True
        """
        return self._is_running

