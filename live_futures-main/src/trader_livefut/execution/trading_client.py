import getpass
import json
import logging
import os
from typing import List, Optional

from ..gateways.ctp_client import Client as CtpClient

logger = logging.getLogger(__name__)

class TradingClient:
    """
    A high-level client for futures trading, providing a simplified interface
    for order execution, account queries, and market data subscriptions.

    This client abstracts the complexities of the underlying CTP gateway.
    """

    def __init__(self, config_path: str, env: str = "sim", password: Optional[str] = None):
        """
        Initializes the TradingClient.

        Args:
            config_path (str): Path to the JSON configuration file containing
                               broker connection details.
            env (str): The environment to connect to (e.g., "sim", "prod").
                       This must correspond to a key in the config file.
        """
        self.client: CtpClient = None
        self._config = self._load_config(config_path, env)
        self._is_logged_in = False
        self._is_logged_in_md = False
        self._is_logged_in_td = False
        self._password = password

    def _load_config(self, config_path: str, env: str) -> dict:
        """Loads connection configuration from a JSON file."""
        try:
            with open(config_path, 'r') as f:
                full_config = json.load(f)
            return full_config[env]
        except (FileNotFoundError, KeyError) as e:
            logger.error(f"Failed to load configuration for env '{env}': {e}")
            raise

    def login(self, mode: str = "both"):
        """
        Logs into the trading and/or market data servers.
        mode: "both" | "md" | "td"
        """
        if self._is_logged_in:
            logger.warning("Already logged in.")
            return

        logger.info(f"Logging in with mode '{mode}'...")

        # Determine password based on mode
        password = self._password or self._config.get("password") or os.getenv("CTP_PASSWORD")

        if mode in ("td", "both"):
            if not password:
                password = getpass.getpass(
                    f"Please enter password for user {self._config['user']}: "
                )
            if not password:
                raise ValueError("A password is required for 'td' or 'both' login mode.")
        elif mode == "md":
            password = password or ""  # Default to empty string for md if no password is provided
        else:
            raise ValueError(f"Unknown login mode: '{mode}'")

        try:
            self.client = CtpClient(
                md_front=self._config["market_front"],
                td_front=self._config["trade_front"],
                broker_id=self._config["broker"],
                app_id=self._config["app"],
                auth_code=self._config["auth"],
                user_id=self._config["user"],
                password=password
            )
            self.client.login(mode=mode)
            self._is_logged_in = True
            self._is_logged_in_md = mode in ("md", "both")
            self._is_logged_in_td = mode in ("td", "both")
            logger.info("Login successful.")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            self.client = None
            self._is_logged_in = False
            self._is_logged_in_md = False
            self._is_logged_in_td = False
            raise

    def logout(self):
        """Logs out from the trading and market data servers."""
        if not self._is_logged_in or not self.client:
            logger.warning("Not logged in.")
            return

        logger.info("Logging out...")
        try:
            self.client.logout()
            self._is_logged_in = False
            logger.info("Logout successful.")
        except Exception as e:
            logger.error(f"Logout failed: {e}")
        finally:
            self.client = None

    def _ensure_logged_in_md(self):
        if not self._is_logged_in or not self.client or not self._is_logged_in_md:
            raise RuntimeError("Market data is not logged in.")

    def _ensure_logged_in_td(self):
        if not self._is_logged_in or not self.client or not self._is_logged_in_td:
            raise RuntimeError("Trading is not logged in.")

    def __enter__(self):
        """Context manager entry."""
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.logout()

    def _ensure_logged_in(self):
        """Checks if the client is logged in, raises RuntimeError otherwise."""
        if not self._is_logged_in or not self.client:
            raise RuntimeError("Client is not logged in.")

    # --- Account and Position Queries ---

    def get_account(self) -> dict:
        """Retrieves the current trading account status."""
        self._ensure_logged_in_td()
        return self.client.getAccount()

    def get_positions(self) -> list:
        """Retrieves all current positions."""
        self._ensure_logged_in_td()
        return self.client.getPositions()

    def get_orders(self) -> dict:
        """Retrieves all orders for the current trading day."""
        self._ensure_logged_in_td()
        return self.client.getOrders()

    # --- Market Data ---

    def subscribe(self, symbols: List[str]):
        """Subscribes to market data for a list of symbols."""
        self._ensure_logged_in_md()
        logger.info(f"Subscribing to market data for: {symbols}")
        self.client.subscribe(symbols)

    def unsubscribe(self, symbols: List[str]):
        """Unsubscribes from market data for a list of symbols."""
        self._ensure_logged_in_md()
        logger.info(f"Unsubscribing from market data for: {symbols}")
        self.client.unsubscribe(symbols)

    def set_market_data_callback(self, callback):
        """
        Sets the callback function for processing incoming market data ticks.

        Args:
            callback (callable): A function that takes one argument (the tick data dict).
        """
        self._ensure_logged_in_md()
        self.client.setReceiver(callback)

    # --- Order Execution and Management ---

    def place_order(self, symbol: str, direction: str, volume: int, price: float,
                    order_type: str = "LIMIT", min_volume: int = 0,
                    flat_yesterday: bool = False) -> str:
        """
        Places an order.

        Args:
            symbol (str): The instrument code (e.g., "IM2506").
            direction (str): "long" or "short".
            volume (int): The order volume. Positive for opening, negative for closing.
            price (float): The order price.
            order_type (str): "LIMIT" (for DAY orders) or "FAK".
            min_volume (int): Minimum volume for FAK orders.
            flat_yesterday (bool): Flag to close yesterday's position.

        Returns:
            str: The order ID for LIMIT orders.
        """
        self._ensure_logged_in_td()
        logger.info(f"Placing order: {order_type} {symbol} {direction} {volume} @ {price}")

        if order_type.upper() == "LIMIT":
            return self.client.orderLimit(code=symbol, direction=direction,
                                          volume=volume, price=price,
                                          flat_yesterday=flat_yesterday)
        elif order_type.upper() == "FAK":
            return self.client.orderFAK(code=symbol, direction=direction,
                                        volume=volume, price=price,
                                        min_volume=min_volume,
                                        flat_yesterday=flat_yesterday)
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

    def cancel_order(self, order_id: str):
        """Cancels a specific order by its ID."""
        self._ensure_logged_in_td()
        logger.info(f"Cancelling order: {order_id}")
        self.client.deleteOrder(order_id)

    def cancel_all_orders(self):
        """Cancels all active (non-filled, non-cancelled) orders."""
        self._ensure_logged_in_td()
        logger.info("Cancelling all active orders...")
        orders = self.get_orders()
        for order_id, order_details in orders.items():
            if order_details.get("is_active", False):
                try:
                    self.cancel_order(order_id)
                    logger.info(f"Cancelled order {order_id}.")
                except Exception as e:
                    logger.error(f"Failed to cancel order {order_id}: {e}")
