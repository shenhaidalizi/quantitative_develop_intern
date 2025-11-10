from dataclasses import dataclass
import pandas as pd
from trader_livefut.utils.utils_gen import get_utc_timestamp

@dataclass
class BaseMarketData:
    """
    Base class for market data, containing common fields shared by all market datasets.
    
    Attributes:
        symbol (str): The trading symbol.
        trade_date (pd.Timestamp): The trading date.
    """
    symbol: str
    trade_date: pd.Timestamp
    trade_datetime: pd.Timestamp = None

    def __repr__(self):
        return f"BaseMarketData(symbol={self.symbol}, trade_date={self.trade_date})"

    def __post_init__(self):
        if self.trade_datetime is None:
            self.trade_datetime = self.trade_date.normalize()

    @property
    def utc_timestamp(self):
        """
        Get the UTC timestamp (in milliseconds) corresponding to the trade_datetime.
        """
        return get_utc_timestamp(self.trade_datetime, unit='ms')
    
    @property
    def trade_date_str(self):

        """
        Get the trade date as a string.
        """
        return self.trade_date.strftime('%Y%m%d')
    
    @property
    def trade_datetime_str(self):
        """
        Get the trade datetime as a string.
        """
        return self.trade_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')