"""
WebSocket数据流示例

展示如何使用WebSocketDataStream连接实时WebSocket服务。

注意: 这个示例需要一个真实的WebSocket服务器。
如果你没有可用的服务器，可以使用模拟服务器或跳过此示例。
"""

import logging
import time
from newstreamer.streams.websocket_stream import WebSocketDataStream

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_websocket_stream_basic():
    """示例1: 基本WebSocket数据流使用"""
    logger.info("=" * 60)
    logger.info("示例1: 基本WebSocket数据流")
    logger.info("=" * 60)
    
    # 定义回调函数
    def on_market_data(data):
        """处理市场数据"""
        logger.info(f"收到数据: {data}")
    
    # 创建WebSocket数据流
    # 注意: 请替换为你的实际WebSocket URL和API密钥
    stream = WebSocketDataStream(
        url='wss://stream.example.com/market',  # 替换为实际URL
        api_key='your_api_key_here',  # 替换为实际API密钥
        reconnect=True,
        reconnect_interval=5,
        ping_interval=30
    )
    
    # 订阅股票
    stream.subscribe(['000001', '600000', '000002'])
    
    # 添加回调
    stream.add_callback(on_market_data)
    
    try:
        # 启动流式传输(阻塞模式)
        # 可以使用Ctrl+C停止
        logger.info("\n开始接收WebSocket数据(按Ctrl+C停止)...")
        stream.start_streaming()
        
    except KeyboardInterrupt:
        logger.info("\n收到停止信号")
    finally:
        stream.stop()
    
    logger.info("\n示例1完成\n")


def example_websocket_custom_parser():
    """示例2: 自定义消息解析器"""
    logger.info("=" * 60)
    logger.info("示例2: 自定义消息解析器")
    logger.info("=" * 60)
    
    # 定义自定义解析器
    def custom_parser(message):
        """
        自定义消息解析器
        
        假设WebSocket返回的消息格式为:
        {"type": "quote", "data": {"symbol": "000001", "price": 100.5, ...}}
        """
        import json
        try:
            msg = json.loads(message)
            
            # 过滤非数据消息
            if msg.get('type') == 'quote':
                return msg.get('data')
            
            return None
            
        except json.JSONDecodeError:
            logger.error(f"JSON解析失败: {message}")
            return None
    
    # 定义回调
    def on_data(data):
        if data:
            logger.info(
                f"{data.get('symbol')}: "
                f"价格={data.get('price')}, "
                f"成交量={data.get('volume')}"
            )
    
    # 创建WebSocket数据流(使用自定义解析器)
    stream = WebSocketDataStream(
        url='wss://stream.example.com/market',
        api_key='your_api_key_here',
        message_parser=custom_parser  # 使用自定义解析器
    )
    
    stream.subscribe(['000001', '600000'])
    stream.add_callback(on_data)
    
    try:
        logger.info("\n开始接收数据...")
        # 运行30秒后停止
        import threading
        stream_thread = threading.Thread(
            target=stream.start_streaming,
            daemon=True
        )
        stream_thread.start()
        
        time.sleep(30)
        
    finally:
        stream.stop()
    
    logger.info("\n示例2完成\n")


def example_mock_websocket_server():
    """示例3: 使用模拟WebSocket服务器进行测试"""
    logger.info("=" * 60)
    logger.info("示例3: 模拟WebSocket服务器")
    logger.info("=" * 60)
    
    logger.info("""
    这个示例展示了如何创建一个简单的WebSocket模拟服务器进行测试。
    
    你可以使用以下代码创建一个模拟服务器(需要安装 websockets库):
    
    # mock_server.py
    import asyncio
    import websockets
    import json
    import random
    
    async def handler(websocket, path):
        async for message in websocket:
            data = json.loads(message)
            
            if data['action'] == 'subscribe':
                # 模拟发送市场数据
                for symbol in data['symbols']:
                    quote = {
                        'symbol': symbol,
                        'price': round(100 + random.uniform(-5, 5), 2),
                        'volume': random.randint(10000, 100000)
                    }
                    await websocket.send(json.dumps(quote))
    
    async def main():
        async with websockets.serve(handler, "localhost", 8765):
            await asyncio.Future()  # run forever
    
    if __name__ == "__main__":
        asyncio.run(main())
    
    然后在另一个终端运行:
    python mock_server.py
    
    最后修改本示例的URL为: ws://localhost:8765
    """)
    
    logger.info("\n示例3完成\n")


def main():
    """运行所有示例"""
    logger.info("\n" + "=" * 60)
    logger.info("WebSocket数据流示例程序")
    logger.info("=" * 60 + "\n")
    
    logger.warning("""
    ⚠️  注意: WebSocket示例需要真实的WebSocket服务器。
    
    如果你没有可用的服务器，请：
    1. 查看 example_mock_websocket_server() 了解如何创建模拟服务器
    2. 或使用其他示例(example_fake.py, example_csv.py)
    
    按Ctrl+C跳过示例...
    """)
    
    try:
        time.sleep(3)
        
        # 取消注释以下行来运行示例
        # example_websocket_stream_basic()
        # example_websocket_custom_parser()
        example_mock_websocket_server()
        
    except KeyboardInterrupt:
        logger.info("\n跳过WebSocket示例")
    
    logger.info("\n" + "=" * 60)
    logger.info("示例完成!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()

