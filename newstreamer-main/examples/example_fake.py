"""
模拟数据流示例

展示如何使用FakeMarketDataStream和FakeLiveDataStream生成模拟数据。
"""

import logging
import time
from newstreamer.streams.fake_stream import FakeMarketDataStream, FakeLiveDataStream

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_fake_generator_stream():
    """示例1: 使用生成器模式的模拟数据流"""
    logger.info("=" * 60)
    logger.info("示例1: 生成器模式的模拟数据流")
    logger.info("=" * 60)
    
    # 创建模拟数据流
    stream = FakeMarketDataStream(
        symbols=['000001', '600000', '000002'],
        initial_price=100.0,
        volatility=0.02,
        max_ticks=10,  # 每个股票生成10个tick
        tick_interval=0.5,  # 0.5秒一个tick
        seed=42  # 固定随机种子，确保结果可重复
    )
    
    # 连接
    stream.connect()
    
    try:
        # 获取000001的订单簿数据
        logger.info("\n获取股票 000001 的订单簿数据:")
        for i, orderbook in enumerate(stream.get_orderbook('000001'), 1):
            mid_price = orderbook.get_mid_price()
            spread = orderbook.get_spread()
            logger.info(
                f"Tick {i}: 中间价={mid_price:.2f}, "
                f"价差={spread:.4f}, "
                f"最佳买价={orderbook.get_bid(0):.2f}, "
                f"最佳卖价={orderbook.get_ask(0):.2f}"
            )
        
    finally:
        # 关闭连接
        stream.shutdown()
    
    logger.info("\n示例1完成\n")


def example_fake_live_stream():
    """示例2: 使用回调模式的模拟实时数据流"""
    logger.info("=" * 60)
    logger.info("示例2: 回调模式的模拟实时数据流")
    logger.info("=" * 60)
    
    # 定义回调函数
    def on_market_data(data_list):
        """处理市场数据"""
        logger.info(f"\n收到 {len(data_list)} 条市场数据:")
        for data in data_list:
            if isinstance(data, dict):
                logger.info(
                    f"  {data['symbol']}: "
                    f"价格={data['price']:.2f}, "
                    f"涨跌幅={data['chg_pct']:.2f}%, "
                    f"成交量={data['volume']:,}"
                )
    
    # 创建实时数据流
    stream = FakeLiveDataStream(
        initial_price=100.0,
        volatility=0.03,
        return_type='dict',
        seed=42
    )
    
    # 订阅股票
    stream.subscribe(['000001', '600000', '000002'])
    
    # 添加回调
    stream.add_callback(on_market_data)
    
    # 启动流式传输(在单独线程中运行)
    import threading
    stream_thread = threading.Thread(
        target=lambda: stream.start_streaming(interval=3),
        daemon=True
    )
    stream_thread.start()
    
    # 运行15秒后停止
    logger.info("\n数据流将运行15秒...")
    time.sleep(15)
    
    # 停止数据流
    stream.stop()
    logger.info("\n示例2完成\n")


def example_fake_object_mode():
    """示例3: 使用对象返回模式"""
    logger.info("=" * 60)
    logger.info("示例3: 对象返回模式")
    logger.info("=" * 60)
    
    # 定义回调函数
    def on_market_data(data_list):
        """处理市场数据对象"""
        for data in data_list:
            # data是SimpleMarketData对象
            logger.info(
                f"{data.symbol}: {data.price:.2f} "
                f"({data.get_change_pct():+.2f}%) "
                f"振幅={data.get_amplitude():.2f}%"
            )
            
            # 检查涨停/跌停
            if data.is_limit_up():
                logger.warning(f"  ⚠️ {data.symbol} 涨停!")
            elif data.is_limit_down():
                logger.warning(f"  ⚠️ {data.symbol} 跌停!")
    
    # 创建实时数据流(返回对象)
    stream = FakeLiveDataStream(
        initial_price=100.0,
        volatility=0.05,  # 增大波动率
        return_type='object',  # 返回对象而不是字典
        seed=42
    )
    
    stream.subscribe(['000001', '600000'])
    stream.add_callback(on_market_data)
    
    # 启动流式传输
    stream_thread = threading.Thread(
        target=lambda: stream.start_streaming(interval=2),
        daemon=True
    )
    stream_thread.start()
    
    # 运行10秒
    time.sleep(10)
    
    # 获取最新数据
    logger.info("\n获取最新数据:")
    latest_data = stream.get_latest_data()
    if latest_data:
        for symbol, data in latest_data.items():
            logger.info(f"  {symbol}: {data}")
    
    stream.stop()
    logger.info("\n示例3完成\n")


def main():
    """运行所有示例"""
    logger.info("\n" + "=" * 60)
    logger.info("模拟数据流示例程序")
    logger.info("=" * 60 + "\n")
    
    # 运行示例
    example_fake_generator_stream()
    time.sleep(1)
    
    example_fake_live_stream()
    time.sleep(1)
    
    example_fake_object_mode()
    
    logger.info("=" * 60)
    logger.info("所有示例完成!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()

