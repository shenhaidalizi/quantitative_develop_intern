import argparse
import time
import logging
from pathlib import Path
from trader_livefut.execution.trading_client import TradingClient
from trader_livefut.models.bookSnapshotData import BookSnapshotData
from trader_livefut.utils.utils_marketdate import convert_marketdata_to_tickdata
from trader_livefut.utils.utils_logging import setRootLogger

# --- Configuration ---
project_root = Path(__file__).resolve().parent
CONFIG_PATH = project_root / 'brokers.json'

TRADING_SYMBOL = "IM2509"

class ManualTrader:
    """
    A class to perform manual trading operations for futures,
    replicating the functionality of the original script.
    """
    def __init__(self, env: str):
        self.client = TradingClient(config_path=str(CONFIG_PATH), env=env)
        self.book: BookSnapshotData = None
        self.client.login()

        # Set up a market data handler
        self.client.set_market_data_callback(self._update_book)

    def _update_book(self, market_data_dict: dict):
        """Callback function to process and store the latest market data."""
        self.book = convert_marketdata_to_tickdata(market_data_dict)
        print(f"Book Updated: {self.book}")

    def print_assets(self):
        """Prints the current account assets and positions."""
        print("\n--- Account Assets ---")
        print(self.client.get_account())
        print("\n--- Positions ---")
        print(self.client.get_positions())
        print("\n--- Active Orders ---")
        print(self.client.get_orders())


    def subscribe_and_wait(self, symbol: str, wait_time: int = 3):
        """Subscribes to a symbol and waits for the book to update."""
        print(f"\nSubscribing to {symbol} and waiting for {wait_time}s...")
        self.client.subscribe([symbol])
        time.sleep(wait_time)
        if self.book is None:
            raise RuntimeError("Failed to receive market data after subscription.")
        print("Subscription successful, book is live.")

    def day_ask1(self, symbol: str, volume: int = 1):
        """Places a short DAY/LIMIT order at the best ask price."""
        self.subscribe_and_wait(symbol)
        
        price = self.book.book.asks[0].price
        print(f"\nPlacing DAY SHORT order for {volume} of {symbol} at ask1: {price}")
        self.client.place_order(symbol, "short", volume, price, order_type="LIMIT")
        self.print_assets()

    def day_bid1(self, symbol: str, volume: int = 1):
        """Places a long DAY/LIMIT order at the best bid price."""
        self.subscribe_and_wait(symbol)
        
        price = self.book.book.bids[0].price
        print(f"\nPlacing DAY LONG order for {volume} of {symbol} at bid1: {price}")
        self.client.place_order(symbol, "long", volume, price, order_type="LIMIT")
        self.print_assets()

    def flat_all_positions_aggressively(self):
        """Flats all positions using aggressive FAK orders."""
        positions = self.client.get_positions()
        if not positions:
            print("\nNo positions to flat.")
            return

        print("\n--- Aggressively Flatting All Positions ---")
        symbols = list(set([p['code'] for p in positions]))
        self.subscribe_and_wait(symbols, wait_time=5)

        for pos in positions:
            symbol = pos['code']
            volume = pos['volume']
            
            if pos['direction'] == 'long':
                # To flat a long position, we place a short order
                price = self.book.book.bids[0].price # Hit the bid
                print(f"Flatting LONG {volume} of {symbol} at {price}")
                self.client.place_order(symbol, "short", -volume, price, order_type="FAK")

            elif pos['direction'] == 'short':
                # To flat a short position, we place a long order
                price = self.book.book.asks[0].price # Take the ask
                print(f"Flatting SHORT {volume} of {symbol} at {price}")
                self.client.place_order(symbol, "long", -volume, price, order_type="FAK")
            
            time.sleep(1) # Small delay between closing orders

        print("\n--- Assets after flatting ---")
        self.print_assets()

    def cleanup(self):
        """Unsubscribe and logout."""
        print("\nCleaning up...")
        try:
            self.client.unsubscribe([TRADING_SYMBOL])
        except Exception as e:
            print(f"Could not unsubscribe: {e}")
        self.client.logout()
        print("Cleanup complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual Futures Trader")
    parser.add_argument("-e", "--env", type=str, default="simnow", 
                        help="Environment to use (e.g., 'simnow' or 'zxjt')")
    args = parser.parse_args()

    # Setup logging
    today_date = time.strftime("%Y%m%d")
    setRootLogger(log_filename=f"manual_trader_{today_date}.log", output_console=True)

    trader = None
    try:
        trader = ManualTrader(env=args.env)
        
        # --- Example Usage ---
        # Uncomment the actions you want to perform
        
        trader.print_assets()
        trader.subscribe_and_wait(symbol=TRADING_SYMBOL)

        # Place a short order
        # trader.day_ask1(TRADING_SYMBOL, volume=1)
        # time.sleep(10) # Wait 10 seconds to see if it fills
        # trader.client.cancel_all_orders()

        # Place a long order
        # trader.day_bid1(TRADING_SYMBOL, volume=1)
        # time.sleep(10)
        # trader.client.cancel_all_orders()

        # Flat all positions
        # trader.flat_all_positions_aggressively()

        # trader.print_assets()

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
    finally:
        if trader:
            trader.cleanup()
