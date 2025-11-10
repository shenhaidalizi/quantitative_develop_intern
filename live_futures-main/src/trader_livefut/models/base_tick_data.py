from .base_market_data import BaseMarketData
import pandas as pd

class BaseTickData(BaseMarketData):
    """
    A simple data class for tick data that inherits from BaseMarketData.
    
    BaseMarketData provides the basic fields (symbol and trade_date). For tick data,
    the full timestamp is stored separately.
    """
    def __init__(self, timestamp, symbol, bid1, bid_vol1, ask1, ask_vol1, last=None):
        # Convert timestamp to pd.Timestamp
        ts = pd.Timestamp(timestamp)
        # For tick data, we take the trade_date as the normalized date of the timestamp.
        trade_date = ts.normalize()
        # Initialize the base class (BaseMarketData) with symbol and trade_date.
        super().__init__(symbol, trade_date)
        # Store full timestamp and additional tick data fields.
        self.timestamp = ts
        self.bid1 = bid1
        self.bid_vol1 = bid_vol1
        self.ask1 = ask1
        self.ask_vol1 = ask_vol1
        self.last = last

    def get_timestamp(self):
        return self.timestamp

    def __str__(self):
        return (f"{self.timestamp}; {self.symbol}; "
                f"bid: {self.bid1} ({self.bid_vol1}); "
                f"ask: {self.ask1} ({self.ask_vol1}); "
                f"last: {self.last}")