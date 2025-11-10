import argparse
import json
import os
import random
import time
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional
#python services/analyzer/core/generate.py --limit 500 --batch-size 50 --repeat 3 --interval 1.0 --output-file-template services/analyzer/core/batch_{batch}{ts}.jsonl

import requests

class StockDataGenerator:
    def __init__(self, stock_basic_info):
        """
        初始化股票数据生成器
        :param stock_basic_info: 股票的基础信息，包含多个字段如symbol、name等
        """
        self.stock_basic_info = stock_basic_info

    def generate_fake_data(self):
        """
        生成伪数据，模拟股票的实时交易信息
        :return: 伪交易数据字典
        """
        stock_info = self.stock_basic_info
        symbol = stock_info.get("symbol")
        stock_name = stock_info.get("name")
        latest_price = round(random.uniform(20, 100), 2)  # 模拟一个随机的当前价格
        change_percent = round(random.uniform(-5, 5), 2)  # 随机涨跌幅 (-5% 到 5%)
        change_amount = round(latest_price * (change_percent / 100), 2)
        trading_volume = random.randint(100000, 5000000)  # 随机交易量
        trading_amount = round(latest_price * trading_volume, 2)  # 交易额
        swing = round(random.uniform(0, 10), 2)  # 振幅 (0% 到 10%)
        high = round(latest_price * (1 + random.uniform(0, swing / 100)), 2)  # 模拟最高价
        low = round(latest_price * (1 - random.uniform(0, swing / 100)), 2)  # 模拟最低价
        open_price = round(latest_price * (1 + random.uniform(-0.01, 0.01)), 2)  # 模拟开盘价
        pre_close = round(latest_price * (1 + random.uniform(-0.01, 0.01)), 2)  # 模拟昨收
        quantity_ratio = round(random.uniform(0.5, 2), 2)  # 随机换手率
        turnover_rate = round(random.uniform(0, 10), 2)  # 随机成交率
        pe_ratio_dynamic = round(random.uniform(10, 50), 2)  # 市盈率
        pb_ratio = round(random.uniform(0.5, 5), 2)  # 市净率
        is_limit_up = random.choice([True, False])  # 随机模拟是否涨停

        data = {
            "Symbol": symbol,
            "StockName": stock_name,
            "Latest": latest_price,
            "ChangePercent": change_percent,
            "ChangeAmount": change_amount,
            "TradingVolume": trading_volume,
            "TradingAmount": trading_amount,
            "Swing": swing,
            "High": high,
            "Low": low,
            "Open": open_price,
            "PreClose": pre_close,
            "QuantityRatio": quantity_ratio,
            "TurnoverRate": turnover_rate,
            "PERatioDynamic": pe_ratio_dynamic,
            "PBRatio": pb_ratio,
            "IsLimitUp": is_limit_up
        }
        return data

    def generate_data_stream(self, output_file: str, interval: float, num_entries: int) -> None:
        """
        生成伪数据流并写入文件
        :param output_file: 输出文件路径
        :param interval: 每次生成数据的时间间隔，单位：秒
        :param num_entries: 需要生成的数据条数
        """
        with open(output_file, 'w') as f:
            for _ in range(num_entries):
                fake_data = self.generate_fake_data()
                json.dump(fake_data, f)
                f.write("\n")
                time.sleep(interval)  # 模拟时间间隔
def _normalize_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将不同字段风格的记录规范化为 {symbol, name}。"""
    if not isinstance(record, dict):
        return None
    symbol = record.get("symbol") or record.get("Symbol") or record.get("ts_code") or record.get("code")
    name = record.get("name") or record.get("StockName") or record.get("stock_name") or record.get("fullname")
    if not symbol:
        return None
    return {"symbol": str(symbol), "name": str(name) if name is not None else str(symbol)}


def _parse_json_payload(payload: Any) -> List[Dict[str, Any]]:
    """从多种JSON结构中提取列表。
    支持: 直接列表; 含 Data/data 字段的对象; 单对象返回; 其他返回空列表。
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("Data", "data", "items", "list"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        # 单对象也可视为一条记录
        return [payload]
    return []


def _parse_json_lines(text: str) -> List[Dict[str, Any]]:
    """解析换行分隔的JSON（NDJSON）。"""
    records: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                records.append(obj)
        except json.JSONDecodeError:
            continue
    return records


def get_stock_basic_info(limit: Optional[int] = None, input_path: Optional[str] = None, timeout: float = 10.0) -> List[Dict[str, str]]:
    """
    获取股票基础信息列表，支持三种来源：
    - input_path 指向的本地文件（.json/.jsonl/ndjson）
    - 线上 API（返回列表、对象含 Data/data 字段，或 NDJSON 文本）
    - 出错时返回空列表
    """
    API_URL = "http://dataapi.trader.com/stock/basic_info"
    records: List[Dict[str, Any]] = []

    # 优先本地文件
    if input_path:
        if not os.path.exists(input_path):
            print(f"本地文件不存在: {input_path}")
            return []
        try:
            # 根据扩展名判断解析方式
            ext = os.path.splitext(input_path)[1].lower()
            if ext in (".json", ""):
                with open(input_path, "r", encoding="utf-8") as f:
                    text = f.read()
                # 先尝试整体 JSON
                try:
                    payload = json.loads(text)
                    records = _parse_json_payload(payload)
                except json.JSONDecodeError:
                    # 再尝试 NDJSON
                    records = _parse_json_lines(text)
            elif ext in (".jsonl", ".ndjson"):
                with open(input_path, "r", encoding="utf-8") as f:
                    records = _parse_json_lines(f.read())
            else:
                print(f"不支持的文件类型: {ext}")
                return []
        except Exception as e:
            print(f"读取本地文件失败: {e}")
            return []
    else:
        # 线上 API
        try:
            resp = requests.get(API_URL, params={"format": "json"}, timeout=timeout)
            resp.raise_for_status()
            # 优先按 JSON 解析
            try:
                payload = resp.json()
                records = _parse_json_payload(payload)
            except json.JSONDecodeError:
                # 若不是标准 JSON，按 NDJSON 文本解析
                records = _parse_json_lines(resp.text)
        except requests.exceptions.RequestException as e:
            print(f"获取股票基本信息失败: {e}")
            return []

    # 规范化与截断
    normalized: List[Dict[str, str]] = []
    for rec in records:
        norm = _normalize_record(rec)
        if norm:
            normalized.append(norm)
        if limit is not None and len(normalized) >= limit:
            break
    return normalized


def ensure_writable_dir(requested_dir: str) -> str:
    """确保输出目录可写；若权限不足则回退到 /tmp/live_monitor/fake_output。
    返回最终可写目录路径。
    """
    try:
        os.makedirs(requested_dir, exist_ok=True)
        test_path = os.path.join(requested_dir, ".perm_test")
        with open(test_path, "w") as f:
            f.write("ok")
        os.remove(test_path)
        return requested_dir
    except Exception as e:
        fallback_dir = os.path.join(tempfile.gettempdir(), "live_monitor", "fake_output")
        os.makedirs(fallback_dir, exist_ok=True)
        print(f"⚠️ 输出目录不可写({requested_dir}): {e}; 已回退到 {fallback_dir}")
        return fallback_dir

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fake stock data stream")
    parser.add_argument("--input", type=str, default=None, help="本地基础信息文件(.json/.jsonl)，为空则走API")
    parser.add_argument("--limit", type=int, default=50, help="选取多少条基础信息")
    parser.add_argument("--interval", type=float, default=0.5, help="两条伪数据间隔秒数")
    parser.add_argument("--num-entries", type=int, default=10, help="每个symbol生成条数")
    parser.add_argument("--output-dir", type=str, default=".", help="输出目录")
    # 批次模式：一次使用前N个symbol，各生成1条，重复R次，落在单个JSONL文件
    parser.add_argument("--output-file", type=str, default=None, help="批量模式输出单个JSONL文件路径；提供该参数则启用批量模式")
    parser.add_argument("--batch-size", type=int, default=50, help="批次中使用的symbol数量，仅批量模式生效")
    parser.add_argument("--repeat", type=int, default=1, help="批量模式下重复批次数")
    # 批次多文件模式：每个批次一个文件，模板支持 {batch} 与 {ts}
    parser.add_argument("--output-file-template", type=str, default=None, help="批量多文件模板，例如 /tmp/batch_{batch}_{ts}.jsonl")
    args = parser.parse_args()

    stock_basic_info_list = get_stock_basic_info(limit=args.limit, input_path=args.input)

    if not stock_basic_info_list:
        print("未能获取到股票基本信息，程序结束")
        return

    # 批量多文件模式：--output-file-template 优先
    if args.output_file_template:
        target_dir = os.path.dirname(args.output_file_template) or args.output_dir or "."
        safe_dir = ensure_writable_dir(target_dir)
        # 选取前N个symbol
        batch_symbols = stock_basic_info_list[: max(0, args.batch_size)]
        if not batch_symbols:
            print("未获取到可用的基础信息，批量模式退出")
            return
        print(f"开始批量生成(多文件): 每批 {len(batch_symbols)} 条, 重复 {args.repeat} 次 -> 目录 {safe_dir}")
        for i in range(max(1, args.repeat)):
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            basename = os.path.basename(args.output_file_template).format(batch=i + 1, ts=ts)
            out_path = os.path.join(safe_dir, basename)
            with open(out_path, "w", encoding="utf-8") as f:
                for stock_info in batch_symbols:
                    gen = StockDataGenerator(stock_info)
                    rec = gen.generate_fake_data()
                    rec["timestamp"] = ts
                    json.dump(rec, f, ensure_ascii=False)
                    f.write("\n")
            print(f"批次 {i + 1} 已写入: {out_path}")
            if i < args.repeat - 1:
                time.sleep(max(0.0, args.interval))
        print("批量多文件生成完成")
        return

    # 批量模式：--output-file 给定时启用
    if args.output_file:
        # 目标文件路径可写性与目录创建
        target_dir = os.path.dirname(args.output_file) or "."
        safe_dir = ensure_writable_dir(target_dir)
        out_path = os.path.join(safe_dir, os.path.basename(args.output_file))

        # 选取前N个symbol
        batch_symbols = stock_basic_info_list[: max(0, args.batch_size)]
        if not batch_symbols:
            print("未获取到可用的基础信息，批量模式退出")
            return

        def append_jsonl(path: str, recs: List[Dict[str, Any]]) -> None:
            with open(path, "a", encoding="utf-8") as f:
                for r in recs:
                    json.dump(r, f, ensure_ascii=False)
                    f.write("\n")

        print(f"开始批量生成: 每批 {len(batch_symbols)} 条, 重复 {args.repeat} 次 -> {out_path}")
        for i in range(max(1, args.repeat)):
            batch_records: List[Dict[str, Any]] = []
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for stock_info in batch_symbols:
                gen = StockDataGenerator(stock_info)
                rec = gen.generate_fake_data()
                rec["timestamp"] = ts
                batch_records.append(rec)
            append_jsonl(out_path, batch_records)
            if i < args.repeat - 1:
                time.sleep(max(0.0, args.interval))
        print(f"批量生成完成: {out_path}")
        return

    # 单文件/每symbol模式（保持兼容）：为每个symbol生成一个独立的JSONL文件
    safe_output_dir = ensure_writable_dir(args.output_dir)
    for stock_info in stock_basic_info_list:
        generator = StockDataGenerator(stock_info)
        symbol = stock_info["symbol"]
        output_file = os.path.join(safe_output_dir, f"{symbol}_fake_stock_data.jsonl")
        generator.generate_data_stream(output_file, interval=args.interval, num_entries=args.num_entries)
        print(f"伪数据已成功生成并保存到 {output_file}")

if __name__ == "__main__":
    main()


# 用法
# 多文件批次模式（推荐）：
# python services/analyzer/core/generate.py --input path/to/basic.jsonl --limit 500 --batch-size 50 --repeat 3 --interval 1.0 --output-file-template /tmp/fake/batch_{batch}{ts}.jsonl
# 含义：
# 每批取前 50 个 symbol，各 1 条记录，写入一个文件；重复 3 批；
# 文件名可用占位符：{batch}（批次号从1计）、{ts}（时间戳）；
# 生成：/tmp/fake/batch_1_YYYYmmddHHMMSS.jsonl、batch_2_...、batch_3_...
# 单文件批次模式（所有批次 append 到一个 JSONL）：
# python services/analyzer/core/generate.py --input path/to/basic.jsonl --batch-size 50 --repeat 10 --interval 1.0 --output-file /tmp/fake/batch.jsonl
# 每 symbol 一个文件（旧模式，保持兼容）：
# python services/analyzer/core/generate.py --input path/to/basic.jsonl --limit 50 --num-entries 10 --interval 0.2 --output-dir /tmp/fake