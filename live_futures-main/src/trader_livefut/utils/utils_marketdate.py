from datetime import datetime, timezone
from trader_livefut.models.old_order_book import OldOrderBook

def convert_marketdata_to_tickdata(marketdata: dict):
    """Converts a raw CTP market data dictionary to a BookSnapshotData object."""
    # 在函数内部进行延迟导入，打破循环依赖

    trade_time_str = marketdata.get("trade_time", "")
    ms = marketdata.get("update_sec", 0)

    try:
        dt_obj = datetime.strptime(trade_time_str, "%Y-%m-%d %H:%M:%S")
        timestamp_s = dt_obj.replace(tzinfo=timezone.utc).timestamp()
        timestamp_ns = int(timestamp_s * 1_000_000_000) + (ms * 1_000_000)
        date_str = trade_time_str[:10]
    except (ValueError, TypeError):
        now = datetime.now(timezone.utc)
        timestamp_ns = int(now.timestamp() * 1_000_000_000)
        date_str = now.strftime('%Y-%m-%d')
    
    from trader_livefut.models.bookSnapshotData import BookSnapshotData
    data = BookSnapshotData(
        symbol=marketdata.get("code", ""),
        trade_date=date_str,
        timestamp=timestamp_ns,
        open=marketdata.get("open"),
        close=0 if marketdata.get("close") is None else marketdata.get("close"),
        volume=marketdata.get("volume"),
        high=marketdata.get("highest"),
        low=marketdata.get("lowest"),
        last=marketdata.get("price"),
        book=None
    )

    # 安全地提取五档行情
    bid_list = [marketdata.get(f"bid{i}", (None, 0))[0] or 0 for i in range(1, 6)]
    bid_vol_list = [marketdata.get(f"bid{i}", (None, 0))[1] or 0 for i in range(1, 6)]
    ask_list = [marketdata.get(f"ask{i}", (None, 0))[0] or 0 for i in range(1, 6)]
    ask_vol_list = [marketdata.get(f"ask{i}", (None, 0))[1] or 0 for i in range(1, 6)]

    book = OldOrderBook(bid_list, ask_list, bid_vol_list, ask_vol_list, data.symbol, data.timestamp)
    data.book = book
    return data