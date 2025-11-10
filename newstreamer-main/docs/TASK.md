# 数据流实现任务说明

## 目标

实现一个新的市场数据流类，能够从指定的数据源获取实时或历史行情数据。

## 任务背景

本项目提供了统一的数据流框架，包含：
- 标准化的数据模型（`OrderBook`, `MarketData`, `BookSnapshotData`）
- 两种基类模式：`DataStreamBase`（生成器模式）和`LiveDataStreamBase`（回调模式）
- 完整的参考实现（Fake数据流、CSV数据流、WebSocket数据流）

你的任务是基于这些基础设施，实现一个连接特定数据源的数据流。

## 选择实现模式

### 模式1: 生成器模式 (DataStreamBase)

**适用场景：**
- 历史数据回放
- 文件数据读取
- 批量数据处理

**示例：**
```python
from newstreamer.streams.base import DataStreamBase
from newstreamer.models.orderbook import OrderBook, OrderBookLevel
from datetime import datetime

class YourDataStream(DataStreamBase):
    def __init__(self):
        super().__init__(market_type='stock')
        # 初始化你的数据源连接
    
    def connect(self):
        """建立连接"""
        # 实现连接逻辑
        self._connected = True
    
    def disconnect(self):
        """断开连接"""
        # 实现断开逻辑
        self._connected = False
    
    def get_orderbook(self, symbol: str):
        """获取订单簿数据流"""
        if not self._connected:
            raise ConnectionError("未连接")
        
        # 从你的数据源获取数据
        for raw_data in your_data_source.fetch(symbol):
            # 转换为OrderBook对象
            bids = [OrderBookLevel(price=..., volume=...) for ...]
            asks = [OrderBookLevel(price=..., volume=...) for ...]
            
            orderbook = OrderBook(
                symbol=symbol,
                timestamp=datetime.now(),
                bids=bids,
                asks=asks
            )
            
            yield orderbook
```

**参考实现：**
- `newstreamer/streams/fake_stream.py` - FakeMarketDataStream
- `newstreamer/streams/csv_stream.py` - CSVMarketDataStream

### 模式2: 回调模式 (LiveDataStreamBase)

**适用场景：**
- 实时行情订阅
- WebSocket连接
- 事件驱动系统

**示例：**
```python
from newstreamer.streams.base import LiveDataStreamBase
from newstreamer.models.market_data import MarketData
import time

class YourLiveDataStream(LiveDataStreamBase):
    def __init__(self):
        super().__init__()
        # 初始化连接
    
    def subscribe(self, subscribe_symbols):
        """订阅股票"""
        self.subscribe_symbols = subscribe_symbols
        # 发送订阅请求到数据源
    
    def unsubscribe(self):
        """取消订阅"""
        self.subscribe_symbols = []
    
    def start_streaming(self, interval=30):
        """开始流式传输"""
        self._is_running = True
        
        while self._is_running:
            # 从数据源获取数据
            data_list = []
            for symbol in self.subscribe_symbols:
                raw_data = your_api.get_data(symbol)
                
                # 转换为MarketData对象
                market_data = MarketData(
                    symbol=symbol,
                    trade_date='20250101',
                    timestamp=int(time.time() * 1e9),
                    price=raw_data['price'],
                    volume=raw_data['volume'],
                    # ... 其他字段
                )
                data_list.append(market_data)
            
            # 触发回调
            self.on_market_data(data_list)
            
            time.sleep(interval)
    
    def stop(self):
        """停止数据流"""
        self._is_running = False
    
    def get_latest_data(self):
        """获取最新数据"""
        # 实现获取最新数据的逻辑
        return None
```

**参考实现：**
- `newstreamer/streams/fake_stream.py` - FakeLiveDataStream
- `newstreamer/streams/websocket_stream.py` - WebSocketDataStream

## 数据模型说明

### OrderBook - 订单簿

```python
from newstreamer.models.orderbook import OrderBook, OrderBookLevel

# 创建订单簿
bids = [
    OrderBookLevel(price=100.0, volume=1000),
    OrderBookLevel(price=99.9, volume=2000),
]
asks = [
    OrderBookLevel(price=100.1, volume=1500),
    OrderBookLevel(price=100.2, volume=1800),
]

book = OrderBook(
    symbol='000001',
    timestamp=datetime.now(),
    bids=bids,
    asks=asks
)

# 使用方法
mid_price = book.get_mid_price()
best_bid = book.get_bid(0)
best_ask = book.get_ask(0)
```

### MarketData - 市场数据

```python
from newstreamer.models.market_data import MarketData

data = MarketData(
    symbol='000001',
    trade_date='20250101',
    timestamp=int(time.time() * 1e9),
    price=100.0,
    volume=1000000,
    open=99.0,
    high=101.0,
    low=98.0,
    close=100.0,
    pre_close=99.5,
    # 可选字段
    name='股票名称',
    chg_pct=0.5,
    turnover_rate=3.2
)

# 使用方法
change_pct = data.get_change_pct()
amplitude = data.get_amplitude()
is_limit = data.is_limit_up()
```

### BookSnapshotData - 订单簿快照

```python
from newstreamer.models.market_data import BookSnapshotData
from newstreamer.models.orderbook import OrderBook

snapshot = BookSnapshotData(
    symbol='000001',
    trade_date='20250101',
    timestamp=int(time.time() * 1e9),
    volume=1000000,
    last=100.0,
    book=orderbook,  # OrderBook对象
    open=99.0,
    high=101.0,
    low=98.0
)

# 使用方法
mid = snapshot.get_mid()
weighted_price = snapshot.get_weightedtop()
has_depth = snapshot.check_last_n_book(5)
```

## 开发步骤

### 1. 选择数据源

确定你要接入的数据源，例如：
- Tushare Pro API
- 东方财富API
- 聚宽数据
- Wind数据
- Bloomberg API
- 自定义WebSocket服务

### 2. 选择实现模式

根据数据源特点选择：
- **文件/数据库** → 生成器模式
- **API轮询** → 回调模式
- **WebSocket** → 回调模式

### 3. 实现核心方法

#### 生成器模式必须实现：
- `connect()` - 建立连接
- `disconnect()` - 断开连接
- `get_orderbook(symbol)` - 返回生成器

#### 回调模式必须实现：
- `subscribe(symbols)` - 订阅股票
- `unsubscribe()` - 取消订阅
- `start_streaming(interval)` - 开始流式传输
- `stop()` - 停止数据流
- `get_latest_data()` - 获取最新数据

### 4. 数据转换

将原始数据转换为标准模型：

```python
def convert_raw_to_orderbook(raw_data):
    """转换原始数据为OrderBook"""
    bids = [
        OrderBookLevel(
            price=raw_data[f'bid_price_{i}'],
            volume=raw_data[f'bid_volume_{i}']
        )
        for i in range(5)
    ]
    # ... 类似处理asks
    
    return OrderBook(...)
```

### 5. 错误处理

```python
try:
    # 获取数据
    data = api.fetch(symbol)
except ConnectionError as e:
    self._handle_error(e)
    raise
except Exception as e:
    logger.error(f"未知错误: {str(e)}")
    raise
```

### 6. 日志记录

```python
import logging

logger = logging.getLogger(__name__)

logger.info("连接已建立")
logger.warning("数据为空")
logger.error(f"请求失败: {error}")
logger.debug(f"收到数据: {data}")
```

### 7. 编写测试

```python
# tests/test_your_stream.py
import pytest
from your_module import YourDataStream

def test_connect():
    stream = YourDataStream()
    stream.connect()
    assert stream._connected
    stream.disconnect()

def test_get_data():
    stream = YourDataStream()
    stream.connect()
    
    data = list(stream.get_orderbook('000001'))
    assert len(data) > 0
    assert isinstance(data[0], OrderBook)
    
    stream.shutdown()
```

## 最佳实践

1. **使用环境变量**存储API密钥
2. **实现重试机制**处理网络错误
3. **添加数据验证**确保数据完整性
4. **使用缓存**减少API调用
5. **记录详细日志**便于调试
6. **编写文档字符串**说明使用方法
7. **遵循PEP 8**代码规范

## 示例项目结构

```
your_data_source/
├── __init__.py
├── stream.py              # 数据流实现
├── converter.py           # 数据转换
├── config.py              # 配置文件
├── tests/
│   └── test_stream.py     # 单元测试
├── examples/
│   └── example_usage.py   # 使用示例
└── README.md              # 说明文档
```

## 提交清单

完成后请确保：
- [ ] 实现了所有必须的抽象方法
- [ ] 数据模型使用标准的OrderBook/MarketData/BookSnapshotData
- [ ] 添加了错误处理和日志记录
- [ ] 编写了单元测试（覆盖率 > 80%）
- [ ] 提供了使用示例
- [ ] 编写了README说明文档
- [ ] 代码通过PEP 8检查
- [ ] 添加了必要的依赖到requirements.txt

## 参考资源

### 代码示例
- `examples/example_fake.py` - Fake数据流使用
- `examples/example_csv.py` - CSV数据流使用
- `examples/example_reference.py` - 参考实现说明

### 文档
- `README.md` - 项目总体说明
- `docs/API.md` - API接口文档
- `docs/TUTORIAL.md` - 详细教程

### 原始参考实现
- `data/src/trader_data/streams/marketDataStream.py`
- `data/src/trader_data/streams/realtime/market/guguLiveDataStream.py`

## 常见问题

**Q: 如何处理API限流？**
A: 使用sleep控制请求频率，或使用令牌桶算法。

**Q: 数据源返回的时间格式不统一怎么办？**
A: 统一转换为纳秒时间戳（int）。

**Q: 如何处理断线重连？**
A: 参考WebSocket实现中的重连逻辑。

**Q: 需要缓存数据吗？**
A: 看需求。实时数据流可以使用Redis，历史数据使用本地缓存。

## 联系方式

如有问题，请联系项目负责人。

