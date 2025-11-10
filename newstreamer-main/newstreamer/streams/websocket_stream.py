"""WebSocket数据流实现

通过WebSocket协议接收实时市场数据。
"""

from typing import List, Optional, Dict, Any, Callable
import json
import logging
import threading
import time
from newstreamer.streams.base import LiveDataStreamBase

logger = logging.getLogger(__name__)


class WebSocketDataStream(LiveDataStreamBase):
    """
    WebSocket市场数据流
    
    通过WebSocket连接接收实时市场数据。
    支持：
    - 自动重连
    - 心跳保活
    - 消息队列
    - 错误处理
    
    示例:
        >>> def on_data(data):
        ...     print(f"收到数据: {data}")
        >>> 
        >>> stream = WebSocketDataStream(
        ...     url='wss://api.example.com/market',
        ...     api_key='your_api_key'
        ... )
        >>> stream.subscribe(['000001', '600000'])
        >>> stream.add_callback(on_data)
        >>> stream.start_streaming()
    """
    
    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        reconnect: bool = True,
        reconnect_interval: int = 5,
        ping_interval: int = 30,
        message_parser: Optional[Callable] = None
    ):
        """
        初始化WebSocket数据流
        
        Args:
            url: WebSocket服务器URL
            api_key: API密钥(如需要)
            reconnect: 是否自动重连
            reconnect_interval: 重连间隔(秒)
            ping_interval: 心跳间隔(秒)
            message_parser: 自定义消息解析器
        """
        super().__init__()
        self.url = url
        self.api_key = api_key
        self.reconnect = reconnect
        self.reconnect_interval = reconnect_interval
        self.ping_interval = ping_interval
        self.message_parser = message_parser or self._default_parser
        
        self.ws = None
        self._ws_thread = None
        self._ping_thread = None
        self._connected = False
    
    def subscribe(self, subscribe_symbols: List[str]):
        """
        订阅股票代码列表
        
        Args:
            subscribe_symbols: 股票代码列表
        """
        self.subscribe_symbols = subscribe_symbols
        logger.info(f"已设置订阅列表: {subscribe_symbols}")
        
        # 如果已连接，发送订阅消息
        if self._connected and self.ws:
            self._send_subscribe_message()
    
    def unsubscribe(self):
        """取消所有订阅"""
        if self._connected and self.ws:
            self._send_unsubscribe_message()
        
        self.subscribe_symbols = []
        logger.info("已取消所有订阅")
    
    def _connect(self):
        """建立WebSocket连接"""
        try:
            # 注意: 这里使用websocket-client库
            import websocket
            
            # 创建WebSocket连接
            self.ws = websocket.WebSocketApp(
                self.url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # 在单独的线程中运行
            self._ws_thread = threading.Thread(
                target=self.ws.run_forever,
                daemon=True
            )
            self._ws_thread.start()
            
            # 等待连接建立
            timeout = 10
            start_time = time.time()
            while not self._connected and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if not self._connected:
                raise ConnectionError("WebSocket连接超时")
            
            logger.info(f"WebSocket已连接: {self.url}")
            
        except ImportError:
            raise ImportError("需要安装websocket-client: pip install websocket-client")
        except Exception as e:
            logger.error(f"WebSocket连接失败: {str(e)}")
            raise
    
    def _disconnect(self):
        """断开WebSocket连接"""
        self._connected = False
        
        if self.ws:
            self.ws.close()
            self.ws = None
        
        logger.info("WebSocket已断开")
    
    def _on_open(self, ws):
        """WebSocket连接建立回调"""
        self._connected = True
        logger.info("WebSocket连接已建立")
        
        # 发送认证信息(如需要)
        if self.api_key:
            self._send_auth_message()
        
        # 发送订阅消息
        if self.subscribe_symbols:
            self._send_subscribe_message()
        
        # 启动心跳线程
        self._start_ping_thread()
    
    def _on_message(self, ws, message):
        """WebSocket消息接收回调"""
        try:
            # 解析消息
            data = self.message_parser(message)
            
            if data is not None:
                # 触发回调
                self.on_market_data(data)
                
        except Exception as e:
            logger.error(f"消息处理失败: {str(e)}, 原始消息: {message}")
    
    def _on_error(self, ws, error):
        """WebSocket错误回调"""
        logger.error(f"WebSocket错误: {str(error)}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭回调"""
        self._connected = False
        logger.warning(f"WebSocket连接关闭: {close_status_code} - {close_msg}")
        
        # 自动重连
        if self.reconnect and self._is_running:
            logger.info(f"{self.reconnect_interval}秒后尝试重连...")
            time.sleep(self.reconnect_interval)
            if self._is_running:
                self._connect()
    
    def _send_auth_message(self):
        """发送认证消息"""
        auth_msg = {
            'action': 'auth',
            'api_key': self.api_key
        }
        self._send_message(auth_msg)
    
    def _send_subscribe_message(self):
        """发送订阅消息"""
        subscribe_msg = {
            'action': 'subscribe',
            'symbols': self.subscribe_symbols
        }
        self._send_message(subscribe_msg)
        logger.info(f"已发送订阅消息: {self.subscribe_symbols}")
    
    def _send_unsubscribe_message(self):
        """发送取消订阅消息"""
        unsubscribe_msg = {
            'action': 'unsubscribe',
            'symbols': self.subscribe_symbols
        }
        self._send_message(unsubscribe_msg)
    
    def _send_message(self, message: Dict):
        """发送消息"""
        if self.ws and self._connected:
            self.ws.send(json.dumps(message))
    
    def _start_ping_thread(self):
        """启动心跳线程"""
        def ping_loop():
            while self._connected and self._is_running:
                try:
                    self._send_message({'action': 'ping'})
                    time.sleep(self.ping_interval)
                except Exception as e:
                    logger.error(f"心跳发送失败: {str(e)}")
                    break
        
        self._ping_thread = threading.Thread(target=ping_loop, daemon=True)
        self._ping_thread.start()
    
    def _default_parser(self, message: str) -> Optional[Dict]:
        """
        默认的消息解析器
        
        Args:
            message: 原始消息字符串
            
        Returns:
            解析后的数据字典，如果是系统消息则返回None
        """
        try:
            data = json.loads(message)
            
            # 过滤系统消息
            if 'action' in data:
                action = data['action']
                if action in ['pong', 'subscribed', 'unsubscribed']:
                    logger.debug(f"收到系统消息: {action}")
                    return None
            
            # 返回市场数据
            return data
            
        except json.JSONDecodeError:
            logger.error(f"JSON解析失败: {message}")
            return None
    
    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """
        获取最新数据
        
        注意: WebSocket流不保存历史数据，此方法返回None
        """
        logger.warning("WebSocket流不保存历史数据")
        return None
    
    def start_streaming(self, interval: int = 30):
        """
        开始流式传输数据
        
        Args:
            interval: 参数无效，WebSocket是事件驱动的
        """
        self._is_running = True
        
        # 建立连接
        self._connect()
        
        # 保持运行状态
        try:
            while self._is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到中断信号")
            self.stop()
    
    def stop(self):
        """停止数据流"""
        logger.info("正在停止WebSocket数据流...")
        self._is_running = False
        self._disconnect()
        logger.info("WebSocket数据流已停止")


def on_data(data):
    print(f"Received data: {data}")
    
stream = WebSocketDataStream(
    url="wss://api.example.com/market",
    api_key="your_api_key"
)
stream.add_callback(on_data)
stream.subscribe(["000001", "600000"])
stream.start_streaming()

