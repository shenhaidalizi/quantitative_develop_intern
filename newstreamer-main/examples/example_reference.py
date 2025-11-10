"""
参考实现示例

展示原始参考实现(marketDataStream和guguLiveDataStream)的使用方式。

这个文件展示了如何使用trader_data包中的参考实现，
以便开发者理解如何基于这些参考实现开发自己的数据流。
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def show_market_data_stream_usage():
    """展示MarketDataStream的使用方式"""
    logger.info("=" * 60)
    logger.info("参考实现1: MarketDataStream (生成器模式)")
    logger.info("=" * 60)
    
    logger.info("""
MarketDataStream 是一个简单的生成器模式数据流实现。

特点:
- 使用生成器(Generator)模式，内存效率高
- 适合历史数据回放和批量处理
- 简单的错误处理机制
- 自动管理连接生命周期

使用示例:
```python
from trader_data.streams.marketDataStream import MarketDataStream

# 创建数据流
stream = MarketDataStream(market_type='futures')

# 获取订单簿数据流
for orderbook in stream.get_orderbook('au2412'):
    print(f"Symbol: {orderbook.symbol}")
    print(f"最佳买价: {orderbook.get_bid(0)}")
    print(f"最佳卖价: {orderbook.get_ask(0)}")

# 关闭连接
stream.shutdown()
```

核心方法:
1. __init__(market_type): 初始化，指定市场类型
2. connect(): 建立数据连接
3. get_orderbook(symbol): 获取订单簿数据流(生成器)
4. shutdown(): 关闭连接并清理资源
5. _handle_error(error): 统一错误处理

实现要点:
- 使用TickProvider作为数据提供者
- 使用yield from委托生成器
- 在shutdown中确保资源释放
- 使用logger记录关键操作

文件位置: data/src/trader_data/streams/marketDataStream.py
    """)


def show_gugu_live_data_stream_usage():
    """展示GuguLiveDataStream的使用方式"""
    logger.info("\n" + "=" * 60)
    logger.info("参考实现2: GuguLiveDataStream (回调模式)")
    logger.info("=" * 60)
    
    logger.info("""
GuguLiveDataStream 是一个功能完整的实时数据流实现。

特点:
- 使用回调(Callback)模式，支持事件驱动
- 支持订阅/取消订阅机制
- 集成Redis缓存，提升性能
- 支持字典和对象两种返回格式
- 完善的错误处理和日志记录

使用示例:
```python
from trader_data.streams.realtime.market.guguLiveDataStream import GuguLiveDataStream

# 定义回调函数
def on_data(data_list):
    for data in data_list:
        print(f"{data['symbol']}: {data['price']}")

# 创建数据流
stream = GuguLiveDataStream(
    apikey='your_api_key',
    use_redis=True,
    return_type='dict'
)

# 订阅股票
stream.subscribe(['000001', '600000'])

# 添加回调
stream.add_callback(on_data)

# 开始流式传输(每30秒更新)
stream.start_streaming(interval=30)

# 停止
stream.stop()
```

核心方法:
1. __init__(): 初始化配置、Redis客户端等
2. subscribe(symbols): 订阅股票列表
3. unsubscribe(): 取消所有订阅
4. add_callback(callback): 添加数据回调函数
5. start_streaming(interval): 开始流式传输
6. stop(): 停止数据流
7. get_latest_data(): 从Redis获取最新数据
8. _fetch_market_data(): 从API获取数据
9. _store_to_redis(): 存储数据到Redis

实现要点:
- 继承LiveDataStreamBase基类
- 使用requests库进行HTTP请求
- 使用ujson提升JSON解析性能
- 使用Redis pipeline批量操作
- 使用_is_running标志控制循环
- 支持数据格式转换(dict/object)
- 设置Redis数据过期时间

数据流程:
1. subscribe() -> 设置订阅列表
2. start_streaming() -> 进入循环
3. _fetch_market_data() -> 从API获取数据
4. _store_to_redis() -> 缓存到Redis
5. on_market_data_list() -> 触发回调
6. 等待interval秒 -> 重复

文件位置: data/src/trader_data/streams/realtime/market/guguLiveDataStream.py
    """)


def show_key_design_patterns():
    """展示关键设计模式"""
    logger.info("\n" + "=" * 60)
    logger.info("关键设计模式")
    logger.info("=" * 60)
    
    logger.info("""
1. 生成器模式 vs 回调模式

生成器模式 (MarketDataStream):
- 优点: 内存效率高，代码简洁，易于理解
- 缺点: 同步执行，不适合多数据源
- 适用: 历史数据回放、单一数据源

回调模式 (GuguLiveDataStream):
- 优点: 异步处理，支持多订阅者，灵活性高
- 缺点: 代码复杂度高，需要管理回调列表
- 适用: 实时数据流、多数据源、事件驱动系统

2. 基类设计

DataStreamBase (生成器模式基类):
- 定义connect/disconnect抽象方法
- 定义get_orderbook抽象方法(返回生成器)
- 提供shutdown和_handle_error工具方法

LiveDataStreamBase (回调模式基类):
- 定义subscribe/unsubscribe抽象方法
- 定义start_streaming/stop抽象方法
- 提供add_callback/remove_callback回调管理
- 提供on_market_data回调触发机制

3. 错误处理

- 使用try-except捕获异常
- 使用logger记录错误信息
- 在错误处理中断开连接
- 向上层传播关键异常

4. 资源管理

- 实现shutdown/stop方法
- 确保连接正确关闭
- 清理缓存和临时数据
- 使用标志位控制循环

5. 数据标准化

- 定义统一的数据模型(OrderBook, MarketData)
- 提供数据格式转换方法
- 使用column_mapping映射不同数据源
- 支持多种返回格式(dict/object)
    """)


def show_best_practices():
    """展示最佳实践"""
    logger.info("\n" + "=" * 60)
    logger.info("开发最佳实践")
    logger.info("=" * 60)
    
    logger.info("""
1. 日志记录
   - 使用logging模块而不是print
   - 记录连接建立/断开
   - 记录错误和异常
   - 使用适当的日志级别(DEBUG/INFO/WARNING/ERROR)

2. 配置管理
   - 使用环境变量或配置文件
   - 提供合理的默认值
   - 支持参数覆盖

3. 性能优化
   - 使用ujson代替json(更快)
   - 使用Redis缓存减少API调用
   - 使用生成器避免一次性加载大量数据
   - 使用Redis pipeline批量操作

4. 错误处理
   - 捕获具体的异常类型
   - 提供有用的错误信息
   - 实现重试机制
   - 优雅降级

5. 测试
   - 编写单元测试
   - 使用mock模拟外部依赖
   - 测试错误情况
   - 提供示例代码

6. 文档
   - 编写清晰的docstring
   - 提供使用示例
   - 说明数据格式
   - 列出依赖项

7. 代码规范
   - 遵循PEP 8
   - 使用类型提示
   - 保持函数简短
   - 避免深层嵌套
    """)


def main():
    """运行所有示例"""
    logger.info("\n" + "=" * 60)
    logger.info("参考实现示例")
    logger.info("=" * 60 + "\n")
    
    show_market_data_stream_usage()
    show_gugu_live_data_stream_usage()
    show_key_design_patterns()
    show_best_practices()
    
    logger.info("\n" + "=" * 60)
    logger.info("参考实现示例完成!")
    logger.info("=" * 60)
    
    logger.info("""
下一步:
1. 查看 data/src/trader_data/streams/marketDataStream.py
2. 查看 data/src/trader_data/streams/realtime/market/guguLiveDataStream.py
3. 运行其他示例: example_fake.py, example_csv.py
4. 开始实现你自己的数据流!
    """)


if __name__ == '__main__':
    main()

