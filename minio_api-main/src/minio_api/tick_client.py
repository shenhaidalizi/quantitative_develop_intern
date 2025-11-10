# src/minio_api/tick_client.py
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import pandas as pd
import duckdb
from minio import Minio
from minio.error import S3Error

from .config import get_config, MinIOConfig

logger = logging.getLogger(__name__)

class MinIOTickDataClient:
    """
    读取期货 Tick/OrderBook 数据（Parquet），仅返回 DataFrame（DuckDB 版）。
    优先直接读精确文件；不存在时回退到“按天目录通配符”读取。
    路径结构：
      [base_prefix/]/tickly/fut_main/<exchange>/YYYY/MM/DD/<symbol>_<contract_type>.<exchange>.parquet
    """

    def __init__(
        self,
        config: Optional[MinIOConfig] = None,
        bucket_type: str = "data",
        base_prefix: Optional[str] = None,
        **kwargs
    ):
        self.config = config or get_config()
        self.bucket_name = kwargs.get("bucket_name", self.config.get_bucket(bucket_type))

        # DuckDB + httpfs
        self.conn = duckdb.connect()
        self.conn.execute("INSTALL httpfs;")
        self.conn.execute("LOAD httpfs;")

        endpoint = kwargs.get("endpoint", self.config.endpoint)
        access_key = kwargs.get("access_key", self.config.access_key)
        secret_key = kwargs.get("secret_key", self.config.secret_key)
        secure = kwargs.get("secure", self.config.secure)

        endpoint_hostport = endpoint.split("://")[-1]
        self.conn.execute(f"SET s3_endpoint='{endpoint_hostport}';")
        self.conn.execute(f"SET s3_access_key_id='{access_key}';")
        self.conn.execute(f"SET s3_secret_access_key='{secret_key}';")
        self.conn.execute(f"SET s3_use_ssl={'true' if secure else 'false'};")
        self.conn.execute("SET s3_url_style='path';")

        # MinIO 客户端（用于存在性检查、列目录）
        self.mcli = Minio(endpoint=endpoint_hostport, access_key=access_key, secret_key=secret_key, secure=secure)

        env_prefix = os.getenv("MINIO_TICK_PREFIX", "")
        self.base_prefix = (base_prefix if base_prefix is not None else env_prefix).strip("/")
        logger.info(f"DuckDB Tick Client ready. bucket={self.bucket_name}, base_prefix='{self.base_prefix}', endpoint={endpoint_hostport}")

    def _parse_ticker(self, ticker: str):
        parts = ticker.split(".")
        if len(parts) != 2:
            raise ValueError(f"ticker格式不正确，应为 symbol_contract_type.exchange，实际: {ticker}")
        exchange = parts[1]
        symbol_contract = parts[0]
        if "_" in symbol_contract:
            symbol, contract_type = symbol_contract.rsplit("_", 1)
        else:
            symbol, contract_type = symbol_contract, "1"
        return symbol, contract_type, exchange

    def _date_path(self, yyyymmdd: str) -> str:
        return f"{yyyymmdd[:4]}/{yyyymmdd[4:6]}/{yyyymmdd[6:8]}"

    def _prefix_root(self) -> str:
        return f"{self.base_prefix}/" if self.base_prefix else ""

    def _object_path(self, ticker: str, yyyymmdd: str) -> str:
        symbol, contract_type, exchange = self._parse_ticker(ticker)
        return f"{self._prefix_root()}tickly/fut_main/{exchange}/{self._date_path(yyyymmdd)}/{symbol}_{contract_type}.{exchange}.parquet"

    def _day_prefix(self, exchange: str, yyyymmdd: str) -> str:
        return f"{self._prefix_root()}tickly/fut_main/{exchange}/{self._date_path(yyyymmdd)}/"

    def _s3_uri(self, object_path: str) -> str:
        return f"s3://{self.bucket_name}/{object_path}"

    def _object_exists(self, object_path: str) -> bool:
        try:
            self.mcli.stat_object(self.bucket_name, object_path)
            return True
        except S3Error as e:
            if getattr(e, "code", "") == "NoSuchKey":
                return False
            logger.debug(f"stat_object失败({self.bucket_name}/{object_path}): {e}")
            return False
        except Exception:
            return False

    def _list_day_parquets(self, exchange: str, yyyymmdd: str) -> List[str]:
        day_prefix = self._day_prefix(exchange, yyyymmdd)
        objs = self.mcli.list_objects(self.bucket_name, prefix=day_prefix, recursive=False)
        names = []
        for o in objs:
            if o.object_name.endswith(".parquet"):
                names.append(o.object_name)
        return names

    def _detect_schema(self, uri: str) -> Tuple[Optional[str], List[str]]:
        try:
            cols = self.conn.execute(f"SELECT * FROM read_parquet('{uri}') LIMIT 0").df().columns.tolist()
            time_col = None
            for cand in ("modify_dt", "datetime"):
                if cand in cols:
                    time_col = cand
                    break
            return time_col, cols
        except Exception as e:
            logger.debug(f"检测schema失败: {uri}, 错误: {e}")
            return None, []

    def _query_files(
        self,
        uris: List[str],
        start_time: str,
        end_time: str,
        symbol: Optional[str] = None,
        contract_type: Optional[str] = None
    ) -> pd.DataFrame:
        if not uris:
            return pd.DataFrame()

        time_col, cols = self._detect_schema(uris[0])
        if not time_col:
            return pd.DataFrame()

        conds = [f"strftime({time_col}, '%H:%M:%S.%f') >= '{start_time}'",
                f"strftime({time_col}, '%H:%M:%S.%f') <= '{end_time}'"]
        if symbol and ("symbol" in cols):
            conds.append(f"CAST(symbol AS VARCHAR) = '{symbol}'")
        if contract_type and ("contract_type" in cols):
            conds.append(f"CAST(contract_type AS VARCHAR) = '{contract_type}'")
        where_sql = " AND ".join(conds)

        uris_sql = "', '".join(uris)
        sql = f"""
        SELECT * FROM read_parquet(['{uris_sql}'])
        WHERE {where_sql}
        ORDER BY {time_col} ASC
        """
        try:
            df = self.conn.execute(sql).df()
            if df is None or df.empty:
                return pd.DataFrame()

            # 数值列标准化（可选）
            numeric_cols = ["last", "volume", "open_interest", "turnover"]
            for i in range(1, 6):
                numeric_cols += [f"bid{i}", f"ask{i}", f"bid_vol{i}", f"ask_vol{i}"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception as e:
            logger.error(f"DuckDB查询失败: {e}")
            return pd.DataFrame()

    def _query_day_wildcard(self, ticker: str, the_date: str, start_time: str, end_time: str) -> pd.DataFrame:
        symbol, contract_type, exchange = self._parse_ticker(ticker)
        # 先列目录，避免空目录下的通配符导致错误
        names = self._list_day_parquets(exchange, the_date)
        if not names:
            return pd.DataFrame()
        uris = [self._s3_uri(n) for n in names]
        return self._query_files(uris, start_time, end_time, symbol=symbol, contract_type=contract_type)

    def fetch(self, ticker: str, the_date: str, start_time: str, end_time: str, data_type: str = "tick") -> pd.DataFrame:
        """
        获取单日数据：先精确文件，缺失则回退到“按天目录通配符”
        """
        object_path = self._object_path(ticker, the_date)
        if self._object_exists(object_path):
            uri = self._s3_uri(object_path)
            return self._query_files([uri], start_time, end_time)
        # 回退
        return self._query_day_wildcard(ticker, the_date, start_time, end_time)

    def fetch_range(self, ticker: str, start_date: str, end_date: str, start_time: str, end_time: str, data_type: str = "tick") -> pd.DataFrame:
        """
        获取多日区间数据：
          - 现有精确文件用一次SQL批量读；
          - 缺失的日期逐日用“按天目录通配符”补齐；
        """
        try:
            sd = datetime.strptime(start_date, "%Y%m%d")
            ed = datetime.strptime(end_date, "%Y%m%d")
        except Exception:
            raise ValueError("日期格式错误，应为 YYYYMMDD")

        symbol, contract_type, exchange = self._parse_ticker(ticker)

        existing_uris: List[str] = []
        fallback_dfs: List[pd.DataFrame] = []

        d = sd
        while d <= ed:
            yyyymmdd = d.strftime("%Y%m%d")
            object_path = self._object_path(ticker, yyyymmdd)
            if self._object_exists(object_path):
                existing_uris.append(self._s3_uri(object_path))
            else:
                # 用“按天目录通配符”回退
                df_day = self._query_day_wildcard(ticker, yyyymmdd, start_time, end_time)
                if df_day is not None and not df_day.empty:
                    fallback_dfs.append(df_day)
            d += timedelta(days=1)

        dfs: List[pd.DataFrame] = []
        if existing_uris:
            df_main = self._query_files(existing_uris, start_time, end_time)
            if df_main is not None and not df_main.empty:
                dfs.append(df_main)
        if fallback_dfs:
            dfs.extend(fallback_dfs)

        if not dfs:
            return pd.DataFrame()

        merged = pd.concat(dfs, ignore_index=True)
        # 排序：优先使用时间列
        time_col = "modify_dt" if "modify_dt" in merged.columns else ("datetime" if "datetime" in merged.columns else None)
        if time_col:
            sort_cols = []
            if "date" in merged.columns:
                sort_cols.append("date")
            sort_cols.append(time_col)
            merged = merged.sort_values(sort_cols)
        return merged


def get_tick_data_from_minio(
    ticker: str,
    start_date: str,
    end_date: str,
    start_time: str = "09:00:00",
    end_time: str = "15:00:00",
    data_type: str = "tick",
    config: Optional[MinIOConfig] = None,
    base_prefix: Optional[str] = None,
) -> pd.DataFrame:
    """
    便捷函数：直接取多日或单日 DataFrame
    """
    client = MinIOTickDataClient(config=config, base_prefix=base_prefix)
    if start_date == end_date:
        return client.fetch(ticker, start_date, start_time, end_time, data_type=data_type)
    return client.fetch_range(ticker, start_date, end_date, start_time, end_time, data_type=data_type)