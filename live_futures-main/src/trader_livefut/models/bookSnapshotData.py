import pandas as pd
from .base_tick_data import BaseTickData
from .order_book import OrderBook
from trader_livefut.utils.utils_gen import pdtime2int
from trader_livefut.utils.utils_marketdate import convert_marketdata_to_tickdata

class BookSnapshotData(BaseTickData):
    """
    A class representing a snapshot of the order book, inheriting from TickData.
    
    It extends TickData by adding additional market fields and an OrderBook instance.
    """ 
    def __init__(self, trade_date: str, symbol: str, timestamp: str, volume: int, last: float, book: OrderBook,
                 open: float = 0, close: float = 0, high: float = 0, low: float = 0):
        """
        Initialize the BookSnapshotData object.

        Args:
            trade_date (str): The trading date (e.g., "2024-10-18").
            symbol (str): The trading symbol.
            timestamp (str): Detailed tick timestamp.
            volume (int): Trading volume.
            last (float): Last traded price.
            book (OrderBook): The order book data.
            open (float, optional): Opening price.
            close (float, optional): Closing price.
            high (float, optional): Highest price.
            low (float, optional): Lowest price.
        """
        # Extract order book first level info.
        bid1 = book.get_bid(0) if book is not None else None
        bid_vol1 = book.get_bid_vol(0) if book is not None else None
        ask1 = book.get_ask(0) if book is not None else None
        ask_vol1 = book.get_ask_vol(0) if book is not None else None

        # Initialize TickData: this will set self.trade_date as normalized timestamp.
        super().__init__(timestamp, symbol, bid1, bid_vol1, ask1, ask_vol1, last=last)

        # Override trade_date with the provided date.
        self.trade_date = pd.Timestamp(trade_date)
        
        # Additional fields specific to BookSnapshotData.
        self.volume = volume
        self.book = book
        self.open = open
        self.close = close
        self.high = high
        self.low = low

    def get_timestamp(self, unit='ms'):
        """
        Get the timestamp of the snapshot in the specified unit.

        Args:
            unit (str, optional): The time unit for the timestamp. Defaults to 'ms'.

        Returns:
            int: The timestamp in the specified unit.

        Raises:
            ValueError: If timestamp is not a pd.Timestamp.
        """
        # TODO: consider the timezone
        if isinstance(self.timestamp, pd.Timestamp):
            return pdtime2int(self.timestamp, unit=unit)
        else:
            raise ValueError("timestamp is not pd.Timestamp")

    def __str__(self):
        if self.book is None:
            return (f"{str(self.timestamp)};{self.symbol};{self.last};{self.volume}")
        else:
            return (f"{str(self.timestamp)};{self.symbol};{self.last};{self.volume};"
                    f"{self.book.get_bid(0)};{self.book.get_bid_vol(0)};"
                    f"{self.book.get_ask(0)};{self.book.get_ask_vol(0)}")

    def check_last_n_book(self, n=1):
        """
        Check if the order book has at least n levels on both bid and ask sides.

        Args:
            n (int, optional): The number of levels to check. Defaults to 1.

        Returns:
            bool: True if the order book has at least n levels, False otherwise.
        """
        if self.book is None:
            return False
        else:
            if len(self.book.asks) < n or len(self.book.bids) < n:
                return False
        return True

    def get_mid(self):
        """
        Get the mid price of the order book.

        Returns:
            float: The mid price.
        """
        return self.book.get_mid_price()

    def get_book(self):
        """
        Get the order book data.

        Returns:
            OrderBookData: The order book data.
        """
        return self.book

    def get_weightedtop(self):
        """
        Get the weighted top price of the order book.

        Returns:
            float: The weighted top price.
        """
        return self.book.get_weighted_top_price()

    def get_last(self):
        """
        Get the last traded price.

        Returns:
            float: The last traded price.
        """
        return self.last

    def get_price(self, type='close'): #TODO: use dictionary to replace this?
        """
        Get a specific price from the order book.

        Args:
            type (str, optional): The type of price to get. Defaults to 'close'.

        Returns:
            float: The requested price.

        Raises:
            ValueError: If the requested price type is not implemented.
        """
        if type == 'mid':
            return self.book.get_mid_price()
        elif type == 'bid0' or type == 'bid_price0':
            return self.book.get_bid(0)
        elif type == 'ask0' or type == 'ask_price0':
            return self.book.get_ask(0)
        elif type == 'bidSz0' or type == 'bid_vol0':
            return self.book.get_bid_vol(0)
        elif type == 'askSz0' or type == 'ask_vol0':
            return self.book.get_ask_vol(0)
        elif type == 'weightedtop':
            return self.book.get_weighted_top_price()
        else:
            raise ValueError("type not implemented")

    @classmethod
    def from_live_dict(cls, data: dict):
        """
        Create a BookSnapshotData object from a dictionary.

        Args:
            data (dict): The dictionary containing the data.

        Returns:
            BookSnapshotData: The created BookSnapshotData object.
        """
        converted_data = convert_marketdata_to_tickdata(data)
        return cls(
            trade_date=converted_data.trade_date,
            symbol=converted_data.symbol,
            timestamp=converted_data.timestamp,
            volume=converted_data.volume,
            last=converted_data.last,
            book=converted_data.book,
            open=converted_data.open,
            close=converted_data.close,
            high=converted_data.high,
            low=converted_data.low
        )

    def to_dict(self):
        selected_cols = ['bid_price1', 'ask_price1', 'bid_vol1', 'ask_vol1', 'bid_price2', 'ask_price2', 'bid_vol2', 'ask_vol2',
            'bid_price3', 'ask_price3', 'bid_vol3', 'ask_vol3', 'bid_price4', 'ask_price4', 'bid_vol4', 'ask_vol4',
            'bid_price5', 'ask_price5', 'bid_vol5', 'ask_vol5', 'last', 'volume']
        
        result = {}
        
        for i in range(1, 6):
            result[f'bid_price{i}'] = self.book.get_bid(i-1)
            result[f'ask_price{i}'] = self.book.get_ask(i-1)
            result[f'bid_vol{i}'] = self.book.get_bid_vol(i-1)
            result[f'ask_vol{i}'] = self.book.get_ask_vol(i-1)
        
        result['last'] = self.last
        result['volume'] = self.volume
        result['mid'] = (result['bid_price1'] + result['ask_price1']) / 2
        
        # 将所有值转换为浮点数
        for key, value in result.items():
            result[key] = float(value) if value is not None else None
        
        return result
