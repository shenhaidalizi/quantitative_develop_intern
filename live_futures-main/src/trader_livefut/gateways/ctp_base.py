# this file is from github 
import json, datetime, time, logging, os, threading, re
from collections import defaultdict
import ctpwrapper.ApiStructure as CTPStruct
from trader_livefut.configs.settings import FUTURES_LIVE_DATA_PATH
import logging

logger = logging.getLogger(__name__)

MAX_TIMEOUT = 10
FILTER = lambda x: None if x > 1.797e+308 else x

class SpiHelper:
    """
    A helper class for CTP API callbacks and synchronization.

    This class provides methods for managing completion events,
    error handling, and API return code checking.
    """

    def __init__(self):
        """
        Initialize the SpiHelper instance.
        """
        self._event = threading.Event()
        self._error = None

    def resetCompletion(self):
        """
        Reset the completion event and clear any previous errors.
        """
        self._event.clear()
        self._error = None

    def waitCompletion(self, operation_name = ""):
        """
        Wait for the completion of an operation.

        Args:
            operation_name (str): The name of the operation.

        Raises:
            TimeoutError: If the operation times out.
            RuntimeError: If an error occurred during the operation.
        """
        if not self._event.wait(MAX_TIMEOUT):
            raise TimeoutError("%s超时" % operation_name)
        if self._error:
            print(self._error)
            if self._error == "CTP:平昨仓位不足":
                return
            raise RuntimeError(self._error)

    def notifyCompletion(self, error = None):
        """
        Notify the completion of an operation.

        Args:
            error (str, optional): An error message if the operation failed.
        """
        self._error = error
        self._event.set()

    def _cvtApiRetToError(self, ret):
        """
        Convert API return code to error message.

        Args:
            ret (int): API return code.

        Returns:
            str: Error message corresponding to the return code.
        """
        assert(-3 <= ret <= -1)
        return ("网络连接失败", "未处理请求超过许可数", "每秒发送请求数超过许可数")[-ret - 1]

    def checkApiReturn(self, ret):
        """
        Check the return code of an API call.

        Args:
            ret (int): The return code from the API call.

        Raises:
            RuntimeError: If the API call was not successful.
        """
        if ret != 0:
            raise RuntimeError(self._cvtApiRetToError(ret))

    def checkApiReturnInCallback(self, ret):
        """
        Check the return code of an API call within a callback.

        Args:
            ret (int): The return code from the API call.
        """
        if ret != 0:
            self.notifyCompletion(self._cvtApiRetToError(ret))

    def checkRspInfoInCallback(self, info):
        """
        Check the response information in a callback.

        Args:
            info: The response information object.

        Returns:
            bool: True if the response is successful, False otherwise.
        """
        if not info or info.ErrorID == 0:
            return True
        self.notifyCompletion(info.ErrorMsg)
        return False
