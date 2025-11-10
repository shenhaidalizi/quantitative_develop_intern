import AmazingData as ad
import logging
import threading
import time
from typing import List, Callable, Dict, Any, Union
from newstreamer.streams.base import LiveDataStreamBase
import json
import logging
import requests
import time
import threading
from typing import List, Dict, Any, Optional, Callable
from newstreamer.streams.base import LiveDataStreamBase
from newstreamer.streams.to_redis import RedisClient
from flask import Flask, jsonify, request
import redis
import json
from flask import jsonify
import os
from dotenv import load_dotenv
load_dotenv()


# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取环境变量
username = os.getenv('AMZ_USERNAME')
password = os.getenv('AMZ_PWD')
host = os.getenv('AMZ_HOST')
port = int(os.getenv('AMZ_PORT'))

load_dotenv()

# 连接参数
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "")

# 兼容：既支持单账号，也支持读写分离账号
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_WRITE_USERNAME = os.getenv("REDIS_WRITE_USERNAME", REDIS_USERNAME)
REDIS_WRITE_PASSWORD = os.getenv("REDIS_WRITE_PASSWORD", REDIS_PASSWORD)
REDIS_READ_USERNAME = os.getenv("REDIS_READ_USERNAME", REDIS_USERNAME)
REDIS_READ_PASSWORD = os.getenv("REDIS_READ_PASSWORD", REDIS_PASSWORD)

class AmazingDataStream(LiveDataStreamBase):
    """
    AmazingData 实时数据流实现
    """

    def __init__(self, username: str, password: str, host: str, port: int):
        """
        初始化AmazingData流
        
        Args:
            username: 用户名
            password: 密码
            host: API主机地址
            port: API端口
        """
        super().__init__()
        self.subscribed_data = []
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self._url = f'http://{host}:{port}/api'
        self.subscribe_symbols = []
        self._is_running = False
        self._stream_thread: Optional[threading.Thread] = None
        
        
        self.redis_client = RedisClient(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            username=REDIS_WRITE_USERNAME,
            password=REDIS_WRITE_PASSWORD,
            prefix=REDIS_PREFIX,
        )
        ad.login(username=self.username, password=self.password, host=self.host, port=self.port)
        

    def test(self):
        base_data_object = ad.BaseData() 
        code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A') 
        # 实时订阅 
        sub_data = ad.SubscribeData() 
        @sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value) 
        def onSnapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):     
            print(period, data)  
        sub_data.run() 

    
    def subscribe(self, subscribe_symbols: List[str]):
        self.subscribe_symbols = subscribe_symbols
        logger.info(f"已订阅股票: {', '.join(subscribe_symbols)}")

        base_data_object = ad.BaseData()
        code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')

        sub_data = ad.SubscribeData()

        @sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
        def onSnapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
            self._store_snapshot_by_code_json(data)
            # 将单条快照写入 Redis，key=code，value=完整快照字典
            # self._store_snapshot_by_code_json(data)

        sub_data.run()

        def amz2redis(self, data: Any):
            
            try:
                for code in data:
                    self.redis_client.write_data(code, data[code])
                    logger.info(f"数据已写入 Redis：{code} -> {data[code]}")
            except Exception as e:
                logger.error(f"写入 Redis 时发生错误: {e}")
                raise
    
    def unsubscribe(self):
        """取消所有订阅"""
        self.subscribe_symbols = []
        logger.info("已取消所有订阅")

    def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """
        获取最新市场数据
        
        返回：
            dict：包含订阅股票数据的字典
        """
        if not self.subscribe_symbols:
            return None
        
        # 从API获取最新数据
        data = {}
        for symbol in self.subscribe_symbols:
            url = f"{self._url}/live/cn/{symbol}"
            try:
                response = requests.get(url, auth=(self.username, self.password))
                if response.status_code == 200:
                    data[symbol] = response.json()
                else:
                    logger.error(f"获取数据失败: {symbol}, 错误码: {response.status_code}")
            except requests.RequestException as e:
                logger.error(f"请求数据失败: {symbol}, 错误: {e}")
        
        logger.info(f"获取最新市场数据: {data}")
        return data if data else None

    def _store_snapshot_by_code(self, snap: Any) -> None:
        """将单只股票快照写入 Redis，key=code，value=快照字典"""
        code = getattr(snap, 'code', None) or getattr(snap, 'symbol', None)
        if not code:
            logger.warning("快照缺少 code/symbol 字段，已跳过")
            return

        payload = self._snapshot_to_dict(snap)
        # RedisClient.write_data 会处理 datetime 等不可序列化对象
        self.redis_client.write_data(code, payload)
        logger.info(f"已写入 Redis：{code}")

    # newstreamer/streams/Amazing_data_stream.py
    # 保留 code 字段：key=code，value=包含 code 在内的完整快照 JSON

    def _store_snapshot_by_code_json(self, snap: Any) -> None:
        # print("_store_snapshot_by_code_json")
        """将单只股票快照存入 Redis：key=code，value=完整快照(包含 code)。"""
        code = getattr(snap, "code", None) or getattr(snap, "symbol", None)
        if not code:
            logger.warning("快照缺少 code/symbol 字段，已跳过")
            return
        payload = self._snapshot_to_payload(snap)  # 保留 code
        self.redis_client.write_data(code, payload)  # RedisClient 会处理 datetime 等序列化
        logger.info(f"写入 Redis 成功：key={code}")

    def _snapshot_to_payload(self, snap: Any) -> Dict[str, Any]:
        # print("_snapshot_to_payload")
        """提取快照为字典，保留 code 字段。"""
        fields = [
            "trade_time", "pre_close", "last", "open", "high", "low", "close",
            "volume", "amount", "num_trades", "high_limited", "low_limited",
            "iopv", "trading_phase_code",
        ]
        for i in range(1, 6):
            fields += [f"ask_price{i}", f"ask_volume{i}", f"bid_price{i}", f"bid_volume{i}"]

        d: Dict[str, Any] = {}

        # 保留 code
        if hasattr(snap, "code"):
            d["code"] = getattr(snap, "code")
        elif hasattr(snap, "symbol"):
            d["code"] = getattr(snap, "symbol")

        # 提取常用字段
        for f in fields:
            if hasattr(snap, f):
                d[f] = getattr(snap, f)

        # 若内容过少，追加通用提取（非私有、不可调用）
        if len(d) < 4:
            try:
                for k in dir(snap):
                    if k.startswith("_"):
                        continue
                    v = getattr(snap, k, None)
                    if callable(v):
                        continue
                    d.setdefault(k, v)
            except Exception:
                pass

        return d

    def _snapshot_to_dict(self, snap: Any) -> Dict[str, Any]:
        """将 Amazing 快照对象转为字典，优先提取常用字段，缺失再回退通用提取。"""
        # 明确列出常用/关键字段（你贴出的字段名）
        fields = [
            'code', 'trade_time', 'pre_close', 'last', 'open', 'high', 'low', 'close',
            'volume', 'amount', 'num_trades', 'high_limited', 'low_limited', 'iopv',
            'trading_phase_code',
        ]
        for i in range(1, 5 + 1):
            fields += [
                f'ask_price{i}', f'ask_volume{i}',
                f'bid_price{i}', f'bid_volume{i}',
            ]

        d: Dict[str, Any] = {}
        for f in fields:
            if hasattr(snap, f):
                d[f] = getattr(snap, f)

        # 若上面字段不全，补充一次通用提取（非私有且非可调用）
        if len(d) <= 2:
            try:
                for k in dir(snap):
                    if k.startswith('_'):
                        continue
                    v = getattr(snap, k, None)
                    if callable(v):
                        continue
                    d[k] = v
            except Exception:
                pass

        return d

    def start_streaming(self, interval: int = 30):
        """
        启动数据流
        
        每隔 `interval` 秒获取一次最新的市场数据并触发回调
        
        Args:
            interval: 数据刷新间隔（秒）
        """
        if self._is_running:
            logger.warning("数据流已经在运行中。")
            return
        
        self._is_running = True
        self._stream_thread = threading.Thread(target=self._stream_data, args=(interval,))
        self._stream_thread.start()
        logger.info(f"数据流已启动，间隔：{interval}秒")

    def stop(self):
        """停止数据流"""
        self._is_running = False
        if self._stream_thread:
            self._stream_thread.join()
        logger.info("数据流已停止")

    def _stream_data(self, interval: int):
        """获取并处理实时数据"""
        while self._is_running:
            data = self.get_latest_data()
            if data:
                self.on_market_data(data)
            time.sleep(interval)

    def _extract_ts_from_snapshot(self, snap: Any) -> str:
        # 优先用 trade_time（datetime），其次 timestamp/ts/time...
        print("_extract_ts_from_snapshot")
        if hasattr(snap, "trade_time") and getattr(snap, "trade_time"):
            dt = getattr(snap, "trade_time")
            try:
                return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            except Exception:
                return str(dt)
        for k in ("timestamp", "ts", "time", "datetime", "updateTime", "serverTime", "epoch"):
            if hasattr(snap, k):
                v = getattr(snap, k)
                if isinstance(v, (int, float)):
                    return str(int(v))
                return str(v)
        # 兜底：当前纳秒时间
        try:
            return str(time.time_ns())
        except Exception:
            return str(int(time.time() * 1000))

    def on_market_data(self, data: Any):
        """
        市场数据回调处理
        
        向所有已注册的回调函数传递最新的数据
        
        Args:
            data: 最新的市场数据
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
            bool: 如果正在运行返回True
        """
        return self._is_running

    def register_api(self, app):
        app.add_url_rule("/api/stock-data", view_func=self._api_get_all_stock_data, methods=["GET"])
        app.add_url_rule("/api/stock-data/<string:code>", view_func=self._api_get_stock_data, methods=["GET"])

    def _api_get_all_stock_data(self):
        rc = self.redis_client
        keys = list(rc.client.scan_iter("*"))  # 或 rc.keys("*") 若你已封装
        data = {k: rc.get_data(k) for k in keys}
        return jsonify({"status": "success", "data": data, "count": len(data)}), 200

    def _api_get_stock_data(self, code: str):
        rc = self.redis_client
        obj = rc.get_data(code)
        if obj is None:
            return jsonify({"status": "error", "message": f"{code} not found"}), 404
        return jsonify({"status": "success", "data": obj}), 200

from flask import Flask
if __name__ == '__main__':
    
    # # 示例回调函数
    # def print_data(data):
    #     print("接收到市场数据：", data)

    # 创建一个数据流实例
    data_stream = AmazingDataStream(username=username, password=password, host=host, port=port)
    # app = Flask(__name__)
    # data_stream.register_api(app)  # 不会丢失 self.redis_client
    # app.run(host="0.0.0.0", port=5000, debug=True)

    # # # # 添加回调函数
    # data_stream.add_callback(print_data)

    # # # 订阅某些股票
    # market_snapshot = data_stream.redis_client.read_hash_all(ts_key)  # -> { "300535.SZ": {...}, "300410.SZ": {...}, ... }
    # print(market_snapshot)
    data_stream.subscribe(['920299'])
    # print(data_stream.redis_client.get_data('688678.SH'))

    # # # 启动数据流，每30秒获取一次数据
    # data_stream.start_streaming(interval=30)

    # # # 等待一段时间后停止数据流
    # time.sleep(120)  # 运行2分钟
    # data_stream.stop()

    # data_stream.test()