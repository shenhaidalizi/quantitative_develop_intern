"""
CSV数据流示例

展示如何使用CSVMarketDataStream从CSV文件读取历史数据。
"""

import logging
import pandas as pd
from pathlib import Path
from newstreamer.streams.csv_stream import CSVMarketDataStream, CSVLiveDataStream
from newstreamer.utils.generators import RandomOrderBookGenerator, RandomMarketDataGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_csv_data():
    """创建示例CSV数据文件"""
    logger.info("创建示例CSV数据文件...")
    
    # 创建data目录
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    
    # 1. 创建订单簿数据CSV
    orderbook_data = []
    symbols = ['000001', '600000']
    
    for symbol in symbols:
        generator = RandomOrderBookGenerator()
        
        for i in range(100):
            book = generator.generate(symbol, timestamp=1000000000 + i * 1000000000)
            
            # 展开为平面结构
            row = {
                'symbol': book['symbol'],
                'timestamp': book['timestamp'],
            }
            
            # 添加五档数据
            for j in range(min(5, len(book['bids']))):
                row[f'bid{j+1}'] = book['bids'][j]
                row[f'bid_vol{j+1}'] = book['bid_vols'][j]
                row[f'ask{j+1}'] = book['asks'][j]
                row[f'ask_vol{j+1}'] = book['ask_vols'][j]
            
            orderbook_data.append(row)
    
    df_orderbook = pd.DataFrame(orderbook_data)
    orderbook_path = data_dir / 'sample_orderbook.csv'
    df_orderbook.to_csv(orderbook_path, index=False)
    logger.info(f"订单簿数据已保存: {orderbook_path}")
    
    # 2. 创建市场数据CSV
    market_data = []
    
    for symbol in symbols:
        generator = RandomMarketDataGenerator()
        
        for i in range(100):
            data = generator.generate(symbol, timestamp=1000000000 + i * 1000000000)
            market_data.append(data)
    
    df_market = pd.DataFrame(market_data)
    market_path = data_dir / 'sample_market.csv'
    df_market.to_csv(market_path, index=False)
    logger.info(f"市场数据已保存: {market_path}")
    
    return orderbook_path, market_path


def example_csv_orderbook_stream():
    """示例1: 从CSV读取订单簿数据"""
    logger.info("\n" + "=" * 60)
    logger.info("示例1: 从CSV读取订单簿数据")
    logger.info("=" * 60)
    
    csv_path = 'data/sample_orderbook.csv'
    
    # 创建CSV数据流
    stream = CSVMarketDataStream(
        csv_path=csv_path,
        data_type='orderbook'
    )
    
    # 连接(加载数据)
    stream.connect()
    
    try:
        # 查看可用的股票
        symbols = stream.get_symbols()
        logger.info(f"可用股票: {symbols}")
        
        # 查看时间范围
        date_range = stream.get_date_range()
        logger.info(f"时间范围: {date_range}")
        
        # 读取000001的前10条订单簿数据
        logger.info("\n读取 000001 前10条数据:")
        for i, orderbook in enumerate(stream.get_orderbook('000001'), 1):
            if i > 10:
                break
            
            logger.info(
                f"Tick {i}: "
                f"中间价={orderbook.get_mid_price():.2f}, "
                f"价差={orderbook.get_spread():.4f}, "
                f"深度={len(orderbook.bids)}档"
            )
        
    finally:
        stream.shutdown()
    
    logger.info("\n示例1完成")


def example_csv_market_stream():
    """示例2: 从CSV读取市场数据"""
    logger.info("\n" + "=" * 60)
    logger.info("示例2: 从CSV读取市场数据")
    logger.info("=" * 60)
    
    csv_path = 'data/sample_market.csv'
    
    # 创建CSV数据流
    stream = CSVMarketDataStream(
        csv_path=csv_path,
        data_type='market'
    )
    
    stream.connect()
    
    try:
        # 读取600000的前10条市场数据
        logger.info("\n读取 600000 前10条数据:")
        for i, market_data in enumerate(stream.get_market_data('600000'), 1):
            if i > 10:
                break
            
            logger.info(
                f"Tick {i}: "
                f"{market_data.symbol} "
                f"价格={market_data.price:.2f}, "
                f"涨跌幅={market_data.get_change_pct():.2f}%, "
                f"成交量={market_data.volume:,}"
            )
        
    finally:
        stream.shutdown()
    
    logger.info("\n示例2完成")


def example_csv_live_replay():
    """示例3: CSV数据回放模式"""
    logger.info("\n" + "=" * 60)
    logger.info("示例3: CSV数据回放模式")
    logger.info("=" * 60)
    
    csv_path = 'data/sample_market.csv'
    
    # 创建CSV实时数据流
    stream = CSVLiveDataStream(
        csv_path=csv_path,
        data_type='market',
        playback_speed=5.0  # 5倍速回放
    )
    
    stream.connect()
    
    # 定义回调函数
    tick_count = [0]  # 使用列表来在闭包中修改
    
    def on_data(market_data):
        tick_count[0] += 1
        logger.info(
            f"Tick {tick_count[0]}: "
            f"{market_data.symbol} "
            f"价格={market_data.price:.2f}"
        )
        
        # 只处理前20条
        if tick_count[0] >= 20:
            return
    
    # 添加回调
    stream.add_callback(on_data)
    
    # 回放数据
    logger.info("\n开始回放 000001 数据(前20条):")
    stream.replay('000001')
    
    stream.shutdown()
    logger.info("\n示例3完成")


def main():
    """运行所有示例"""
    logger.info("\n" + "=" * 60)
    logger.info("CSV数据流示例程序")
    logger.info("=" * 60)
    
    # 创建示例数据
    orderbook_path, market_path = create_sample_csv_data()
    
    # 运行示例
    example_csv_orderbook_stream()
    example_csv_market_stream()
    example_csv_live_replay()
    
    logger.info("\n" + "=" * 60)
    logger.info("所有示例完成!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()

