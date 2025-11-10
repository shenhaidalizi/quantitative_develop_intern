# 文件：services/analyzer/core/read_redis.py
import os
import json
from typing import Any, Dict, List, Optional
import os
import json
from typing import Any, Dict, List, Optional, Iterable
import glob
from datetime import datetime
try:
    from .to_redis import RedisClient
except Exception:
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from to_redis import RedisClient


# 避免触发 packages 的重型 __init__ 导入：优先本地导入
try:
    from .to_redis import RedisClient  # 用 -m 方式运行时
except Exception:
    import sys
    sys.path.insert(0, os.path.dirname(__file__))  # 直接脚本运行时
    from to_redis import RedisClient
import os
import dotenv
dotenv.load_dotenv()

# 连接参数
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "")

# 兼容：既支持单账号，也支持读写分离账号
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_WRITE_USERNAME = os.getenv("REDIS_WRITE_USERNAME", REDIS_USERNAME)
REDIS_WRITE_PASSWORD = os.getenv("REDIS_WRITE_PASSWORD", REDIS_PASSWORD)
REDIS_READ_USERNAME = os.getenv("REDIS_READ_USERNAME", REDIS_USERNAME)
REDIS_READ_PASSWORD = os.getenv("REDIS_READ_PASSWORD", REDIS_PASSWORD)



def _json_loads_maybe_twice(raw: Any) -> Optional[Dict[str, Any]]:
    """
    将 Redis 返回的值解析为 dict，兼容双层 JSON 字符串情况。
    """
    if raw is None:
        return None
    obj: Any = raw
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("utf-8", errors="ignore")
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return None
        if isinstance(obj, str):  # 二次嵌套
            try:
                obj = json.loads(obj)
            except Exception:
                pass
    if not isinstance(obj, dict):
        return None
    return obj


def _to_old_api_fields(d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    适配你给出的 Redis 值：
      {"code":"600980.SH","pre_close":25.4,"last":24.91,"volume":2696300,...}
    转成老接口字段：
      Symbol, StockName, Latest, ChangePercent, TradingVolume
    """
    code = d.get("code") or d.get("Symbol") or d.get("stock_code")
    if not code:
        return None
    last = float(d.get("last") or d.get("Latest") or d.get("price") or 0.0)
    pre_close = float(d.get("pre_close") or d.get("prev_close") or d.get("preClose") or 0.0)
    vol = float(d.get("volume") or d.get("TradingVolume") or 0.0)

    chg = 0.0
    if pre_close and pre_close > 0:
        chg = (last / pre_close - 1.0) * 100.0

    return {
        "Symbol": str(code),
        "StockName": str(d.get("stock_name", "")),  # 你数据里没有名字，这里留空字符串
        "Latest": last,
        "ChangePercent": round(chg, 2),
        "TradingVolume": vol,  # 为累计成交量，后续逻辑会做差分得到每分钟量
    }


def fetch_one(symbol: str) -> Optional[Dict[str, Any]]:
    """
    读取单只股票（例如 symbol='600980.SH'），等价于 GET teamPublic:600980.SH
    返回老接口字段的 dict。
    """
    client = RedisClient(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        username=REDIS_READ_USERNAME,
        password=REDIS_READ_PASSWORD,
        prefix=REDIS_PREFIX,
    )
    raw = client.client.get(f"{REDIS_PREFIX}{symbol}")
    d = _json_loads_maybe_twice(raw)
    if not d:
        return None
    return _to_old_api_fields(d)


def _chunks(it: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(it), n):
        yield it[i : i + n]


def fetch_snapshot_from_env(pattern: str = "*", chunk: int = 1000) -> List[Dict[str, Any]]:
    """
    扫描命名空间内所有股票（如 teamPublic:*），批量 MGET，转换为老接口列表。
    """
    client = RedisClient(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        username=REDIS_READ_USERNAME,
        password=REDIS_READ_PASSWORD,
        prefix=REDIS_PREFIX,
    )

    # 注意：此处 scan_iter 已经带上前缀（内部 _k）
    keys = list(client.scan_iter(pattern))
    if not keys:
        return []

    out: List[Dict[str, Any]] = []
    for part in _chunks(keys, chunk):
        vals = client.client.mget(part)  # 直接用全量 key 批量获取
        for raw in vals:
            d = _json_loads_maybe_twice(raw)
            if not d:
                continue
            norm = _to_old_api_fields(d)
            if norm:
                out.append(norm)
    return out



import os
from io import BytesIO
from typing import List, Dict, Any, Optional

import pandas as pd
import requests

BASE_URL = os.getenv(
    "BASIC_INFO_API_URL",
    "http://dataapi.trader.com/stock/basic_info",
)

import json
from typing import Dict, Any, List, Optional
def _pick_writable_cache_dir() -> str:
    """
    选择一个可写目录：优先 env，其次模块同级 data，/app/statistic_data，最后 /tmp。
    """
    cands = []
    env_dir = os.getenv("BASIC_INFO_CACHE_DIR")
    if env_dir:
        cands.append(env_dir)
    cands += [
        os.path.join(os.path.dirname(__file__), "data"),
        "/app/statistic_data/basic_info_cache",
        "/tmp/live_monitor/basic_info_cache",
    ]
    for d in cands:
        if not d:
            continue
        try:
            os.makedirs(d, exist_ok=True)
            test_fp = os.path.join(d, ".perm_test")
            with open(test_fp, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test_fp)
            return d
        except Exception:
            continue
    return "/tmp"  # 兜底

BASIC_INFO_CACHE_DIR = _pick_writable_cache_dir()
BASIC_INFO_CACHE_PREFIX = os.getenv("BASIC_INFO_CACHE_PREFIX", "basic_info_name_map")

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _write_json_atomic(fp: str, obj: Any) -> None:
    _ensure_dir(os.path.dirname(fp))
    tmp = f"{fp}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, fp)

def _today_tag() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def _name_map_path(date_tag: str) -> str:
    _ensure_dir(BASIC_INFO_CACHE_DIR)
    return os.path.join(BASIC_INFO_CACHE_DIR, f"{BASIC_INFO_CACHE_PREFIX}_{date_tag}.json")


def _list_name_map_files() -> List[str]:
    pat = os.path.join(BASIC_INFO_CACHE_DIR, f"{BASIC_INFO_CACHE_PREFIX}_*.json")
    files = glob.glob(pat)
    files.sort(reverse=True)  # YYYY-MM-DD 字符串可按字典序逆序=新→旧
    return files


def fetch_basic_info(fmt: str = "json") -> Optional[pd.DataFrame]:
    """
    fmt 取值: 'json' | 'csv.gz' | 'parquet'
    返回 DataFrame，自动适配不同格式。
    """
    url = f"{BASE_URL}?format={fmt}"
    resp = requests.get(url, timeout=15, proxies={"http": None, "https": None})
    resp.raise_for_status()

    if fmt == "json":
        print("json")
        data = resp.json()
        rows: List[Dict[str, Any]]
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            rows = data["data"]
        elif isinstance(data, list):
            rows = data
        else:
            return None
        return pd.DataFrame(rows)

    if fmt == "csv.gz":
        # gzip 压缩的 CSV
        print("csv.gz")
        return pd.read_csv(
            BytesIO(resp.content),
            compression="gzip",
            dtype=str,
            keep_default_na=False,
            engine="python",
        )

    if fmt == "parquet":
        # 列式二进制格式
        print("parquet")
        return pd.read_parquet(BytesIO(resp.content))

    raise ValueError(f"unsupported format: {fmt}")

# 加到 services/analyzer/core/read_redis.py（放在 fetch_basic_info 附近）
from typing import Any, Dict, List, Optional
import requests

def get_stock_basic_info() -> Optional[List[Dict[str, Any]]]:
    """
    从基础信息接口获取 JSON，返回 list[dict]。
    兼容两种返回：
      1) {"data": [...]}  2) [...]
    """
    try:
        url = f"{BASE_URL}?format=json"
        resp = requests.get(url, timeout=15, proxies={"http": None, "https": None})
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict) and isinstance(data.get("data"), list):
            rows = data["data"]
        elif isinstance(data, list):
            rows = data
        else:
            return None

        out: List[Dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            obj = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
            # 关键字段统一为字符串，避免前导零丢失
            if "ts_code" in obj:
                obj["ts_code"] = str(obj["ts_code"]).strip()
            if "name" in obj:
                obj["name"] = str(obj["name"]).strip()
            out.append(obj)
        return out
    except Exception as e:
        print(f"get_stock_basic_info failed: {e}")
        return None

def build_name_map_file(out_path: Optional[str] = None) -> str:
    """
    生成 {ts_code->name} 文件。未传 out_path 时，默认写入“今天”的文件。
    """
    out = out_path or _name_map_path(_today_tag())
    rows = get_stock_basic_info() or []
    name_map: Dict[str, str] = {}
    for r in rows:
        if isinstance(r, dict):
            code = str(r.get("ts_code", "")).strip()
            name = str(r.get("name", "")).strip()
            if code and name:
                name_map[code] = name
    _write_json_atomic(out, name_map)
    return out

def ensure_today_name_map_file(keep: int = 1) -> str:
    """
    若今日文件存在则复用；若不存在则生成今日文件。
    之后仅保留最近 keep 份（默认只保留今天），删除更旧的。
    """
    today_fp = _name_map_path(_today_tag())
    if not os.path.exists(today_fp):
        build_name_map_file(today_fp)
    # 清理旧文件
    files = _list_name_map_files()
    for fp in files[keep:]:
        try:
            os.remove(fp)
        except Exception:
            pass
    return today_fp

def load_name_map(path: Optional[str] = None) -> Dict[str, str]:
    """
    读映射：优先传入 path；否则优先读今日文件；若无则读最新一份；都没有则返回空。
    """
    if path and os.path.exists(path):
        fp = path
    else:
        today_fp = _name_map_path(_today_tag())
        if os.path.exists(today_fp):
            fp = today_fp
        else:
            files = _list_name_map_files()
            if not files:
                return {}
            fp = files[0]
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return {str(k).strip(): str(v).strip() for k, v in data.items() if k and v}
    except Exception:
        return {}

def fetch_snapshot_with_names_fileonly() -> List[Dict[str, Any]]:
    """
    不用内存缓存：每次调用都从本地映射文件读取名称，然后拉取 Redis 快照并填充。
    返回字段：Symbol, StockName, Latest, ChangePercent, TradingVolume
    """
    name_map = load_name_map()
    data = fetch_snapshot_from_env(pattern="*")  # 需已实现 Redis 扫描与规范化
    if not data:
        return []
    for rec in data:
        code = rec.get("Symbol")
        if code and not rec.get("StockName"):
            rec["StockName"] = name_map.get(code, "")
    return data

# 追加到 services/analyzer/core/read_redis.py 末尾，提供本地可运行的测试 CLI
import argparse
import json

def _print_json(obj, limit: int = None):
    if isinstance(obj, list) and limit is not None:
        obj = obj[:limit]
    print(json.dumps(obj, ensure_ascii=False, indent=2))

def cli():
    parser = argparse.ArgumentParser(description="read_redis 测试工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("build-map", help="从基础信息API生成本地映射文件")
    p1.add_argument("--out", default=None, help="输出路径（默认 env BASIC_INFO_CACHE_FILE）")

    p2 = sub.add_parser("print-map", help="打印本地映射文件的前N条")
    p2.add_argument("-n", type=int, default=5)

    p3 = sub.add_parser("fetch-one", help="按 ts_code 读取单只（如 600980.SH）")
    p3.add_argument("--code", required=True)

    p4 = sub.add_parser("fetch-scan", help="扫描Redis并拉取全市场")
    p4.add_argument("--limit", type=int, default=5, help="仅打印前N条")
    p4.add_argument("--names-file", action="store_true", help="用本地名称映射填充名称")

    args = parser.parse_args()

    # 标注当前 Redis 连接信息，便于诊断
    print(f"[cfg] REDIS {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB} prefix='{REDIS_PREFIX}'")

    if args.cmd == "build-map":
        path = build_name_map_file(args.out)
        name_map = load_name_map(path)
        print(f"[ok] 写入映射文件: {path}，条数={len(name_map)}")
        # 打印样例
        sample = list(name_map.items())[:5]
        _print_json(sample)

    elif args.cmd == "print-map":
        name_map = load_name_map()
        print(f"[ok] 本地映射条数={len(name_map)}")
        sample = list(name_map.items())[: args.n]
        _print_json(sample)

    elif args.cmd == "fetch-one":
        rec = fetch_one(args.code)
        # 若有本地名称映射则补齐
        if rec and (not rec.get("StockName")):
            nm = load_name_map()
            if rec.get("Symbol") in nm:
                rec["StockName"] = nm[rec["Symbol"]]
        _print_json(rec or {})

    elif args.cmd == "fetch-scan":
        if args.names_file:
            data = fetch_snapshot_with_names_fileonly()
        else:
            data = fetch_snapshot_from_env(pattern="*")
        print(f"[ok] snapshot 数={len(data)}")
        _print_json(data, limit=args.limit)

if __name__ == "__main__":
    cli()
