import websocket
import json
import threading
import time
import logging
from typing import List, Dict, Any, Optional
from newstreamer.streams.base import LiveDataStreamBase
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class SimNowDataStream:
    """
    SimNow 数据流实现，获取真实市场数据流
    """

    def __init__(self, username: str, password: str, market_front: str, broker: str, user: str, app: str, auth: str):
        """
        初始化SimNow数据流

        Args:
            username: 用户名
            password: 密码
            market_front: 市场前端（WebSocket服务器地址）
            broker: 经纪商
            user: 用户ID
            app: 应用ID
            auth: 认证码
        """
        self.username = username
        self.password = password
        self.market_front = market_front
        self.broker = broker
        self.user = user
        self.app = app
        self.auth = auth
        self.subscribe_symbols = []
        self._is_running = False
        self._stream_thread: Optional[threading.Thread] = None

        self.ws = None
        self._connected = False

        # 登录到市场和交易前端
        self.login()

    def login(self):
        """登录到市场数据和交易系统"""
        logger.info("Logging into SimNow...")

        try:
            # 登录逻辑，这里通过市场前端地址建立连接
            logger.info(f"Connecting to market front: {self.market_front}, broker: {self.broker}, user: {self.user}")
            self.ws = websocket.WebSocketApp(
                self.market_front,  # 使用实际的 WebSocket 地址
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            self.ws.run_forever()
            self._connected = True
            logger.info("Login successful.")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            self._connected = False

    def on_open(self, ws):
        """WebSocket连接建立时的回调"""
        logger.info("WebSocket connected")
        # 发送认证消息
        self.send_auth_message()

    def send_auth_message(self):
        """发送认证消息"""
        auth_msg = {
            'action': 'auth',
            'api_key': self.auth,
            'user': self.user,
            'app': self.app,
            'broker': self.broker
        }
        self.ws.send(json.dumps(auth_msg))
        logger.info("Authentication message sent.")

    def on_message(self, ws, message):
        """WebSocket消息接收回调"""
        try:
            data = json.loads(message)
            logger.info(f"Received data: {data}")
            self.on_market_data(data)
        except Exception as e:
            logger.error(f"Error parsing message: {e}")

    def on_error(self, ws, error):
        """WebSocket错误回调"""
        logger.error(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭回调"""
        self._connected = False
        logger.warning(f"WebSocket closed: {close_status_code}, {close_msg}")

    def on_market_data(self, data: Dict[str, Any]):
        """处理接收到的市场数据"""
        logger.info(f"Market data: {data}")
        # 在此你可以处理数据或写入Redis等地方

    def subscribe(self, subscribe_symbols: List[str]):
        """订阅市场数据"""
        self.subscribe_symbols = subscribe_symbols
        logger.info(f"Subscribing to symbols: {', '.join(subscribe_symbols)}")
        
        # 在此可以发送订阅消息给WebSocket服务器
        subscribe_msg = {
            'action': 'subscribe',
            'symbols': self.subscribe_symbols
        }
        self.ws.send(json.dumps(subscribe_msg))

    def subscribe_all(self):
        """订阅所有可用的市场数据"""
        logger.info(f"Subscribing to all market data...")

        # 创建一个通用的订阅消息，表示订阅所有数据
        subscribe_msg = {
            'action': 'subscribe_all'  # 假设有一个订阅所有数据的操作
        }
        self.ws.send(json.dumps(subscribe_msg))

    def on_message(self, ws, message):
        """WebSocket消息接收回调"""
        try:
            data = json.loads(message)
            logger.info(f"Received data: {data}")

            # 这里是处理所有市场数据的地方
            self.on_market_data(data)  # 可以直接调用统一的市场数据处理方法

        except Exception as e:
            logger.error(f"Error parsing message: {e}")
    def on_market_data(self, data: Dict[str, Any]):
        """处理接收到的所有市场数据"""
        logger.info(f"Market data received: {data}")
        
        # 你可以在这里处理数据，或者将其存储到 Redis
        self.amz2redis(data)

    def amz2redis(self, data: Any):
        """将数据存储到 Redis"""
        try:
            # 将数据存储到 Redis
            for key, value in data.items():
                self.redis_client.write_data(key, value)
                logger.info(f"Data written to Redis: {key} -> {value}")
        except Exception as e:
            logger.error(f"Error writing to Redis: {e}")



    def unsubscribe(self):
        """取消订阅"""
        logger.info(f"Unsubscribing from symbols: {', '.join(self.subscribe_symbols)}")
        unsubscribe_msg = {
            'action': 'unsubscribe',
            'symbols': self.subscribe_symbols
        }
        self.ws.send(json.dumps(unsubscribe_msg))
        self.subscribe_symbols = []

    def start_streaming(self):
        """启动数据流"""
        if self._is_running:
            logger.warning("Data stream is already running.")
            return

        self._is_running = True
        self._stream_thread = threading.Thread(target=self._stream_data)
        self._stream_thread.start()
        logger.info("Data streaming started.")

    def _stream_data(self):
        """模拟获取实时数据流"""
        while self._is_running:
            if self._connected:
                # 如果已经连接，模拟从 WebSocket 接收数据
                time.sleep(5)

    def stop(self):
        """停止数据流"""
        self._is_running = False
        if self._stream_thread:
            self._stream_thread.join()
        logger.info("Data stream stopped.")

# 创建数据流实例，传入认证信息和市场数据服务器地址
data_stream = SimNowDataStream(
    username="your_username", 
    password="your_password", 
    market_front=os.getenv("MARKET_FRONT"), 
    broker=os.getenv("BROKER"),
    user=os.getenv("USER"),
    app=os.getenv("APP"),
    auth=os.getenv("AUTH")
)

# 启动数据流
data_stream.start_streaming()

# 订阅所有市场数据
data_stream.subscribe_all()

# 在获取一定时间的数据后停止
time.sleep(120)  # 运行2分钟
data_stream.stop()

