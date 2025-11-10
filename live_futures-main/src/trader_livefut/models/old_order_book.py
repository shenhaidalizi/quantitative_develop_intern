import numpy as np
import math

class OldOrderBook:
    """
    A class representing order book data.
    """

    def __init__(self, bid_list, ask_list, bid_vol_list, ask_vol_list, symbol, timestamp):
        """
        Initialize the OrderBookData object.

        Args:
            bid_list (list): List of bid prices.
            ask_list (list): List of ask prices.
            bid_vol_list (list): List of bid volumes.
            ask_vol_list (list): List of ask volumes.
            symbol (str): The trading symbol.
            timestamp: The timestamp of the order book data.
        """
        self.symbol = symbol
        self.timestamp = timestamp
        self.bids, self.bid_vols = self._get_bid_info(bid_list, bid_vol_list)
        self.asks, self.ask_vols = self._get_ask_info(ask_list, ask_vol_list)
    
    def check_last_n_book(self, n=1):
        """
        Check if the order book has at least n levels on both bid and ask sides.

        Args:
            n (int, optional): The number of levels to check. Defaults to 1.

        Returns:
            bool: True if the order book has at least n levels, False otherwise.
        """
        if len(self.asks) < n or len(self.bids) < n:
            return False
        return True

    def get_bid(self, index):
        """
        Get the bid price at a specific index.

        Args:
            index (int): The index of the bid price.

        Returns:
            float: The bid price at the specified index, or np.nan if not available.
        """
        if index < len(self.bids):
            return self.bids[index]
        else:
            return np.nan
    
    def get_ask(self, index):
        """
        Get the ask price at a specific index.

        Args:
            index (int): The index of the ask price.

        Returns:
            float: The ask price at the specified index, or np.nan if not available.
        """
        if index < len(self.asks):
            return self.asks[index]
        else:
            return np.nan
    
    def get_bid_vol(self, index):
        """
        Get the bid volume at a specific index.

        Args:
            index (int): The index of the bid volume.

        Returns:
            int: The bid volume at the specified index, or np.nan if not available.
        """
        if index < len(self.bid_vols):
            return self.bid_vols[index]
        else:
            return np.nan
    
    def get_ask_vol(self, index):
        """
        Get the ask volume at a specific index.

        Args:
            index (int): The index of the ask volume.

        Returns:
            int: The ask volume at the specified index, or np.nan if not available.
        """
        if index < len(self.ask_vols):
            return self.ask_vols[index]
        else:
            return np.nan
    
    def _get_bid_info(self, bid_list, bid_vol_list):
        bids = []
        bid_vols = []
        for bid, bid_vol in zip(bid_list, bid_vol_list):
            if bid is None or bid_vol is None:
                break
            bid = float(bid)
            bid_vol = int(float(bid_vol))
            if math.isnan(bid) or math.isnan(bid_vol):
                break
            bids.append(bid)
            bid_vols.append(bid_vol)
        return bids, bid_vols

    def _get_ask_info(self, ask_list, ask_vol_list):
        asks = []
        ask_vols = []
        for ask, ask_vol in zip(ask_list, ask_vol_list):
            if ask is None or ask_vol is None:
                break
            ask = float(ask)
            ask_vol = int(float(ask_vol))
            if math.isnan(ask) or math.isnan(ask_vol):
                break
            asks.append(ask)
            ask_vols.append(ask_vol)
        return asks, ask_vols

    def get_mid_price(self):
        """
        Calculate the mid price of the order book.

        Returns:
            float: The mid price, or np.nan if not available.
        """
        if len(self.bid_vols) == 0 or len(self.ask_vols) == 0:
            return np.nan
        else:
            return (self.bids[0] + self.asks[0]) / 2

    def get_weighted_top_price(self):
        """
        Calculate the weighted top price of the order book.

        Returns:
            float: The weighted top price, or np.nan if not available.
        """
        if len(self.bid_vols) == 0 or len(self.ask_vols) == 0:
            return np.nan
        else:
            return (self.bid_vols[0] * self.asks[0] + self.ask_vols[0] * self.bids[0]) / (self.bid_vols[0] + self.ask_vols[0])

    def get_weighted_bid_price(self, n=1):
        """
        Calculate the weighted bid price of the order book.

        Args:
            n (int, optional): The number of levels to consider. Defaults to 1.

        Returns:
            float: The weighted bid price, or np.nan if not available.
        """
        if not self.check_last_n_book(n):
            return np.nan
        else:
            return np.average(self.bids[:n], weights=self.bid_vols[:n])
    
    def get_weighted_ask_price(self,n=1):
        """
        Calculate the weighted ask price of the order book.

        Args:
            n (int, optional): The number of levels to consider. Defaults to 1.

        Returns:
            float: The weighted ask price, or np.nan if not available.
        """
        if not self.check_last_n_book(n):
            return np.nan
        else:
            return np.average(self.asks[:n], weights=self.ask_vols[:n])

    def get_weight_top_n_prices(self, n=1):
        """
        Calculate the weighted top n prices of the order book.

        Args:
            n (int, optional): The number of levels to consider. Defaults to 1.

        Returns:
            float: The weighted top n prices, or np.nan if not available.
        """
        if not self.check_last_n_book(n):
            return np.nan
        val = (np.dot(self.bid_vols[:n], self.asks[:n]) + np.dot(self.ask_vols[:n], self.bids[:n])) / np.sum(self.ask_vols[:n] + self.bid_vols[:n])
        return val

    def get_weight_top_n_prices_sum_first(self, n=1):
        """
        Calculate the weighted top n prices of the order book, summing first.

        Args:
            n (int, optional): The number of levels to consider. Defaults to 1.

        Returns:
            float: The weighted top n prices, or np.nan if not available.
        """
        weighted_bid = self.get_weighted_bid_price(n=n)
        weighted_ask = self.get_weighted_ask_price(n=n)
        bid_vol_sum = np.sum(self.bid_vols[:n])
        ask_vol_sum = np.sum(self.ask_vols[:n])
        if bid_vol_sum == 0 or ask_vol_sum == 0:
            return np.nan
        return (weighted_bid * ask_vol_sum + weighted_ask * bid_vol_sum) / (bid_vol_sum + ask_vol_sum)


    def __str__(self):
        """
        Get a string representation of the OrderBookData.

        Returns:
            str: A string representation of the object.
        """
        return f"bids:{self.bids};{self.bid_vols};\nasks:{self.asks};{self.ask_vols}"