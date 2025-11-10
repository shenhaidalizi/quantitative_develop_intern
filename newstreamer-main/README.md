# NewStreamer - 市场数据流开发包

高性能、模块化的市场数据流框架，用于量化交易系统的数据接入层开发。

## 概述

NewStreamer 提供了统一的数据流接口和多种实现方式，支持实时行情、历史数据回放、模拟数据生成等多种场景。

## 特性

- **统一接口**: 基于标准化的数据流接口，支持多种数据源无缝切换
- **多种实现**: 内置实时行情、历史回放、模拟数据等多种数据流
- **高性能**: 使用生成器模式和异步回调，支持大规模数据处理
- **易扩展**: 清晰的接口设计，方便实现自定义数据源
- **生产就绪**: 包含错误处理、日志记录、Redis缓存等企业级特性

实现了fake数据流、amazing——data数据流，live_data数据流，redis数据流，simnow数据流，读写redis功能

## 安装

```bash
cd /home/ubuntu/TradeNew/experiment/zhousiyuan/newstreamer
pip install -r requirements.txt
```

## 快速开始

### 1. 使用模拟数据流

```python
from newstreamer.streams.fake_stream import FakeMarketDataStream

# 创建模拟数据流
stream = FakeMarketDataStream(symbols=['000001', '600000'])

# 获取订单簿数据
for orderbook in stream.get_orderbook('000001'):
    print(f"Symbol: {orderbook.symbol}")
    print(f"最佳买价: {orderbook.get_bid(0)}")
    print(f"最佳卖价: {orderbook.get_ask(0)}")
    
stream.shutdown()
```

### 2. 使用实时数据流

```python
from newstreamer.streams.live_stream import LiveMarketDataStream

# 创建回调函数
def on_data(data_list):
    for data in data_list:
        print(f"{data['symbol']}: {data['price']}")

# 创建实时数据流
stream = LiveMarketDataStream()
stream.subscribe(['000001', '600000'])
stream.add_callback(on_data)

# 开始流式传输（每30秒更新一次）
stream.start_streaming(interval=30)
```

### 3. 从CSV文件读取

```python
from newstreamer.streams.csv_stream import CSVMarketDataStream

stream = CSVMarketDataStream('data/market_data.csv')
for data in stream.get_orderbook('000001'):
    print(data)
```

## 目录结构

```
newstreamer/
├── README.md                  # 项目说明文档
├── requirements.txt           # 依赖包列表
├── setup.py                   # 安装配置
├── newstreamer/              # 主包目录
│   ├── __init__.py
│   ├── streams/              # 数据流实现
│   │   ├── __init__.py
│   │   ├── base.py           # 基类定义
│   │   ├── fake_stream.py    # 模拟数据流
│   │   ├── csv_stream.py     # CSV数据流
│   │   ├── websocket_stream.py  # WebSocket数据流
│   │   └── live_stream.py    # 实时数据流基类
│   ├── models/               # 数据模型
│   │   ├── __init__.py
│   │   ├── orderbook.py      # 订单簿模型
│   │   └── market_data.py    # 市场数据模型
│   └── utils/                # 工具函数
│       ├── __init__.py
│       └── generators.py     # 数据生成器
├── examples/                 # 示例代码
│   ├── example_fake.py       # 模拟数据示例
│   ├── example_csv.py        # CSV数据示例
│   ├── example_websocket.py  # WebSocket示例
│   └── example_live.py       # 实时数据示例
├── tests/                    # 测试代码
│   ├── __init__.py
│   ├── test_fake_stream.py
│   └── test_csv_stream.py
└── docs/                     # 文档
    ├── design.md             # 设计文档
    ├── api.md                # API文档
    └── tutorial.md           # 教程文档
```

## 参考实现

本包提供了两个核心参考实现：

### 1. MarketDataStream (简单生成器模式)
- 位置: `data/src/trader_data/streams/marketDataStream.py`
- 特点: 基于生成器的简单数据流，适合历史数据回放
- 使用场景: 回测、数据分析

### 2. GuguLiveDataStream (回调模式)
- 位置: `data/src/trader_data/streams/realtime/market/guguLiveDataStream.py`
- 特点: 支持订阅、回调、Redis缓存的实时数据流
- 使用场景: 实时交易、在线监控

## 核心概念

### 数据流基类

所有数据流都应继承自基类并实现以下方法：

```python
class DataStreamBase:
    def subscribe(self, symbols: List[str]):
        """订阅股票代码"""
        pass
    
    def unsubscribe(self):
        """取消订阅"""
        pass
    
    def add_callback(self, callback: Callable):
        """添加回调函数"""
        pass
    
    def get_latest_data(self):
        """获取最新数据"""
        pass
    
    def stop(self):
        """停止数据流"""
        pass
```

### 数据模型

#### OrderBook (订单簿)
```python
class OrderBook:
    symbol: str          # 股票代码
    timestamp: int       # 时间戳
    bids: List[float]    # 买价列表
    bid_vols: List[int]  # 买量列表
    asks: List[float]    # 卖价列表
    ask_vols: List[int]  # 卖量列表
```

#### MarketData (市场数据)
```python
class MarketData:
    symbol: str          # 股票代码
    price: float         # 最新价
    volume: int          # 成交量
    open: float          # 开盘价
    high: float          # 最高价
    low: float           # 最低价
    close: float         # 收盘价
```

## 开发指南

### 实现自定义数据流

1. 继承基类
2. 实现必要的抽象方法
3. 处理错误和日志
4. 添加单元测试

示例代码见 `docs/tutorial.md`

### 最佳实践

1. **错误处理**: 使用try-except包裹网络请求和数据解析
2. **日志记录**: 使用logging模块记录关键操作和错误
3. **资源管理**: 实现shutdown/stop方法，确保资源正确释放
4. **性能优化**: 
   - 使用生成器避免一次性加载大量数据
   - 使用Redis缓存减少重复请求
   - 使用ujson提升JSON解析性能

### 测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_fake_stream.py -v

# 运行示例代码
python examples/example_fake.py
```

## 依赖项

- Python >= 3.8
- pandas >= 1.3.0
- numpy >= 1.21.0
- ujson >= 5.1.0
- redis >= 4.0.0
- requests >= 2.26.0
- websocket-client >= 1.2.0

## 常见问题

### Q: 如何选择合适的数据流？

- **回测/研究**: 使用 `FakeMarketDataStream` 或 `CSVMarketDataStream`
- **实时交易**: 使用 `LiveMarketDataStream` 或实现自定义数据源
- **开发调试**: 使用 `FakeMarketDataStream` 生成模拟数据

### Q: 如何提升数据流性能？

1. 启用Redis缓存减少API调用
2. 调整数据更新间隔
3. 使用异步回调处理数据
4. 对订阅列表进行合理分批

### Q: 如何处理连接中断？

参考 `GuguLiveDataStream` 的实现：
- 使用重试机制
- 记录错误日志
- 提供断线重连功能

## 贡献指南

欢迎贡献新的数据源实现！

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/YourDataSource`)
3. 提交更改 (`git commit -am 'Add YourDataSource'`)
4. 推送到分支 (`git push origin feature/YourDataSource`)
5. 创建Pull Request

## 许可证

本项目仅供内部使用。

## 联系方式

如有问题，请联系开发团队。

---

**版本**: 1.0.0  
**更新日期**: 2025-10-22
