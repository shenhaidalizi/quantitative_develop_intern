from trader_livefut.execution.trading_client import TradingClient
import os
c = TradingClient(config_path="/home/ubuntu/TradeNew/live/live_futures/scripts/brokers.json", env="simnow")
c.login(mode="md")
c.set_market_data_callback(lambda tick: print(tick))
c.subscribe(["IM2512","IF2512"])