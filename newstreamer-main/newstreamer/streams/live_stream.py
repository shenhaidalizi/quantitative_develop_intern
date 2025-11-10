import time
import threading
import logging
import requests
from typing import Callable, List, Dict, Any, Optional
from abc import ABC, abstractmethod
from newstreamer.streams.base import LiveDataStreamBase


# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LiveDataStream(LiveDataStreamBase):
    """
    实时数据流 - 从URL获取市场数据
    
    通过定期从一个API获取最新数据，并通过回调通知订阅者。
    """

    def __init__(self, base_url: str):
        """
        初始化实时数据流
        
        Args:
            base_url: 数据源URL的基础部分，例如 "http://dataapi.trader.com/live/cn/"
        """
        super().__init__()
        self.base_url = base_url
        self._stream_thread: Optional[threading.Thread] = None
        self._interval = 30  # 默认30秒刷新一次数据

    def subscribe(self, subscribe_symbols: List[str]):
        """
        订阅市场数据
        
        Args:
            subscribe_symbols: 股票代码列表
        """
        self.subscribe_symbols = subscribe_symbols
        logger.info(f"已订阅股票: {', '.join(subscribe_symbols)}")

    def unsubscribe(self):
        """取消所有订阅"""
        self.subscribe_symbols = []
        logger.info("已取消所有订阅")

    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """
        获取最新市场数据
        
        从API获取市场数据
        
        Returns:
            市场数据字典，包含订阅的股票及其价格和成交量
        """
        if not self.subscribe_symbols:
            return None
        
        # 如果订阅的是所有股票，调用 "all" 接口
        if self.subscribe_symbols == ["all"]:
            return self._get_all_data()
        
        # 否则为每个股票调用单支股票数据接口
        data = {}
        for symbol in self.subscribe_symbols:
            data[symbol] = self._get_single_stock_data(symbol)
        
        return data

    def _get_all_data(self) -> Optional[Dict[str, Any]]:
        """从API获取所有股票数据"""
        try:
            response = requests.get(f"{self.base_url}all")
            response.raise_for_status()  # 检查响应状态
            data = response.json()  # 假设返回JSON数据
            logger.info(f"获取所有股票数据: {data}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"获取所有数据时发生错误: {str(e)}")
            return None

    def _get_single_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取单支股票数据"""
        try:
            response = requests.get(f"{self.base_url}{symbol}")
            response.raise_for_status()  # 检查响应状态
            data = response.json()  # 假设返回JSON数据
            logger.info(f"获取股票 {symbol} 数据: {data}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"获取股票 {symbol} 数据时发生错误: {str(e)}")
            return None

    def start_streaming(self, interval: int = 30):
        """
        启动数据流
        
        Args:
            interval: 数据刷新间隔（秒）
        """
        self._interval = interval
        if self._is_running:
            logger.warning("数据流已经在运行中。")
            return
        
        # 启动流式传输的后台线程
        self._is_running = True
        self._stream_thread = threading.Thread(target=self._stream_data)
        self._stream_thread.start()
        logger.info(f"数据流已启动，间隔：{interval}秒")

    def stop(self):
        """停止数据流"""
        if self._is_running:
            self._is_running = False
            if self._stream_thread:
                self._stream_thread.join()
            logger.info("数据流已停止")
        else:
            logger.warning("数据流未在运行中")

    def _stream_data(self):
        """模拟实时数据流"""
        while self._is_running:
            data = self.get_latest_data()
            if data:
                self.on_market_data(data)
            time.sleep(self._interval)
        
    def on_market_data(self, data: Any):
        """
        实时数据回调处理
        
        向所有已注册的回调函数传递最新的数据
        
        Args:
            data: 最新的市场数据
        """
        super().on_market_data(data)

# 示例回调函数
def print_data(data):
    print("接收到市场数据：", data)

# 创建一个数据流实例
data_stream = LiveDataStream(base_url="http://dataapi.trader.com/live/cn/")

# 添加回调函数
data_stream.add_callback(print_data)

# 订阅某些股票
# data_stream.subscribe(["all"])  # 可以替换成 ["all"] 来获取所有股票数据
data_stream.subscribe(['000001'])

# 启动数据流，每30秒获取一次数据
data_stream.start_streaming(interval=30)

# 等待一段时间后停止数据流
time.sleep(120)  # 运行2分钟
data_stream.stop()
