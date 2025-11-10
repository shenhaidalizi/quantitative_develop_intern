import os
import logging
from ctpwrapper import ApiStructure as CTPStruct
from .ctp_base import SpiHelper, FILTER
from trader_livefut.configs.settings import FUTURES_LIVE_DATA_PATH
import ctpwrapper as CTP

logger = logging.getLogger(__name__)

class QuoteImpl(SpiHelper, CTP.MdApiPy):
    """
    Implementation of the CTP market data API.
    
    This class handles the connection to the CTP market data server,
    login, subscription to market data, and processing of market data updates.
    """

    def __init__(self, front):
        """
        Initialize the QuoteImpl instance.
        
        Args:
            front (str): The front address of the CTP market data server.
        """
        SpiHelper.__init__(self)
        CTP.MdApiPy.__init__(self)
        self._receiver = None
        self._broker_id = None
        self._user_id = None
        self._password = None
        self._connected = False
        flow_dir = FUTURES_LIVE_DATA_PATH + "md_flow/"
        os.makedirs(flow_dir, exist_ok = True)
        self.Create(flow_dir)
        self.RegisterFront(front)
        self.Init()
    
    def login(self, broker_id, user_id, password):
        """
        Login to the CTP market data server.
        """
        self._broker_id = broker_id
        self._user_id = user_id
        self._password = password
        if self._connected:
            field = CTPStruct.ReqUserLoginField(BrokerID=self._broker_id,
                                                UserID=self._user_id,
                                                Password=self._password)
            self.checkApiReturnInCallback(self.ReqUserLogin(field, 0))
        self.waitCompletion("登录行情会话")

    def OnRspError(self, pRspInfo, nRequestID, bIsLast):
        """
        Callback for error responses.
        
        Args:
            pRspInfo: The error information.
            nRequestID (int): The request ID.
            bIsLast (bool): Indicates if this is the last packet.
        """
        print("OnRspError:")
        print("requestID:", nRequestID)
        print(pRspInfo)
        print(bIsLast)

    def __del__(self):
        """
        Destructor to ensure proper logout from the market data server.
        """
        try:
            if hasattr(self, 'Release'):
                self.Release()
            logger.info("已登出行情服务器...")
        except Exception as e:
            logger.error(f"登出行情服务器时发生错误: {e}")

    def shutdown(self):
        """
        Shutdown the connection to the market data server.
        """
        try:
            if hasattr(self, 'Release'):
                self.Release()
            logger.info("已登出行情服务器...")
        except Exception as e:
            logger.error(f"关闭行情服务器时发生错误: {e}")

    def Release(self):
        """
        Release resources and logout from the market data server.
        """
        try:
            super(QuoteImpl, self).Release()
        except AttributeError:
            logger.warning("Release 方法不存在，可能已经被释放")
        except Exception as e:
            logger.error(f"Release 方法调用失败: {e}")

    def OnFrontConnected(self):
        """
        Callback when connection to the front server is established.
        """
        logger.info("已连接行情服务器...")
        self._connected = True
        if self._broker_id and self._user_id and self._password:
            field = CTPStruct.ReqUserLoginField(BrokerID=self._broker_id,
                                                UserID=self._user_id,
                                                Password=self._password)
            self.checkApiReturnInCallback(self.ReqUserLogin(field, 0))
            self.status = 0
        else:
            logger.info("等待设置行情登录凭据后再登录...")
        
    def OnFrontDisconnected(self, nReason):
        """
        Callback when disconnected from the front server.
        
        Args:
            nReason (int): The reason for disconnection.
        """
        logger.info("已断开行情服务器:{}...".format(nReason))
        print("Md OnFrontDisconnected {0}".format(nReason))
    
    def OnHeartBeatWarning(self, nTimeLapse):
        """
        Callback for heartbeat warning.
        
        Args:
            nTimeLapse (int): Time elapsed since the last received message.
        """
        logger.info('Md OnHeartBeatWarning, time = {0}'.format(nTimeLapse))

    def OnRspUserLogin(self, _, info, req_id, is_last):
        """
        Callback for user login response.
        
        Args:
            _: Unused parameter.
            info: Login response information.
            req_id (int): Request ID.
            is_last (bool): Indicates if this is the last packet.
        """
        assert(req_id == 0)
        assert(is_last)
        if not self.checkRspInfoInCallback(info):
            return
        logger.info("已登录行情会话...")
        self.status = 1
        self.notifyCompletion()

    def setReceiver(self, func):
        """
        Set the receiver function for market data.
        
        Args:
            func: The function to receive market data.
        
        Returns:
            The previous receiver function.
        """
        old_func = self._receiver
        self._receiver = func
        return old_func

    def subscribe(self, codes:list[str]):
        """
        Subscribe to market data for specified instruments.
        
        Args:
            codes (list[str]): List of instrument codes to subscribe to.
        """
        if isinstance(codes, str):
            codes = [codes]
        self.resetCompletion()
        self.checkApiReturn(self.SubscribeMarketData(codes))
        self.waitCompletion("订阅行情")

    def OnRspSubMarketData(self, field, info, _, is_last):
        """
        Callback for market data subscription response.
        
        Args:
            field: Subscription field information.
            info: Response information.
            _: Unused parameter.
            is_last (bool): Indicates if this is the last packet.
        """
        if not self.checkRspInfoInCallback(info):
            assert(is_last)
            return
        logger.info("已订阅<%s>的行情..." % field.InstrumentID)
        if is_last:
            self.notifyCompletion()

    def OnRtnDepthMarketData(self, field):
        """
        Callback for receiving market data updates.
        
        Args:
            field: Market data field containing updated information.
        """
        if not self._receiver:
            return
        self._receiver({"trade_time": field.TradingDay[:4] + '-' + field.TradingDay[4:6] + '-' + field.TradingDay[6:] + " " + field.UpdateTime, "update_sec": int(field.UpdateMillisec), 
                "code": field.InstrumentID, "price": FILTER(field.LastPrice),
                "open": FILTER(field.OpenPrice), "close": FILTER(field.ClosePrice),
                "highest": FILTER(field.HighestPrice), "lowest": FILTER(field.LowestPrice),
                "upper_limit": FILTER(field.UpperLimitPrice),
                "lower_limit": FILTER(field.LowerLimitPrice),
                "settlement": FILTER(field.SettlementPrice), "volume": field.Volume,
                "turnover": field.Turnover, "open_interest": int(field.OpenInterest),
                "pre_close": FILTER(field.PreClosePrice),
                "pre_settlement": FILTER(field.PreSettlementPrice),
                "pre_open_interest": int(field.PreOpenInterest),
                "ask1": (FILTER(field.AskPrice1), field.AskVolume1),
                "bid1": (FILTER(field.BidPrice1), field.BidVolume1),
                "ask2": (FILTER(field.AskPrice2), field.AskVolume2),
                "bid2": (FILTER(field.BidPrice2), field.BidVolume2),
                "ask3": (FILTER(field.AskPrice3), field.AskVolume3),
                "bid3": (FILTER(field.BidPrice3), field.BidVolume3),
                "ask4": (FILTER(field.AskPrice4), field.AskVolume4),
                "bid4": (FILTER(field.BidPrice4), field.BidVolume4),
                "ask5": (FILTER(field.AskPrice5), field.AskVolume5),
                "bid5": (FILTER(field.BidPrice5), field.BidVolume5)})

    def unsubscribe(self, codes):
        """
        Unsubscribe from market data for specified instruments.
        
        Args:
            codes (list[str]): List of instrument codes to unsubscribe from.
        """
        self.resetCompletion()
        self.checkApiReturn(self.UnSubscribeMarketData(codes))
        self.waitCompletion("取消订阅行情")

    def OnRspUnSubMarketData(self, field, info, _, is_last):
        """
        Callback for market data unsubscription response.
        
        Args:
            field: Unsubscription field information.
            info: Response information.
            _: Unused parameter.
            is_last (bool): Indicates if this is the last packet.
        """
        if not self.checkRspInfoInCallback(info):
            assert(is_last)
            return
        logger.info("已取消订阅<%s>的行情..." % field.InstrumentID)
        if is_last:
            self.notifyCompletion()
