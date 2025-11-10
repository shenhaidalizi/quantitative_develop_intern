# /home/ubuntu/TradeNew/live/live_futures/scripts/data_recorder.py
import argparse
import csv
import os
import queue
import signal
import threading
import time
from pathlib import Path
from typing import Dict, Tuple, Optional, List

from trader_livefut.execution.trading_client import TradingClient
from trader_livefut.configs.settings import FUTURES_LIVE_DATA_PATH

try:
    from trader_livefut.utils.utils_logging import setRootLogger  # 可选
except Exception:  # noqa: BLE001
    setRootLogger = None


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _fmt_ms(ms: int) -> str:
    # 将毫秒整数格式化为3位字符串
    try:
        return f"{int(ms):03d}"
    except Exception:
        return "000"


def _build_event_time(trade_time: str, update_ms: Optional[int]) -> str:
    # trade_time: "YYYY-MM-DD HH:MM:SS"
    # update_ms: int 毫秒
    if not trade_time:
        return ""
    if update_ms is None:
        return trade_time
    return f"{trade_time}.{_fmt_ms(update_ms)}"


def _flatten_tick(tick: dict) -> Tuple[str, str, int, List]:
    """
    将 CTP 行情字典扁平化为一行 CSV 记录（字段顺序固定）。
    返回: (symbol, date_str, update_ms, row_values)
    """
    # 关键字段
    code = tick.get("code", "")
    trade_time = tick.get("trade_time", "")
    update_ms = tick.get("update_sec", None)
    date_str = trade_time.split(" ")[0].replace("-", "") if trade_time else time.strftime("%Y%m%d")

    # 价格与统计
    price = tick.get("price")
    open_ = tick.get("open")
    close = tick.get("close")
    highest = tick.get("highest")
    lowest = tick.get("lowest")
    upper_limit = tick.get("upper_limit")
    lower_limit = tick.get("lower_limit")
    settlement = tick.get("settlement")
    volume = tick.get("volume")
    turnover = tick.get("turnover")
    open_interest = tick.get("open_interest")
    pre_close = tick.get("pre_close")
    pre_settlement = tick.get("pre_settlement")
    pre_open_interest = tick.get("pre_open_interest")

    # 五档
    def _pair(t):
        if isinstance(t, (tuple, list)) and len(t) == 2:
            return t[0], t[1]
        return None, None

    bid1_p, bid1_v = _pair(tick.get("bid1"))
    bid2_p, bid2_v = _pair(tick.get("bid2"))
    bid3_p, bid3_v = _pair(tick.get("bid3"))
    bid4_p, bid4_v = _pair(tick.get("bid4"))
    bid5_p, bid5_v = _pair(tick.get("bid5"))

    ask1_p, ask1_v = _pair(tick.get("ask1"))
    ask2_p, ask2_v = _pair(tick.get("ask2"))
    ask3_p, ask3_v = _pair(tick.get("ask3"))
    ask4_p, ask4_v = _pair(tick.get("ask4"))
    ask5_p, ask5_v = _pair(tick.get("ask5"))

    event_time = _build_event_time(trade_time, update_ms)
    recv_ts_ms = time.time_ns() // 1_000_000

    row = [
        event_time, trade_time, update_ms, code,
        price, open_, close, highest, lowest,
        upper_limit, lower_limit, settlement,
        volume, turnover, open_interest,
        pre_close, pre_settlement, pre_open_interest,
        bid1_p, bid1_v, ask1_p, ask1_v,
        bid2_p, bid2_v, ask2_p, ask2_v,
        bid3_p, bid3_v, ask3_p, ask3_v,
        bid4_p, bid4_v, ask4_p, ask4_v,
        bid5_p, bid5_v, ask5_p, ask5_v,
        recv_ts_ms,
    ]
    return code, date_str, update_ms if isinstance(update_ms, int) else -1, row


CSV_HEADER = [
    "event_time", "trade_time", "update_ms", "code",
    "price", "open", "close", "highest", "lowest",
    "upper_limit", "lower_limit", "settlement",
    "volume", "turnover", "open_interest",
    "pre_close", "pre_settlement", "pre_open_interest",
    "bid1", "bid1_vol", "ask1", "ask1_vol",
    "bid2", "bid2_vol", "ask2", "ask2_vol",
    "bid3", "bid3_vol", "ask3", "ask3_vol",
    "bid4", "bid4_vol", "ask4", "ask4_vol",
    "bid5", "bid5_vol", "ask5", "ask5_vol",
    "recv_ts_ms",
]


class DataRecorder:
    """
    异步落盘器：
    - 回调线程仅做入队，避免阻塞 CTP 回调
    - 后台线程批量写入 CSV
    - 自动按天按合约分文件: out_root/ticks/<env>/<YYYYMMDD>/<SYMBOL>.csv
    """

    def __init__(self, out_root: Path, env: str, flush_interval: float = 1.0, batch_size: int = 2000):
        self.out_root = Path(out_root)
        self.env = env
        self.flush_interval = flush_interval
        self.batch_size = batch_size

        self._q: "queue.Queue[dict]" = queue.Queue(maxsize=200_000)
        self._stop = threading.Event()
        self._t: Optional[threading.Thread] = None

        # file_key -> (file_handle, csv_writer, header_written)
        self._files: Dict[Tuple[str, str], Tuple[object, csv.writer, bool]] = {}

    def start(self) -> None:
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, name="DataRecorderWriter", daemon=True)
        self._t.start()

    def stop(self) -> None:
        self._stop.set()
        if self._t:
            self._t.join(timeout=5.0)
        # 确保全部关闭
        for (sym, d), (fh, _, _) in list(self._files.items()):
            try:
                fh.flush()
                fh.close()
            except Exception:
                pass
            self._files.pop((sym, d), None)

    def callback(self, tick: dict) -> None:
        try:
            self._q.put_nowait(tick)
        except queue.Full:
            # 丢弃策略：打印一条告警但不阻塞；生产可改为环形缓冲或分片落盘
            # 避免阻塞行情线程
            pass

    def _open_writer(self, symbol: str, date_str: str) -> Tuple[object, csv.writer, bool]:
        key = (symbol, date_str)
        if key in self._files:
            return self._files[key]

        out_dir = self.out_root / "ticks" / self.env / date_str
        _ensure_dir(out_dir)
        fpath = out_dir / f"{symbol}.csv"
        exists = fpath.exists()
        fh = open(fpath, "a", newline="", encoding="utf-8")
        writer = csv.writer(fh)
        header_written = exists and self._has_header(fpath)
        if not header_written and fpath.stat().st_size == 0:
            writer.writerow(CSV_HEADER)
            header_written = True
            fh.flush()
        self._files[key] = (fh, writer, header_written)
        return self._files[key]

    @staticmethod
    def _has_header(fpath: Path) -> bool:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return f.readline().strip().split(",") == CSV_HEADER
        except Exception:
            return False

    def _loop(self) -> None:
        last_flush = time.monotonic()
        pending: List[Tuple[str, str, List]] = []

        while not self._stop.is_set():
            timeout = max(0.0, self.flush_interval - (time.monotonic() - last_flush))
            try:
                item = self._q.get(timeout=timeout if timeout > 0 else 0.01)
                symbol, date_str, _, row = _flatten_tick(item)
                pending.append((symbol, date_str, row))
            except queue.Empty:
                pass

            need_flush = (
                (time.monotonic() - last_flush) >= self.flush_interval
                or len(pending) >= self.batch_size
                or (self._stop.is_set() and pending)
            )
            if not need_flush:
                continue

            # 分桶写入
            try:
                buckets: Dict[Tuple[str, str], List[List]] = {}
                for sym, d, r in pending:
                    buckets.setdefault((sym, d), []).append(r)

                for (sym, d), rows in buckets.items():
                    fh, writer, header_written = self._open_writer(sym, d)
                    writer.writerows(rows)
                    try:
                        fh.flush()
                        os.fsync(fh.fileno())
                    except Exception:
                        pass
            finally:
                pending.clear()
                last_flush = time.monotonic()


def main() -> None:
    parser = argparse.ArgumentParser(description="CTP Tick 数据落盘器（CSV）")
    parser.add_argument("-e", "--env", type=str, default="sim", help="环境名（与 brokers.json 中的键一致）")
    parser.add_argument("-s", "--symbols", type=str, required=True, help="订阅合约，逗号分隔，如: IM2509,IF2509")
    parser.add_argument("-o", "--out-dir", type=str, default=str(Path(FUTURES_LIVE_DATA_PATH)), help="输出根目录（默认使用项目 data 路径）")
    parser.add_argument("-c", "--config", type=str, default=str(Path(__file__).resolve().parent / "brokers.json"), help="brokers.json 路径")
    parser.add_argument("--flush-interval", type=float, default=1.0, help="批量写入间隔秒")
    parser.add_argument("--batch-size", type=int, default=2000, help="批量写入最大条数")
    args = parser.parse_args()

    if setRootLogger:
        today = time.strftime("%Y%m%d")
        setRootLogger(log_filename=f"data_recorder_{today}.log", output_console=True)

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    out_root = Path(args.out_dir)

    client = TradingClient(config_path=args.config, env=args.env, password=os.getenv("CTP_PASSWORD") or "")
    client.login(mode="md")

    recorder = DataRecorder(out_root=out_root, env=args.env, flush_interval=args.flush_interval, batch_size=args.batch_size)
    recorder.start()
    client.set_market_data_callback(recorder.callback)
    client.subscribe(symbols)

    stop_flag = {"stop": False}

    def _graceful_shutdown(signum, frame):
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    try:
        while not stop_flag["stop"]:
            time.sleep(0.5)
    finally:
        try:
            client.unsubscribe(symbols)
        except Exception:
            pass
        recorder.stop()
        client.logout()


if __name__ == "__main__":
    main()
