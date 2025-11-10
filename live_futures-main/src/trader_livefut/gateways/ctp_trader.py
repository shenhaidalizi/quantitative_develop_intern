import os
import logging
import time
import json
import re
from collections import defaultdict
from ctpwrapper import ApiStructure as CTPStruct
from .ctp_base import SpiHelper, FILTER
import ctpwrapper as CTP
from trader_livefut.configs.settings import FUTURES_LIVE_DATA_PATH

logger = logging.getLogger(__name__)

class TraderImpl(SpiHelper, CTP.TraderApiPy):
    """
    Implementation of the CTP trader API.

    This class handles the connection to the CTP trading server, login,
    order placement, and processing of trading-related updates.
    """

    def __init__(self, front, broker_id, app_id, auth_code, user_id, password):
        """
        Initialize the TraderImpl instance.

        Args:
            front (str): The front address of the CTP trading server.
            broker_id (str): The broker ID.
            app_id (str): The application ID.
            auth_code (str): The authentication code.
            user_id (str): The user ID.
            password (str): The password.
        """
        SpiHelper.__init__(self)
        CTP.TraderApiPy.__init__(self)
        self._last_query_time = 0
        self._broker_id = broker_id
        self._app_id = app_id
        self._auth_code = auth_code
        self._user_id = user_id
        self._password = password
        self._front_id = None
        self._session_id = None
        self._order_action = None
        self._order_ref = 0
        flow_dir = FUTURES_LIVE_DATA_PATH + "td_flow/"
        os.makedirs(flow_dir, exist_ok = True)
        self.Create(flow_dir)
        self.RegisterFront(front)
        self.SubscribePrivateTopic(2)   #THOST_TERT_QUICK
        self.SubscribePublicTopic(2)    #THOST_TERT_QUICK
        self.Init()
        self.waitCompletion("登录交易会话")
        del self._app_id, self._auth_code, self._password
        self._getInstruments()
        self.instruments_option = defaultdict(list)
        self.instruments_future = defaultdict(list)
        self._buildInstrumentsDict()
        self._traded_volume = 0

    def _limitFrequency(self):
        delta = time.time() - self._last_query_time
        if delta < 1:
            time.sleep(1 - delta)
        self._last_query_time = time.time()

    def __del__(self):
        self.Release()
        logger.info("已登出交易服务器...")
    
    def shutdown(self):
        self.Release()
        logger.info("已登出交易服务器...")

    def OnFrontConnected(self):
        logger.info("已连接交易服务器...")
        field = CTPStruct.ReqAuthenticateField(BrokerID = self._broker_id,
                AppID = self._app_id, AuthCode = self._auth_code, UserID = self._user_id)
        self.checkApiReturnInCallback(self.ReqAuthenticate(field, 0))
    
    def OnRspError(self, pRspInfo, nRequestID, bIsLast):
        """
        Callback for error responses.

        Args:
            pRspInfo: Error information.
            nRequestID (int): Request ID.
            bIsLast (bool): Indicates if this is the last packet.
        """
        print("OnRspError:")
        print("requestID:", nRequestID)
        print(pRspInfo)
        print(bIsLast)

    def OnHeartBeatWarning(self, nTimeLapse):
        """
        Callback for heartbeat warning.

        Args:
            nTimeLapse (int): Time elapsed since the last received message.
        """
        logger.info("OnHeartBeatWarning time: ", nTimeLapse)

    def OnFrontDisconnected(self, nReason):
        """
        Callback when disconnected from the front server.

        Args:
            nReason (int): The reason for disconnection.
        """
        logger.info("已断开交易服务器:{}...".format(nReason))
        print("OnFrontDisConnected:", nReason)

    def OnRspAuthenticate(self, _, info, req_id, is_last):
        """
        Callback for authentication response.

        Args:
            _: Unused parameter.
            info: Authentication response information.
            req_id (int): Request ID.
            is_last (bool): Indicates if this is the last packet.
        """
        assert(req_id == 0)
        assert(is_last)
        if not self.checkRspInfoInCallback(info):
            return
        logger.info("已通过交易终端认证...")
        field = CTPStruct.ReqUserLoginField(BrokerID = self._broker_id,
                UserID = self._user_id, Password = self._password)
        self.checkApiReturnInCallback(self.ReqUserLogin(field, 1))

    def OnRspUserLogin(self, field, info, req_id, is_last):
        """
        Callback for user login response.

        Args:
            field: Login response field.
            info: Login response information.
            req_id (int): Request ID.
            is_last (bool): Indicates if this is the last packet.
        """
        assert(req_id == 1)
        assert(is_last)
        if not self.checkRspInfoInCallback(info):
            return
        self._front_id = field.FrontID
        self._session_id = field.SessionID
        logger.info("已登录交易会话...")
        field = CTPStruct.SettlementInfoConfirmField(BrokerID = self._broker_id,
                InvestorID = self._user_id)
        self.checkApiReturnInCallback(self.ReqSettlementInfoConfirm(field, 2))

    def OnRspSettlementInfoConfirm(self, _, info, req_id, is_last):
        """
        Callback for settlement information confirmation response.

        Args:
            _: Unused parameter.
            info: Confirmation response information.
            req_id (int): Request ID.
            is_last (bool): Indicates if this is the last packet.
        """
        assert(req_id == 2)
        assert(is_last)
        if not self.checkRspInfoInCallback(info):
            return
        logger.info("已确认结算单...")
        self.notifyCompletion()

    def _getInstruments(self):
        """
        Retrieve and cache instrument information.
        """
        print("getting instruments")
        file_path = FUTURES_LIVE_DATA_PATH + "instruments.dat"
        now_date = time.strftime("%Y-%m-%d", time.localtime())
        if os.path.exists(file_path):
            fd = open(file_path)
            cached_date = fd.readline()
            if cached_date[: -1] == now_date:
                self._instruments = json.load(fd)
                fd.close()
                logger.info("已加载全部共%d个合约..." % len(self._instruments))
                return
            fd.close()
        self._instruments = {}
        self.resetCompletion()
        self._limitFrequency()
        self.checkApiReturn(self.ReqQryInstrument(CTPStruct.QryInstrumentField(), 3))
        last_count = 0
        while True:
            try:
                self.waitCompletion("获取所有合约")
                break
            except TimeoutError as e:
                count = len(self._instruments)
                if count == last_count:
                    raise e
                logger.info("已获取%d个合约..." % count)
                last_count = count
        fd = open(file_path, "w")
        fd.write(now_date + "\n")
        json.dump(self._instruments, fd, ensure_ascii=False, indent=4)
        fd.close()
        logger.info("已保存全部共%d个合约..." % len(self._instruments))
        print("saved instruments")
    def _buildInstrumentsDict(self):
        """
        Build dictionaries of instruments categorized by type and exchange.
        """
        for symbol in self._instruments:
            instrument = self._instruments[symbol]
            instrument["symbol"] = symbol
            if re.search(r"[\d\-][CP][\d\-]", symbol):
                try:
                    self.instruments_option[re.findall(r"([A-Za-z]{2,}\d{2,})", symbol)[0]].append(instrument)
                except:
                    self.instruments_option[re.findall(r'(^[A-Za-z]\d+)', symbol)[0]].append(instrument)
            else:
                self.instruments_future[instrument['exchange']].append(instrument)

    def OnRspQryInstrument(self, field, info, req_id, is_last):
        assert(req_id == 3)
        if not self.checkRspInfoInCallback(info):
            assert(is_last)
            return
        if field:
            if field.OptionsType == '1':        #THOST_FTDC_CP_CallOptions
                option_type = "call"
            elif field.OptionsType == '2':      #THOST_FTDC_CP_PutOptions
                option_type = "put"
            else:
                option_type = None
            expire_date = None if field.ExpireDate == "" else       \
                    time.strftime("%Y-%m-%d", time.strptime(field.ExpireDate, "%Y%m%d"))
            self._instruments[field.InstrumentID] = {"name": field.InstrumentName,
                    "exchange": field.ExchangeID, "multiple": field.VolumeMultiple,
                    "price_tick": field.PriceTick, "expire_date": expire_date,
                    "long_margin_ratio": FILTER(field.LongMarginRatio),
                    "short_margin_ratio": FILTER(field.ShortMarginRatio),
                    "option_type": option_type, "strike_price": FILTER(field.StrikePrice),
                    "is_trading": bool(field.IsTrading)}
        if is_last:
            logger.info("已获取全部共%d个合约..." % len(self._instruments))
            self.notifyCompletion()

    def getAccount(self):
        """
        Get the account information.

        Returns:
            dict: A dictionary containing account information.
        """
        #THOST_FTDC_BZTP_Future = 1
        field = CTPStruct.QryTradingAccountField(BrokerID = self._broker_id,
                InvestorID = self._user_id, CurrencyID = "CNY", BizType = '1')
        self.resetCompletion()
        self._limitFrequency()
        self.checkApiReturn(self.ReqQryTradingAccount(field, 8))
        self.waitCompletion("获取资金账户")
        return self._account

    def OnRspQryTradingAccount(self, field, info, req_id, is_last):
        assert(req_id == 8)
        assert(is_last)
        if not self.checkRspInfoInCallback(info):
            return
        self._account = {"balance": field.Balance, "margin": field.CurrMargin,
                "available": field.Available}
        logger.info("已获取资金账户...")
        self.notifyCompletion()

    def getOrders(self):
        """
        Get all orders for the current trading day.

        Returns:
            dict: A dictionary of all orders.
        """
        self._orders = {}
        field = CTPStruct.QryOrderField(BrokerID = self._broker_id,
                InvestorID = self._user_id)
        self.resetCompletion()
        self._limitFrequency()
        self.checkApiReturn(self.ReqQryOrder(field, 4))
        self.waitCompletion("获取所有报单")
        return self._orders

    def _gotOrder(self, order):
        if len(order.OrderSysID) == 0:
            return
        oid = "%s@%s" % (order.OrderSysID, order.InstrumentID)
        (direction, volume) = (int(order.Direction), order.VolumeTotalOriginal)
        assert(direction in (0, 1))
        if order.CombOffsetFlag == '1':     #THOST_FTDC_OFEN_Close
            direction = 1 - direction
            volume = -volume
        direction = "short" if direction else "long"
        #THOST_FTDC_OST_AllTraded = 0, THOST_FTDC_OST_Canceled = 5
        is_active = order.OrderStatus not in ('0', '5')
        assert(oid not in self._orders)
        self._orders[oid] = {"code": order.InstrumentID, "direction": direction,
                "price": order.LimitPrice, "volume": volume,
                "volume_traded": order.VolumeTraded, "is_active": is_active}

    def OnRspQryOrder(self, field, info, req_id, is_last):
        assert(req_id == 4)
        if not self.checkRspInfoInCallback(info):
            assert(is_last)
            return
        if field:
            self._gotOrder(field)
        if is_last:
            logger.info("已获取所有报单...")
            self.notifyCompletion()

    def getPositions(self):
        """
        Get current positions.

        Returns:
            list: A list of current positions.
        """
        self._positions = []
        field = CTPStruct.QryInvestorPositionField(BrokerID = self._broker_id,
                InvestorID = self._user_id)
        self.resetCompletion()
        self._limitFrequency()
        self.checkApiReturn(self.ReqQryInvestorPosition(field, 5))
        self.waitCompletion("获取所有持仓")
        return self._positions

    def _gotPosition(self, position):
        code = position.InstrumentID
        if position.PosiDirection == '2':       #THOST_FTDC_PD_Long
            direction = "long"
        elif position.PosiDirection == '3':     #THOST_FTDC_PD_Short
            direction = "short"
        else:
            return
        volume = position.Position
        if volume == 0:
            return
        self._positions.append({"code": code, "direction": direction,
                    "volume": volume, "margin": position.UseMargin,
                    "cost": position.OpenCost})

    def OnRspQryInvestorPosition(self, field, info, req_id, is_last):
        assert(req_id == 5)
        if not self.checkRspInfoInCallback(info):
            assert(is_last)
            return
        if field:
            self._gotPosition(field)
        if is_last:
            # logger.debug("已获取所有持仓...")
            self.notifyCompletion()

    def OnRtnOrder(self, order):
        if self._order_action:
            if self._order_action(order):
                self._order_action = None

    def _handleNewOrder(self, order):
        order_ref = None if len(order.OrderRef) == 0 else int(order.OrderRef)
        # logging.debug(order)
        if (order.FrontID, order.SessionID, order_ref) !=               \
                (self._front_id, self._session_id, self._order_ref):
            return False
        if order.OrderStatus == 'a':                #THOST_FTDC_OST_Unknown
            return False
        if order.OrderSubmitStatus == '4':          #THOST_FTDC_OSS_InsertRejected
            self.notifyCompletion(order.StatusMsg)
            return True
        if order.TimeCondition == '1':              #THOST_FTDC_TC_IOC
            #THOST_FTDC_OST_AllTraded = 0, THOST_FTDC_OST_Canceled = 5
            if order.OrderStatus in ('0', '5'):
                logger.info("已执行IOC单，成交量：%d" % order.VolumeTraded)
                self._traded_volume = order.VolumeTraded
                self.notifyCompletion()
                return True
        else:
            assert(order.TimeCondition == '3')      #THOST_FTDC_TC_GFD
            if order.OrderSubmitStatus == '3':      #THOST_FTDC_OSS_Accepted
                #THOST_FTDC_OST_AllTraded = 0, THOST_FTDC_OST_PartTradedQueueing = 1
                #THOST_FTDC_OST_PartTradedNotQueueing = 2, THOST_FTDC_OST_NoTradeQueueing = 3
                #THOST_FTDC_OST_NoTradeNotQueueing = 4, THOST_FTDC_OST_Canceled = 5
                assert(order.OrderStatus in ('0', '1', '2', '3', '4', '5'))
                assert(len(order.OrderSysID) != 0)
                self._order_id = "%s@%s" % (order.OrderSysID, order.InstrumentID)
                logger.info("已提交限价单（单号：<%s>）" % self._order_id)
                self.notifyCompletion()
                return True
        return False

    def _order(self, code, direction, volume, price, min_volume, flat_yesterday=False):
        """
        Internal method to place an order.

        Args:
            code (str): Instrument code.
            direction (str): Order direction ('long' or 'short').
            volume (int): Order volume.
            price (float): Order price.
            min_volume (int): Minimum volume to be filled.
            flat_yesterday (bool): Whether to close yesterday's position.

        Raises:
            ValueError: If invalid parameters are provided.
        """
        if code not in self._instruments:
            raise ValueError("合约<%s>不存在！" % code)
        exchange = self._instruments[code]["exchange"]
        if direction == "long":
            direction = 0               #THOST_FTDC_D_Buy
        elif direction == "short":
            direction = 1               #THOST_FTDC_D_Sell
        else:
            raise ValueError("错误的买卖方向<%s>" % direction)
        if volume != int(volume) or volume == 0:
            raise ValueError("交易数量<%s>必须是非零整数" % volume)
        if volume > 0:
            offset_flag = '0'           #THOST_FTDC_OF_Open
        elif flat_yesterday:
            offset_flag = '4'           #THOST_FTDC_OF_CloseYesterday 平昨
            volume = -volume
            direction = 1 - direction
        else:
            offset_flag = '3'           #THOST_FTDC_OF_CloseToday 平今
            volume = -volume
            direction = 1 - direction
        direction = str(direction)
        #Market Price Order
        if price == 0:
            if exchange == "CFFEX":
                price_type = 'G'        #THOST_FTDC_OPT_FiveLevelPrice
            else:
                price_type = '1'        #THOST_FTDC_OPT_AnyPrice
            #THOST_FTDC_TC_IOC, THOST_FTDC_VC_AV
            (time_cond, volume_cond) = ('1', '1')
        #Limit Price Order
        elif min_volume == 0:
            #THOST_FTDC_OPT_LimitPrice, THOST_FTDC_TC_GFD, THOST_FTDC_VC_AV
            (price_type, time_cond, volume_cond) = ('2', '3', '1')
        #FAK Order
        else:
            min_volume = abs(min_volume)
            if min_volume > volume:
                raise ValueError("最小成交量<%s>不能超过交易数量<%s>" % (min_volume, volume))
            #THOST_FTDC_OPT_LimitPrice, THOST_FTDC_TC_IOC, THOST_FTDC_VC_MV
            (price_type, time_cond, volume_cond) = ('2', '1', '2')
        self._order_ref += 1
        self._order_action = self._handleNewOrder
        field = CTPStruct.InputOrderField(BrokerID = self._broker_id,
                InvestorID = self._user_id, ExchangeID = exchange, InstrumentID = code,
                Direction = direction, CombOffsetFlag = offset_flag,
                TimeCondition = time_cond, VolumeCondition = volume_cond,
                OrderPriceType = price_type, LimitPrice = price,
                VolumeTotalOriginal = volume, MinVolume = min_volume,
                CombHedgeFlag = '1',            #THOST_FTDC_HF_Speculation
                ContingentCondition = '1',      #THOST_FTDC_CC_Immediately
                ForceCloseReason = '0',         #THOST_FTDC_FCC_NotForceClose
                OrderRef = "%12d" % self._order_ref)
        self.resetCompletion()
        self.checkApiReturn(self.ReqOrderInsert(field, 6))
        self.waitCompletion("录入报单")
    def OnRspOrderInsert(self, field, info, req_id, is_last):
        """
        Callback for order insertion response.

        Args:
            field: Order insertion response field.
            info: Response information.
            req_id (int): Request ID.
            is_last (bool): Indicates if this is the last packet.
        """
        assert(req_id == 6)
        assert(is_last)
        logger.info("OnRspOrderInsert 已提交限价单...")
        self.OnErrRtnOrderInsert(field, info)

    def OnErrRtnOrderInsert(self, _, info):
        """
        Callback for order insertion error.

        Args:
            _: Unused parameter.
            info: Error information.
        """
        success = self.checkRspInfoInCallback(info)
        logger.info(" OnErrRtnOrderInsert 已提交限价单失败" if success else "已提交限价单成功")
        assert(not success)

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
        self._order(code, direction, volume, 0, 0, flat_yesterday=flat_yesterday)
        return self._traded_volume

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
        assert(price > 0)
        self._order(code, direction, volume, price, 1 if min_volume == 0 else min_volume, flat_yesterday=flat_yesterday)
        return self._traded_volume

    # def orderFOK(self, code, direction, volume, price):
    #     return self.orderFAK(code, direction, volume, price, volume)

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
        assert(price > 0)
        self._order(code, direction, volume, price, 0, flat_yesterday=flat_yesterday)
        return self._order_id

    def _handleDeleteOrder(self, order):
        """
        Handle the response to an order deletion request.

        Args:
            order: Order information.

        Returns:
            bool: True if the order deletion is complete, False otherwise.
        """
        oid = "%s@%s" % (order.OrderSysID, order.InstrumentID)
        if oid != self._order_id:
            return False
        logging.debug(order)
        if order.OrderSubmitStatus == '5':      #THOST_FTDC_OSS_CancelRejected
            self.notifyCompletion(order.StatusMsg)
            return True
        #THOST_FTDC_OST_AllTraded = 0, THOST_FTDC_OST_Canceled = 5
        if order.OrderStatus in ('0', '5'):
            logger.info("已撤销限价单，单号：<%s>" % self._order_id)
            self.notifyCompletion()
            return True
        return False

    def deleteOrder(self, order_id):
        """
        Cancel an existing order.

        Args:
            order_id (str): The ID of the order to be cancelled.
        """
        items = order_id.split("@")
        if len(items) != 2:
            raise ValueError("订单号<%s>格式错误" % order_id)
        (sys_id, code) = items
        if code not in self._instruments:
            raise ValueError("订单号<%s>中的合约号<%s>不存在" % (order_id, code))
        field = CTPStruct.InputOrderActionField(BrokerID = self._broker_id,
                InvestorID = self._user_id, UserID = self._user_id,
                ActionFlag = '0',               #THOST_FTDC_AF_Delete
                ExchangeID = self._instruments[code]["exchange"],
                InstrumentID = code, OrderSysID = sys_id)
        self.resetCompletion()
        self._order_id = order_id
        self._order_action = self._handleDeleteOrder
        self.checkApiReturn(self.ReqOrderAction(field, 7))
        self.waitCompletion("撤销报单")

    def OnRspOrderAction(self, field, info, req_id, is_last):
        assert(req_id == 7)
        assert(is_last)
        logger.info("OnRspOrderAction {info}, {req_id}")
        self.OnErrRtnOrderAction(field, info)

    def OnErrRtnOrderAction(self, _, info):
        success = self.checkRspInfoInCallback(info)
        logger.info("OnErrRtnOrderAction {info}")
        assert(not success)

    def setOrderCallback(self, callback):
        """
        Set a callback function for order updates.

        Args:
            callback (function): The callback function to handle order updates.
        """
        self._order_callback = callback

    def OnRtnOrder(self, order):
        if hasattr(self, '_order_callback'):
            self._order_callback(order)
        if self._order_action:
            if self._order_action(order):
                self._order_action = None


