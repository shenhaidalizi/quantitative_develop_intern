from .ctp_quote import QuoteImpl
from .ctp_trader import TraderImpl
import logging

logger = logging.getLogger(__name__)

class Client:
    """
    A client class for interacting with CTP (Comprehensive Transaction Platform) for futures trading.
    
    This class provides methods for logging in, subscribing to market data,
    placing orders, and querying account information.
    """

    def __init__(self, md_front, td_front, broker_id, app_id, auth_code, user_id, password):
        """
        Initialize the Client instance.

        Args:
            md_front (str): Market data front address.
            td_front (str): Trading front address.
            broker_id (str): Broker ID.
            app_id (str): Application ID.
            auth_code (str): Authentication code.
            user_id (str): User ID.
            password (str): User password.
        """
        self._md = None
        self._td = None
        self.md_front = md_front
        self.td_front = td_front
        self.broker_id = broker_id
        self.app_id = app_id
        self.auth_code = auth_code
        self.user_id = user_id
        self.password = password
    
    def login(self, mode="both"):
        """
        Log in to the market data and/or trading servers.
        mode: "both" | "md" | "td"
        """
        logger.info("Client: 开始登录")
        if mode in ("both", "td"):
            self._td = TraderImpl(self.td_front, self.broker_id, self.app_id, self.auth_code, self.user_id, self.password)
        if mode in ("both", "md"):
            self._md = QuoteImpl(self.md_front)
            self._md.login(self.broker_id, self.user_id, self.password)
        logger.info("Client: 登录完成")
    
    def logout(self):
        """
        Log out from the market data and trading servers.
        """
        '''
        登出
        '''
        if self._md:
            self._md.shutdown()
        if self._td:
            self._td.shutdown()
    
    def setReceiver(self, callback):
        """
        Set the callback function for receiving market data.

        Args:
            callback (function): The callback function to handle market data.

        Returns:
            function: The previous callback function.
        """
        '''
        tick行情处理函数
        '''
        # try:
        #     from hq_func import parse_hq
        # except:
        #TODO: change receiver function
        # parse_hq = lambda x: print(x)
        return self._md.setReceiver(callback)

    def subscribe(self, codes):
        """
        Subscribe to market data for specified instrument codes.

        Args:
            codes (list): List of instrument codes to subscribe to.

        Raises:
            ValueError: If an invalid instrument code is provided.
        """
        if self._td:
            for code in codes:
                if code not in self._td._instruments:
                    raise ValueError("合约<%s>不存在" % code)
        self._md.subscribe(codes)

    def get_instruments_option(self, future=None):
        """
        Get a list of option instruments.

        Args:
            future (str, optional): The underlying future code. If provided, returns options for that future.

        Returns:
            list: List of option instruments.
        """
        '''
        获取期权合约列表，可指定对应的期货代码
        '''
        if future is None:
            return self._td.instruments_option
        return self._td.instruments_option.get(future, None)

    def get_instruments_future(self, exchange=None):
        """
        Get a list of future instruments.

        Args:
            exchange (str, optional): The exchange code. If provided, returns futures for that exchange.

        Returns:
            list: List of future instruments.
        """
        '''
        获取期货合约列表，可指定对应的交易所
        '''
        if exchange is None:
            return self._td.instruments_future
        return self._td.instruments_future[exchange]

    def unsubscribe(self, codes):
        """
        Unsubscribe from market data for specified instrument codes.

        Args:
            codes (list): List of instrument codes to unsubscribe from.
        """
        '''
        取消订阅
        '''
        self._md.unsubscribe(codes)

    def getInstrument(self, code):
        """
        Get detailed information about a specific instrument.

        Args:
            code (str): The instrument code.

        Returns:
            dict: Detailed information about the instrument.

        Raises:
            ValueError: If the instrument code does not exist.
        """
        '''
        获取指定合约详情
        '''
        if code not in self._td._instruments:
            raise ValueError("合约<%s>不存在" % code)
        return self._td._instruments[code].copy()

    def getAccount(self):
        """
        Get account information.

        Returns:
            dict: Account information including balance, margin, and available funds.
        """
        '''
        获取账号资金情况
        '''
        return self._td.getAccount()

    def getOrders(self):
        """
        Get all orders for the current trading day.

        Returns:
            dict: A dictionary of all orders.
        """
        '''
        获取当天订单
        '''
        return self._td.getOrders()

    def getPositions(self):
        """
        Get current positions.

        Returns:
            list: A list of current positions.
        """
        '''
        获取持仓
        '''
        return self._td.getPositions()

    def orderMarket(self, code, direction, volume, flat_yesterday=False):
        """
        Place a market order.

        Args:
            code (str): Instrument code.
            direction (str): Order direction ('long' or 'short').
            volume (int): Order volume.
            flat_yesterday (bool, optional): Whether to close yesterday's position. Defaults to False.

        Returns:
            int: The traded volume.
        """
        '''
        市价下单
        '''
        return self._td.orderMarket(code, direction, volume, flat_yesterday)

    def orderFAK(self, code, direction, volume, price, min_volume, flat_yesterday=False):
        """
        Place a Fill-and-Kill (FAK) order.

        Args:
            code (str): Instrument code.
            direction (str): Order direction ('long' or 'short').
            volume (int): Order volume.
            price (float): Order price.
            min_volume (int): Minimum volume to be filled.
            flat_yesterday (bool, optional): Whether to close yesterday's position. Defaults to False.

        Returns:
            int: The traded volume.
        """
        '''
        FAK下单
        '''
        return self._td.orderFAK(code, direction, volume, price, min_volume, flat_yesterday)

    # def orderFOK(self, code, direction, volume, price):
    #     '''
    #     FOK下单
    #     '''
    #     return self._td.orderFOK(code, direction, volume, price)

    def orderLimit(self, code, direction, volume, price, flat_yesterday=False):
        """
        Place a limit order.

        Args:
            code (str): Instrument code.
            direction (str): Order direction ('long' or 'short').
            volume (int): Order volume.
            price (float): Order price.
            flat_yesterday (bool, optional): Whether to close yesterday's position. Defaults to False.

        Returns:
            str: The order ID.
        """
        '''
        限价单
        '''
        return self._td.orderLimit(code, direction, volume, price, flat_yesterday)

    def deleteOrder(self, order_id):
        """
        Cancel an existing order.

        Args:
            order_id (str): The ID of the order to be cancelled.
        """
        '''
        撤销订单
        '''
        self._td.deleteOrder(order_id)

    def setOrderCallback(self, callback):
        """
        Set a callback function for order updates.

        Args:
            callback (function): The callback function to handle order updates.
        """
        '''
        设置订单回调函数
        '''
        self._td.setOrderCallback(callback)
