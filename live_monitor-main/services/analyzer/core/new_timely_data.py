#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
new_timely_data.py
- 每分钟从 http://dataapi.trader.com/live/cn/all 拉取全市场快照
- 基于 TradingVolume 维护每支股票 30 分钟分钟量窗口，计算 rolling1/5/10/30 与 all（累计）
- 读取预计算统计 parquet（列: time, stock_code, window_type, mean, std）
- 以当分钟交易时刻的统计均值/方差计算各窗口 z-score（含 all → rolling_full）
- 维护 ChangePercent 的 30 分钟窗口，计算 Chg5/Chg30（最近 5/30 分钟变化的百分点差）
- 生成 JSON（records），字段顺序严格：
  code, Name, Price, Chg, Vol, r1_z, r5_z, r10_z, r30_z, rolling_full, Chg5, Chg30
"""

import os
import time as pytime
import json
from dataclasses import dataclass, field
from typing import Dict, Deque, Optional, List, Tuple
from collections import deque
from datetime import datetime, time as dt_time, timedelta

import requests
import pandas as pd
import numpy as np
import glob

# 在 services/analyzer/core/new_timely_data.py 顶部合适位置加入（与 fetch_snapshot 的导入方式一致）
try:
    from services.analyzer.core.read_redis import ensure_today_name_map_file as _ensure_name_map
except Exception:
    try:
        from .read_redis import ensure_today_name_map_file as _ensure_name_map
    except Exception:
        import os, sys
        sys.path.insert(0, os.path.dirname(__file__))
        from read_redis import ensure_today_name_map_file as _ensure_name_map

# ==================== 配置 ====================

API_URL = "http://dataapi.trader.com/live/cn/all"

@dataclass
class TradingConfig:
    morning_start: dt_time = dt_time(9, 31, 0)
    morning_end: dt_time = dt_time(11, 30, 0)   # 左闭右开，至 11:29
    afternoon_start: dt_time = dt_time(13, 0, 0)
    afternoon_end: dt_time = dt_time(15, 0, 0)  # 左闭右开，至 14:59
    update_interval: int = 60  # 秒
    max_keep_groups: int = 5   # 保留最近 N 组 test_*.json
    window_lengths: Tuple[int, ...] = (1, 5, 10, 30)  # 分钟窗口
    chg_window: int = 31  # 对 ChangePercent 维护的窗口大小

@dataclass
class PathConfig:
    """路径配置类"""
    # 支持通过环境变量配置数据根目录
    data_root: str = os.getenv('DATA_ROOT', os.path.dirname(os.path.abspath(__file__)))
    
    @property
    def previous_data_path(self) -> str:
        """动态获取最新的时间数据文件路径"""
        statistic_dir = os.path.join(self.data_root, "statistic_data")
        
        # 确保目录存在
        if not os.path.exists(statistic_dir):
            os.makedirs(statistic_dir)
        
        # 查找所有匹配的时间数据文件 - 改为parquet格式
        pattern = os.path.join(statistic_dir, "time_data_*.parquet")
        files = glob.glob(pattern)
        
        if files:
            # 按修改时间排序，返回最新的文件
            latest_file = max(files, key=os.path.getmtime)
            print(f"📁 使用最新的数据文件: {latest_file}")
            return latest_file
        else:
            # 如果没有找到文件，使用当前日期作为默认值
            today_date = datetime.now().strftime('%Y-%m-%d')
            default_file = os.path.join(statistic_dir, f"time_data_{today_date}.parquet")
            print(f"⚠️ 未找到历史数据文件，将使用: {default_file}")
            return default_file
    
    @property
    def save_data_path(self) -> str:
        return os.path.join(self.data_root, "data", "test_result")
    
    @property
    def test_data_path(self) -> str:
        return os.path.join(self.data_root, "data", "test_data")
    
    @property
    def index_data_path(self) -> str:
        return os.path.join(self.data_root, "data", "index_data")
    
    @property
    def index_weight_data_path(self) -> str:
        return os.path.join(self.data_root, "data", "index_weight_data.csv")

    @property
    def test_save_data_path(self) -> str:
        """测试模式专用保存路径"""
        return os.path.join(self.data_root, "data", "test_result_temp")


CONFIG = TradingConfig()
PATHS = PathConfig()


# ==================== 交易时间索引与工具 ====================

def create_trading_time_map(cfg: TradingConfig) -> Tuple[Dict[str, int], Dict[int, str]]:
    time_to_idx: Dict[str, int] = {}
    idx_to_time: Dict[int, str] = {}
    idx = 0

    def add_session(start_: dt_time, end_: dt_time) -> None:
        nonlocal idx
        cur = datetime.combine(datetime.today().date(), start_)
        end_dt = datetime.combine(datetime.today().date(), end_)
        while cur < end_dt:
            t = cur.strftime("%H:%M:00")
            time_to_idx[t] = idx
            idx_to_time[idx] = t
            idx += 1
            cur += timedelta(minutes=1)

    add_session(cfg.morning_start, cfg.morning_end)
    add_session(cfg.afternoon_start, cfg.afternoon_end)
    return time_to_idx, idx_to_time


TIME_TO_INDEX, INDEX_TO_TIME = create_trading_time_map(CONFIG)


def time_str_to_us(t: str) -> int:
    """'HH:MM:SS' → 当天微秒数（如 09:31:00 → 34260*1e6 = 34260000000）"""
    h, m, s = map(int, t.split(":"))
    sec = h * 3600 + m * 60 + s
    return sec * 1_000_000


def now_minute_str() -> str:
    return datetime.now().strftime("%H:%M:00")


def is_trading_time(t: str) -> bool:
    return t in TIME_TO_INDEX


def get_trading_index(t: str) -> Optional[int]:
    return TIME_TO_INDEX.get(t)


def wait_next_minute() -> None:
    now = datetime.now()
    sleep_sec = 60 - now.second - (1 if now.microsecond > 0 else 0)
    if sleep_sec > 0:
        pytime.sleep(sleep_sec)


# ==================== 统计数据读取（parquet） ====================

def load_stats_parquet(parquet_path: str) -> pd.DataFrame:
    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"统计文件不存在: {parquet_path}")
    df = pd.read_parquet(parquet_path)

    required = {"time", "stock_code", "window_type", "mean", "std"}
    if not required.issubset(df.columns):
        raise ValueError(f"统计文件缺少列: {required - set(df.columns)}")

    df = df[["time", "stock_code", "window_type", "mean", "std"]].copy()

    def to_time_us(v):
        if isinstance(v, (int, np.integer)):
            return int(v)
        if isinstance(v, str):
            try:
                parts = v.split(":")
                h = int(parts[0]); m = int(parts[1])
                sec_part = parts[2] if len(parts) >= 3 else "00"
                if "." in sec_part:
                    s_str, micro_str = sec_part.split(".", 1)
                    s = int(s_str)
                    micro = int((micro_str + "000000")[:6])
                else:
                    s = int(sec_part)
                    micro = 0
                return (h * 3600 + m * 60 + s) * 1_000_000 + micro
            except Exception:
                return np.nan
        if isinstance(v, dt_time):
            return (v.hour * 3600 + v.minute * 60 + v.second) * 1_000_000 + v.microsecond
        if hasattr(v, "to_pydatetime"):
            t = v.to_pydatetime()
            return (t.hour * 3600 + t.minute * 60 + t.second) * 1_000_000 + t.microsecond
        return np.nan

    df["time"] = df["time"].apply(to_time_us)
    df = df[df["time"].notna()].copy()
    df["time"] = df["time"].astype(np.int64)

    # 保留后缀，统一大写（与快照中的 Symbol 一致）
    df["code"] = df["stock_code"].astype(str).str.upper()
    return df[["time", "code", "window_type", "mean", "std"]]


def get_stats_for_time(stats_df: pd.DataFrame, time_us: int) -> pd.DataFrame:
    """
    取某个 time_us 对应的统计，返回列扁平化:
    index=code；列: rolling1_mean, rolling1_std, rolling5_mean, ..., all_mean, all_std
    """
    sub = stats_df[stats_df["time"] == time_us].copy()
    if sub.empty:
        # 回退：找最接近且不晚于当前的 time
        cand = stats_df.loc[stats_df["time"] <= time_us, "time"]
        if not cand.empty:
            last_t = cand.max()
            sub = stats_df[stats_df["time"] == last_t].copy()
        else:
            return pd.DataFrame(index=[], columns=[])

    piv = sub.pivot_table(index="code", columns="window_type", values=["mean", "std"])
    piv.columns = [f"{lvl2}_{lvl1}" for lvl1, lvl2 in piv.columns]  # ('mean','rolling1')→'rolling1_mean'
    piv = piv.reset_index().rename(columns={"code": "code"}).set_index("code")
    # 确保 all_mean/std 存在（缺失则填 NaN）
    for w in ("rolling1", "rolling5", "rolling10", "rolling30", "all"):
        for s in ("mean", "std"):
            col = f"{w}_{s}"
            if col not in piv.columns:
                piv[col] = np.nan
    return piv


# ==================== 实时快照与 rolling 维护 ====================

@dataclass
class SymbolState:
    prev_cum_vol: Optional[float] = None
    vol_deque: Deque[float] = field(default_factory=lambda: deque(maxlen=CONFIG.window_lengths[-1]))
    chg_deque: Deque[float] = field(default_factory=lambda: deque(maxlen=CONFIG.chg_window))


class RollingEngine:
    def __init__(self) -> None:
        self.states: Dict[str, SymbolState] = {}

    def update_and_get_windows(
        self,
        symbol: str,
        cum_vol: float,
        chg_percent: float
    ) -> Dict[str, float]:
        st = self.states.get(symbol)
        if st is None:
            st = SymbolState()
            self.states[symbol] = st

        # 计算分钟交易量（由累计量差分）
        if st.prev_cum_vol is None or cum_vol < st.prev_cum_vol:
            # 第一次或跨日/重置
            minute_vol = 0.0
        else:
            minute_vol = float(max(cum_vol - st.prev_cum_vol, 0.0))

        st.prev_cum_vol = float(cum_vol)
        st.vol_deque.append(minute_vol)

        # 维护 ChangePercent 窗口
        st.chg_deque.append(float(chg_percent))

        # 计算 rolling 窗口和 all
        res = {}
        vol_list = list(st.vol_deque)
        for w in CONFIG.window_lengths:
            res[f"rolling{w}"] = float(sum(vol_list[-w:])) if len(vol_list) > 0 else 0.0

        # 全量累计优先使用接口累计量
        res["all"] = float(cum_vol)
        return res

    # 将上面函数替换为：
    def get_chg_delta(self, symbol: str, minutes: int) -> float:
        st = self.states.get(symbol)
        if st is None or minutes <= 0 or len(st.chg_deque) == 0:
            return 0.0

        dq = st.chg_deque
        latest = float(dq[-1])

        # 足够分钟数：最新 - 恰好 minutes 之前
        if len(dq) > minutes:
            base = float(dq[-1 - minutes])
            return latest - base

        # 不足分钟数：最新 - 最旧
        if len(dq) >= 2:
            return latest - float(dq[0])

        return 0.0

    def get_chg_sum(self, symbol: str, window: int) -> float:
        st = self.states.get(symbol)
        if st is None or window <= 0 or len(st.chg_deque) == 0:
            return 0.0
        dq = list(st.chg_deque)
        # 仅对最近 window 个分钟的 Chg 求和；可用 np.nansum 更稳健
        return float(np.nansum(dq[-window:]))


from typing import Optional, List, Dict

def fetch_snapshot() -> Optional[List[Dict]]:
    """
    每分钟：仅从本地映射文件取名称，再从 Redis 取行情。
    """
    try:
        from services.analyzer.core.read_redis import fetch_snapshot_with_names_fileonly as _fetch
    except Exception:
        try:
            from .read_redis import fetch_snapshot_with_names_fileonly as _fetch
        except Exception:
            import os, sys
            sys.path.insert(0, os.path.dirname(__file__))
            from read_redis import fetch_snapshot_with_names_fileonly as _fetch

    data = _fetch()
    return data if data else None


# ==================== Z-Score 计算 ====================

# 替换 /home/zhousiyuan/live_monitor/services/analyzer/core/new_timely_data.py 中的 compute_z_scores

def compute_z_scores(rolling_df: pd.DataFrame, stats_df: pd.DataFrame) -> pd.DataFrame:
    """
    rolling_df: index=code, 列: rolling1, rolling5, rolling10, rolling30, all
                （若存在 rolling_full_mean/rolling_full_std 也会被使用）
    stats_df:   index=code, 列: rolling1_mean/std, ..., all_mean/std, (可选) rolling_full_mean/std
    返回：在 rolling_df 基础上新增列：
      rolling1_z, rolling5_z, rolling10_z, rolling30_z, all_z
    """
    merged = rolling_df.join(stats_df, how="inner")

    # 常规窗口按各自 mean/std
    for w in ("rolling1", "rolling5", "rolling10", "rolling30"):
        mean_col = f"{w}_mean"
        std_col = f"{w}_std"
        z_col = f"{w}_z"
        if mean_col in merged.columns and std_col in merged.columns:
            std = merged[std_col].replace(0, np.nan)
            z = (merged[w] - merged[mean_col]) / std
            merged[z_col] = z.fillna(0.0).round(2)
        else:
            merged[z_col] = 0.0

    # all_z 特殊：优先使用 rolling_full_mean/std，其次回退 all_mean/std
    base_col = "all"
    mean_col_all = (
        "rolling_full_mean" if "rolling_full_mean" in merged.columns
        else "all_mean" if "all_mean" in merged.columns
        else None
    )
    std_col_all = (
        "rolling_full_std" if "rolling_full_std" in merged.columns
        else "all_std" if "all_std" in merged.columns
        else None
    )
    if mean_col_all and std_col_all and base_col in merged.columns:
        std = merged[std_col_all].replace(0, np.nan)
        z = (merged[base_col] - merged[mean_col_all]) / std
        merged["all_z"] = z.fillna(0.0).round(2)
    else:
        merged["all_z"] = 0.0

    return merged[["rolling1_z", "rolling5_z", "rolling10_z", "rolling30_z", "all_z"]]


# ==================== 文件与输出 ====================

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def manage_result_files(save_path: str, max_groups: int) -> None:
    try:
        files = [f for f in os.listdir(save_path) if f.startswith("test_") and f.endswith(".json")]
        if len(files) <= max_groups:
            return
        files_full = [(os.path.getmtime(os.path.join(save_path, f)), f) for f in files]
        files_full.sort()
        for _, fn in files_full[:-max_groups]:
            try:
                os.remove(os.path.join(save_path, fn))
            except Exception:
                pass
    except Exception:
        pass


def save_json(records: List[Dict], now_str: str, idx: int) -> str:
    ensure_dir(PATHS.save_data_path)
    file_base = f"test_{now_str.replace(':', '')}_idx{idx}"
    fp = os.path.join(PATHS.save_data_path, f"{file_base}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)
    manage_result_files(PATHS.save_data_path, CONFIG.max_keep_groups)
    return fp


def _debug_base_dir() -> str:
    return os.path.join(PATHS.save_data_path, "debug")

def _prepare_tick_debug_dir(t_str: str) -> str:
    safe_ts = t_str.replace(":", "")
    d = os.path.join(_debug_base_dir(), safe_ts)
    ensure_dir(d)
    return d

def _cleanup_old_debug_dirs(keep: int = None) -> None:
    keep = keep or CONFIG.max_keep_groups
    base = _debug_base_dir()
    if not os.path.exists(base):
        return
    subdirs = [os.path.join(base, x) for x in os.listdir(base) if os.path.isdir(os.path.join(base, x))]
    if len(subdirs) <= keep:
        return
    subdirs.sort(key=lambda p: os.path.getmtime(p))
    for p in subdirs[:-keep]:
        try:
            # 删除整个时间戳调试目录
            for root, _, files in os.walk(p, topdown=False):
                for f in files:
                    os.remove(os.path.join(root, f))
                os.rmdir(root)
        except Exception:
            pass

import os
from minio import Minio
from datetime import datetime
from minio.error import S3Error

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = "live-data"

def download_latest_time_data(prefix: str = "time_data_", local_dir: str = "/app/statistic_data"):
    """
    从 MinIO 下载最新的统计数据文件 (例如 time_data_20251020.parquet)，
    并重命名为带中划线日期的格式 (例如 time_data_2025-10-20.parquet)。

    参数:
        prefix (str): 文件名前缀（默认 'time_data_'）
        local_dir (str): 本地下载目录（默认 '/app/statistic_data'）

    返回:
        str: 下载到本地的完整文件路径
    """
    try:
        # 初始化客户端
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )

        if not client.bucket_exists(MINIO_BUCKET):
            raise ValueError(f"❌ 桶不存在: {MINIO_BUCKET}")

        # 获取桶中所有符合命名的对象
        objects = client.list_objects(MINIO_BUCKET, recursive=True)
        time_files = [
            obj.object_name for obj in objects
            if obj.object_name.startswith(prefix) and obj.object_name.endswith(".parquet")
        ]

        if not time_files:
            raise FileNotFoundError(f"⚠️ 未找到符合命名规则的文件: {prefix}*.parquet")

        # 提取日期并找到最新文件
        def extract_date(name):
            try:
                date_str = name.replace(prefix, "").replace(".parquet", "")
                return datetime.strptime(date_str, "%Y%m%d")
            except Exception:
                return datetime.min

        latest_file = max(time_files, key=extract_date)
        latest_date = extract_date(latest_file).strftime("%Y-%m-%d")  # 转成带中划线日期

        # 构造本地路径
        os.makedirs(local_dir, exist_ok=True)
        new_filename = f"{prefix}{latest_date}.parquet"
        local_path = os.path.join(local_dir, new_filename)

        # 下载并重命名
        temp_path = os.path.join(local_dir, os.path.basename(latest_file))
        client.fget_object(MINIO_BUCKET, latest_file, temp_path)

        # 重命名（覆盖旧文件）
        if os.path.exists(local_path):
            os.remove(local_path)
        os.rename(temp_path, local_path)

        print(f"✅ 最新数据文件已下载并重命名: {latest_file} → {new_filename}")
        return local_path

    except S3Error as e:
        print(f"❌ MinIO 错误: {e}")
        raise
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        raise

# ==================== 主流程 ====================
from typing import Optional

# 修改 run_loop 签名与 CLI，支持 --debug
def run_loop(parquet_path: Optional[str], one_shot: bool = False, debug: bool = False) -> None:
    download_latest_time_data()
    parquet_path = parquet_path or PATHS.previous_data_path
    stats_all = load_stats_parquet(parquet_path)
    engine = RollingEngine()
    _ensure_name_map(keep=1)  # 关键：仅一次，生成/复用今日 {ts_code->name} 映射文件

    print(f"统计数据加载完成: {len(stats_all):,} 行 @ {parquet_path}")
    print(f"输出目录: {PATHS.save_data_path}")
    print("开始运行，每分钟更新一次...")

    while True:
        wait_next_minute()
        t_str = now_minute_str()
        # if not is_trading_time(t_str):
        #     print(f"[{datetime.now():%H:%M:%S}] 非交易时间，跳过")
        #     if one_shot:
        #         break
        #     continue

        idx = get_trading_index(t_str)
        time_us = time_str_to_us(t_str)
        tick_debug_dir = _prepare_tick_debug_dir(t_str) if debug else None

        snap = fetch_snapshot()
        if not snap:
            print(f"[{t_str}] 快照为空，重试")
            if one_shot:
                break
            continue

        df = pd.DataFrame(snap)
        cols = {
            "Symbol": "code",
            "StockName": "Name",
            "Latest": "Price",
            "ChangePercent": "Chg",
            "TradingVolume": "Vol"
        }
        miss = set(cols.keys()) - set(df.columns)
        if miss:
            print(f"[{t_str}] 快照缺失列: {miss}，跳过")
            if one_shot:
                break
            continue
        df = df[list(cols.keys())].rename(columns=cols)

        if debug and tick_debug_dir:
            df.to_csv(os.path.join(tick_debug_dir, "snapshot.csv"), index=False)

        roll_rows = []
        chg5_map: Dict[str, float] = {}
        chg30_map: Dict[str, float] = {}

        for _, row in df.iterrows():
            code = str(row["code"])
            vol_cum = float(row["Vol"]) if pd.notna(row["Vol"]) else 0.0
            chg = float(row["Chg"]) if pd.notna(row["Chg"]) else 0.0

            win_vals = engine.update_and_get_windows(code, vol_cum, chg)
            roll_rows.append({
                "code": code,
                "rolling1": win_vals["rolling1"],
                "rolling5": win_vals["rolling5"],
                "rolling10": win_vals["rolling10"],
                "rolling30": win_vals["rolling30"],
                "all": win_vals["all"],
            })
            # 原来是 get_chg_delta(差分)，改为窗口求和
            chg5_map[code] = engine.get_chg_delta(code, 5)
            chg30_map[code] = engine.get_chg_delta(code, 30)
        # print(f"chg5_map: {chg5_map}")
        # print(f"chg30_map: {chg30_map}")
        rolling_df = pd.DataFrame(roll_rows).set_index("code")
        if debug and tick_debug_dir:
            rolling_df.to_csv(os.path.join(tick_debug_dir, "rolling.csv"))

        # if debug and tick_debug_dir:
        #     stats_all.to_csv(os.path.join(tick_debug_dir, "stats_all.csv"))
        stats_now = get_stats_for_time(stats_all, time_us)

        if stats_now.empty:
            print(f"[{t_str}] 统计无匹配 time={time_us} 记录，跳过")
            if one_shot:
                break
            continue
        if debug and tick_debug_dir:
            stats_now.to_csv(os.path.join(tick_debug_dir, "stats.csv"))

        z_df = compute_z_scores(rolling_df, stats_now)
        if debug and tick_debug_dir:
            z_df.to_csv(os.path.join(tick_debug_dir, "zscore.csv"))

        out = (
            df.set_index("code")
            .join(rolling_df, how="inner")
            .join(z_df, how="inner")
        ).assign(
            r1_z=lambda x: x["rolling1_z"].round(2),
            r5_z=lambda x: x["rolling5_z"].round(2),
            r10_z=lambda x: x["rolling10_z"].round(2),
            r30_z=lambda x: x["rolling30_z"].round(2),
            rolling_full=lambda x: x["all_z"].round(2),
            Chg5=pd.Series(chg5_map),
            Chg30=pd.Series(chg30_map),
        )

        if "Vol" in out.columns:
            out["Vol"] = np.where(out["Vol"].isna(), out["all"], out["Vol"]).astype(float)
        else:
            out["Vol"] = out["all"].astype(float)

        if debug and tick_debug_dir:
            out.to_csv(os.path.join(tick_debug_dir, "out_full.csv"))

        final_cols = [
            "Name", "Price", "Chg", "Vol",
            "r1_z", "r5_z", "r10_z", "r30_z",
            "rolling_full", "Chg5", "Chg30"
        ]
        final_df = out[final_cols].copy()
        final_df.index.name = "code"
        final_df.sort_values(by="rolling_full", ascending=False, inplace=True)

        if debug and tick_debug_dir:
            final_df.to_csv(os.path.join(tick_debug_dir, "final.csv"))

        records = final_df.reset_index().to_dict(orient="records")
        fp = save_json(records, t_str, idx if idx is not None else -1)
        print(f"[{t_str}] 输出 {len(records)} 条 → {fp}")

        if debug:
            _cleanup_old_debug_dirs(CONFIG.max_keep_groups)

        if one_shot:
            break

from dotenv import load_dotenv
load_dotenv()

# 2) 通用布尔解析函数（放在任意工具函数区）
def getenv_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    v = str(v).strip().lower()
    return v in {"1", "true", "yes", "on", "y", "t"}

# 3) 从 .env 读取开关与参数（放在 CONFIG = TradingConfig() 之后）
ENV_DEBUG = getenv_bool("DEBUG", False)
ENV_ONCE = getenv_bool("ONCE", False) or getenv_bool("ONE_SHOT", False)
ENV_UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", CONFIG.update_interval))
CONFIG.update_interval = ENV_UPDATE_INTERVAL


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Live monitor (new_timely_data)")
    parser.add_argument("--parquet", required=False, help="统计 parquet 文件路径（不传则自动选择最新）")
    parser.add_argument("--once", action="store_true", default=ENV_ONCE, help="仅运行一次（默认从 .env 读取 ONCE）")
    parser.add_argument("--debug", action="store_true", default=ENV_DEBUG, help="调试输出（默认从 .env 读取 DEBUG）")
    args = parser.parse_args()
    run_loop(args.parquet, one_shot=bool(args.once), debug=bool(args.debug))


if __name__ == "__main__":
    main()