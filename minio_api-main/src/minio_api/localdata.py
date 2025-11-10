# 文件: open/minio_api/src/minio_api/localdata.py
from __future__ import annotations

import io
import json
from typing import List, Sequence, Optional, Union
import pandas as pd

from .config import get_config, MinIOConfig
from .downloader import MinIOFileDownloader
 
def _infer_file_type(path: str, file_type: str = "auto") -> str:
    if file_type != "auto":
        return file_type
    lower = path.lower()
    if lower.endswith(".parquet"):
        return "parquet"
    if lower.endswith(".csv") or lower.endswith(".csv.gz") or lower.endswith(".csv.gzip"):
        return "csv"
    return "csv"

# 1) 修复 gzip CSV 读取（BytesIO 上 compression='infer' 无法识别）
def _infer_csv_compression_from_name(name: str) -> Optional[str]:
    lower = name.lower()
    if lower.endswith(".csv.gz") or lower.endswith(".csv.gzip"):
        return "gzip"
    return None

def _read_info_df(
    object_path: str,
    *,
    file_type: str = "auto",
    bucket_type: str = "trader_data",
    config: Optional[MinIOConfig] = None,
) -> pd.DataFrame:
    cfg = config or get_config()
    bucket = cfg.get_bucket(bucket_type)
    dl = MinIOFileDownloader(cfg)
    name = object_path if object_path.startswith("info/") else f"info/{object_path}"
    data = dl.download_data(bucket, name)
    if data is None:
        return pd.DataFrame()

    ft = _infer_file_type(name, file_type=file_type)
    bio = io.BytesIO(data)
    if ft == "parquet":
        return pd.read_parquet(bio)

    # CSV：根据对象名判断是否 gzip（BytesIO 无法 infer）
    comp = _infer_csv_compression_from_name(name)
    return pd.read_csv(bio, compression=comp if comp else None)


def _read_info_latest_df(
    prefix: str,
    *,
    valid_suffixes: Sequence[str] = (".csv", ".csv.gz", ".csv.gzip", ".parquet"),
    file_type: str = "auto",
    bucket_type: str = "trader_data",
    config: Optional[MinIOConfig] = None,
) -> pd.DataFrame:
    cfg = config or get_config()
    bucket = cfg.get_bucket(bucket_type)
    dl = MinIOFileDownloader(cfg)
    list_prefix = f"info/{prefix.lstrip('/')}"
    objs = dl.list_objects(bucket, prefix=list_prefix, recursive=True)
    if not objs:
        return pd.DataFrame()
    cand = [o["object_name"] for o in objs if any(o["object_name"].endswith(suf) for suf in valid_suffixes)]
    if not cand:
        return pd.DataFrame()
    latest = sorted(cand)[-1]
    return _read_info_df(latest, file_type=file_type, bucket_type=bucket_type, config=cfg)

def get_code_list(
    exclude_exch_list: List[str] | None = None,
    list_date_before: str = "99999999",
    exclude_market_list: List[str] | None = None,
) -> List[str]:
    df = _read_info_latest_df("stock_basic_listed.", file_type="csv")
    if df is None or df.empty:
        return []
    df = df[df["ts_code"].notna()]
    if "list_date" in df.columns:
        df = df[df["list_date"].astype(str).str[:8].astype(int) <= int(list_date_before)]
    if exclude_market_list:
        market_map = {"main": "主板", "kcb": "科创板", "cyb": "创业板", "zxb": "中小板"}
        ex_markets = [market_map[m] for m in exclude_market_list if m in market_map]
        if "market" in df.columns and ex_markets:
            df = df[~df["market"].isin(ex_markets)]
    codes = sorted(df["ts_code"].astype(str).tolist())
    if exclude_exch_list:
        ex = set(exclude_exch_list)
        codes = [c for c in codes if c[-2:] not in ex]
    return codes

def get_basicacc_code_list(list_date_before: str = "99999999") -> List[str]:
    return get_code_list(list_date_before=list_date_before, exclude_market_list=["kcb", "cyb", "zxb"])

def get_index_list(include_exch_list: Union[List[str], str] = ("SZ", "SH")) -> List[str]:
    df = _read_info_latest_df("index_basic.", file_type="csv")
    if df is None or df.empty:
        return []
    df = df[df["ts_code"].notna()]
    if isinstance(include_exch_list, str) and include_exch_list.lower() == "all":
        return sorted(df["ts_code"].astype(str).tolist())
    if isinstance(include_exch_list, (list, tuple)) and "ALL" in include_exch_list:
        return sorted(df["ts_code"].astype(str).tolist())
    suffix = tuple(include_exch_list) if isinstance(include_exch_list, (list, tuple)) else (include_exch_list,)
    df = df[df["ts_code"].astype(str).str.endswith(suffix)]
    return sorted(df["ts_code"].astype(str).tolist())

def get_fund_code_list(market: str = "SZSH") -> List[str]:
    df = _read_info_latest_df("fund_listed_basic.", file_type="csv")
    if df is None or df.empty:
        df = _read_info_latest_df("fund_basic.", file_type="csv")
        if df is None or df.empty:
            return []
        if "status" in df.columns:
            df = df[df["status"] == "L"]
    df = df[df["ts_code"].astype(str).str.endswith(("SH", "SZ"))]
    return sorted(df["ts_code"].astype(str).tolist())

def get_fut_main_code_list(include_exchange_list: List[str] | None = None) -> List[str]:
    include_exchange_list = include_exchange_list or ["CFFEX", "SHFE", "DCE", "CZCE", "INE", "GFEX"]
    df = _read_info_latest_df("fut_basic.", file_type="csv")
    if df is None or df.empty:
        return []
    if "exchange" in df.columns:
        df = df[df["exchange"].isin(include_exchange_list)]
        exch_series = df["exchange"].astype(str)
    else:
        # 回退：从 ts_code 后缀提取（可能为简写）
        exch_series = df["ts_code"].astype(str).str.split(".").str[1]

    if "fut_code" in df.columns:
        pairs = {(str(fc), str(ex)) for fc, ex in zip(df["fut_code"], exch_series)}
        return [f"{sym}_1.{exch}" for sym, exch in sorted(pairs)]
    return []


def _read_manual_text_lines(
    object_path: str,
    *,
    bucket_type: str = "trader_data",
    config: Optional[MinIOConfig] = None,
    encoding: str = "utf-8"
) -> List[str]:
    """
    从 MinIO 读取手工维护的文本列表（每行一个标的），如: manual_files/stock_list.txt
    """
    cfg = config or get_config()
    bucket = cfg.get_bucket(bucket_type)
    dl = MinIOFileDownloader(cfg)
    name = object_path if object_path.startswith(("manual_files/", "info/")) else f"manual_files/{object_path}"
    data = dl.download_data(bucket, name)
    if data is None:
        return []
    try:
        text = data.decode(encoding, errors="ignore")
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        return lines
    except Exception:
        return []

def _read_info_latest_df_multi(
    prefixes: Sequence[str],
    *,
    file_type: str = "auto",
    bucket_type: str = "trader_data",
    config: Optional[MinIOConfig] = None,
) -> pd.DataFrame:
    """
    依次尝试多个 info/ 前缀，返回第一个可用的最新 DataFrame
    """
    from .localdata import _read_info_latest_df  # 复用已有内部方法
    for p in prefixes:
        df = _read_info_latest_df(p, file_type=file_type, bucket_type=bucket_type, config=config)
        if df is not None and not df.empty:
            return df
    return pd.DataFrame()

def get_us_code_list(list_date_before: str = "99999999") -> List[str]:
    """
    返回美股 ts_code 列表，规则对齐旧逻辑：
    - 过滤 ts_code 非空
    - 过滤 delist_date 非空（保持兼容，若需“仅在市”可改为 isna()）
    - 过滤 list_date <= list_date_before
    - 去除手工黑名单 manual_files/error_us_symbol.txt
    """
    # 常见命名尝试：优先 listed，其次 basic
    df = _read_info_latest_df_multi(
        ["us_stock_basic_listed.", "usstock_basic_listed.", "us_stock_basic.", "usstock_basic."],
        file_type="csv",
    )
    if df is None or df.empty:
        return []
    if "ts_code" not in df.columns:
        return []

    df = df[df["ts_code"].notna()]
    if "delist_date" in df.columns:
        df = df[df["delist_date"].notna()]
    if "list_date" in df.columns:
        # 容错: 非数字填充
        s = df["list_date"].astype(str).str[:8]
        s = pd.to_numeric(s, errors="coerce")
        df = df[s <= pd.to_numeric(list_date_before, errors="coerce")]

    codes = sorted(df["ts_code"].astype(str).tolist())

    # 黑名单过滤
    error_syms = _read_manual_text_lines("manual_files/error_us_symbol.txt")
    if error_syms:
        ban = set(error_syms)
        codes = [c for c in codes if c not in ban]
    return codes

def get_star_list() -> List[str]:
    """
    返回自选股/星标列表：
    - 优先读取 manual_files/stock_list.txt（每行一个代码）
    - 回退 info/stock_list.csv（取 symbol 列）
    """
    # 1) 文本版
    lines = _read_manual_text_lines("manual_files/stock_list.txt")
    if lines:
        return sorted(lines)

    # 2) CSV 版
    from .localdata import _read_info_df, _read_info_latest_df
    # 先尝试“固定名”，再尝试“最新”
    for name in ("stock_list.csv", "stock_list.csv.gz"):
        df = _read_info_df(name, file_type="csv")
        if df is not None and not df.empty and "symbol" in df.columns:
            return sorted(df["symbol"].astype(str).tolist())

    df = _read_info_latest_df("stock_list.", file_type="csv")
    if df is not None and not df.empty and "symbol" in df.columns:
        return sorted(df["symbol"].astype(str).tolist())

    return []


def get_basic_df(datestr: Optional[str] = None) -> pd.DataFrame:
    """
    返回股票基础信息 DataFrame（以 ts_code 为索引），兼容旧版 utils_localdata.get_basic_df 用法：
    - 若 datestr 指定，优先读取 info/stock_basic.{datestr}.csv(.gz) 或 info/stock_basic_listed.{datestr}.csv(.gz)
    - 否则读取最新：优先 stock_basic_listed.*，回退 stock_basic.*
    - 确保 'ts_code'、'name'、'list_date' 等字段存在时保留；索引设置为 ts_code
    """
    # 1) datestr 精确命名
    if datestr:
        for base in ("stock_basic", "stock_basic_listed"):
            for ext in (".csv", ".csv.gz", ".csv.gzip"):
                name = f"{base}.{datestr}{ext}"
                df_try = _read_info_df(name, file_type="csv")
                if df_try is not None and not df_try.empty:
                    if "list_date" in df_try.columns:
                        df_try["list_date"] = df_try["list_date"].astype(str)
                    if "ts_code" in df_try.columns:
                        df_try = df_try.set_index("ts_code", drop=False)
                    return df_try

    # 2) 最新版本（优先 listed）
    df = _read_info_latest_df("stock_basic_listed.", file_type="csv")
    if (df is None or df.empty):
        df = _read_info_latest_df("stock_basic.", file_type="csv")
    if df is None or df.empty:
        return pd.DataFrame()

    if "list_date" in df.columns:
        df["list_date"] = df["list_date"].astype(str)
    if "ts_code" in df.columns:
        df = df.set_index("ts_code", drop=False)
    return df


def _read_json_object(
    object_path: str,
    *,
    bucket_type: str = "trader_data",
    config: Optional[MinIOConfig] = None,
    encoding: str = "utf-8"
) -> Optional[dict]:
    cfg = config or get_config()
    bucket = cfg.get_bucket(bucket_type)
    dl = MinIOFileDownloader(cfg)
    name = object_path if object_path.startswith(("manual_files/", "info/")) else f"info/{object_path}"
    data = dl.download_data(bucket, name)
    if data is None:
        return None
    try:
        text = data.decode(encoding, errors="ignore")
        return json.loads(text)
    except Exception:
        return None


def get_code_dict(datestr: Optional[str] = None) -> dict:
    """
    返回 {ts_code: 信息字典} 的映射。
    优先从 MinIO 读取 JSON（manual_files/code_dict*.json 或 info/code_dict*.json），
    若不存在则由 stock_basic(.listed) 最新快照构造。
    """
    # 1) datestr 指定时优先精确读取 JSON
    if datestr:
        for base in ("manual_files/code_dict", "info/code_dict"):
            for ext in (".json", ".JSON"):
                obj = f"{base}.{datestr}{ext}"
                j = _read_json_object(obj)
                if isinstance(j, dict) and j:
                    return j

    # 2) 无 datestr：读取默认 JSON
    for obj in ("manual_files/code_dict.json", "info/code_dict.json"):
        j = _read_json_object(obj)
        if isinstance(j, dict) and j:
            return j

    # 3) 由基础表构造
    df = get_basic_df(datestr=datestr)
    if df is None or df.empty:
        return {}
    # 确保 ts_code 存在
    if "ts_code" not in df.columns:
        return {}
    # 统一字符串化关键列（避免下游假定类型）
    if "list_date" in df.columns:
        df["list_date"] = df["list_date"].astype(str)
    # 构造映射
    result: dict = {}
    for _, row in df.iterrows():
        ts = str(row.get("ts_code"))
        result[ts] = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
    return result