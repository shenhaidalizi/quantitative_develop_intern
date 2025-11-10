# 修改文件：/home/ubuntu/TradeNew/live/live_futures/src/trader_livefut/utils/utils_gen.py

import pandas as pd

def pdtime2int(timestamp: pd.Timestamp, unit: str = 's') -> int:
    """Convert pandas timestamp to int timestamp"""
    # Ensure the timestamp is localized to UTC before conversion
    timestamp = timestamp.tz_localize('UTC') if timestamp.tz is None else timestamp.tz_convert('UTC')
    if unit == 's':
        return int(timestamp.value / 1000000000)
    elif unit == 'ms':
        return int(timestamp.value / 1000000)
    else:
        raise ValueError("unit not implemented")


def get_utc_timestamp(trade_date, unit='s'):
    """
    Convert the provided trade_date (or timestamp) to UTC timestamp.
    """
    if isinstance(trade_date, str):
        ts = pd.Timestamp(trade_date)
    elif isinstance(trade_date, pd.Timestamp):
        ts = trade_date
    else:
        raise TypeError('trade_date must be a str or pd.Timestamp')

    if ts.tzinfo is None:
        ts = ts.tz_localize('Asia/Shanghai')

    ts_utc = ts.tz_convert('UTC')

    if unit == 's':
        return int(ts_utc.timestamp())
    elif unit == 'ms':
        return int(ts_utc.timestamp() * 1e3)
    else:
        raise ValueError(f'Unit {unit} not supported')
