# 文件：/home/ubuntu/TradeNew/infra/open/minio_api/src/minio_api/minute_client.py
import os
import logging
from typing import Optional, Union, List, Callable, Any

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.fs as pafs

from .config import get_config, MinIOConfig

logger = logging.getLogger(__name__)


def _default_minute_schema() -> pa.Schema:
    # 与 data_dev 中的 MINUTE_KLINE_SCHEMA 对齐
    return pa.schema([
        pa.field("ts_code", pa.string()),
        pa.field("trade_time", pa.timestamp("ms")),
        pa.field("open", pa.float64()),
        pa.field("high", pa.float64()),
        pa.field("low", pa.float64()),
        pa.field("close", pa.float64()),
        pa.field("vol", pa.float64()),
        pa.field("amount", pa.float64()),
        pa.field("pre_close", pa.float64()),
    ])


class MinIOMinuteDataClient:
    """
    从 MinIO 上读取按 Hive(year=/month=) 分区的分钟级 Parquet（PyArrow Dataset 版）。

    目录结构示例：
      s3://{bucket}/{base_prefix}/year=YYYY/month=MM/consolidated.parquet

    过滤字段：
      - 符号列：ts_code
      - 时间列：trade_time (timestamp(ms))
      - 分区列：year(int32), month(int32)
    """

    def __init__(
        self,
        config: Optional[MinIOConfig] = None,
        bucket_type: str = "data",
        base_prefix: Optional[str] = None,
        schema: Optional[pa.Schema] = None,
        builder: Optional[Callable[[pd.Series], Any]] = None,
        **kwargs,
    ):
        self.config = config or get_config()
        self.bucket_name = kwargs.get("bucket_name", self.config.get_bucket(bucket_type))
        # 可通过环境变量覆盖，如：MINIO_MINUTE_PREFIX=minutely/cnstock
        env_prefix = os.getenv("MINIO_MINUTE_PREFIX", "")
        self.base_prefix = (base_prefix if base_prefix is not None else env_prefix).strip("/")

        # 文件内 schema（不含分区列）
        self.file_schema = schema or _default_minute_schema()
        # 可选的构造器，用于 output_type='list' 时构建对象（如 MinuteKLineData）
        self.builder = builder

        # 构造 PyArrow 的 S3 FileSystem（MinIO 兼容）
        endpoint = self.config.endpoint  # 形如 "localhost:9000" 或 "minio:9000"
        secure = self.config.secure
        endpoint_override = f"http{'s' if secure else ''}://{endpoint}"

        self.s3fs = pafs.S3FileSystem(
            access_key=self.config.access_key,
            secret_key=self.config.secret_key,
            endpoint_override=endpoint_override,
        )

        logger.info(
            f"MinIOMinuteDataClient ready. bucket={self.bucket_name}, "
            f"base_prefix='{self.base_prefix}', endpoint={endpoint_override}"
        )

    def _root_uri(self) -> str:
        if self.base_prefix:
            return f"{self.bucket_name}/{self.base_prefix}"
        return f"{self.bucket_name}"

    def _partitioning(self) -> ds.Partitioning:
        # 分区列 year/month（int32）
        partition_schema = pa.schema([
            pa.field("year", pa.int32()),
            pa.field("month", pa.int32()),
        ])
        return ds.partitioning(partition_schema, flavor="hive")

    def _full_schema(self) -> pa.Schema:
        # 数据列 + 分区列
        return pa.schema(list(self.file_schema) + list(self._partitioning().schema))

    def _build_dataset(self) -> ds.Dataset:
        # 指向分区根目录（包含 year=/month= 子目录）
        return ds.dataset(
            self._root_uri(),
            filesystem=self.s3fs,
            format="parquet",
            schema=self._full_schema(),
            partitioning=self._partitioning(),
        )

    @staticmethod
    def _validate_output_type(output_type: str):
        if output_type not in ("df", "list"):
            raise ValueError("Unsupported output_type, choose 'df' or 'list'.")

    def _apply_filter_and_collect(
        self,
        dataset: ds.Dataset,
        filter_cond,
        output_type: str,
    ):
        table = dataset.to_table(filter=filter_cond)
        df = table.to_pandas()
        if df.empty:
            return df if output_type == "df" else []

        # 排序
        if "trade_time" in df.columns:
            df.sort_values("trade_time", inplace=True)

        if output_type == "df":
            return df

        # output_type == 'list'
        if self.builder is None:
            raise ValueError("output_type='list' 需要在初始化时提供 builder 可调用对象。")
        items = []
        for _, row in df.iterrows():
            items.append(self.builder(row))
        return items

    def fetch_minute_data(
        self,
        symbol: Union[str, List[str], None],
        start_datetime: str,
        end_datetime: str,
        output_type: str = "df",
    ):
        """
        精确到时间戳区间的分钟数据读取。

        Args:
            symbol: 单个 ts_code、ts_code 列表、'all'/None
            start_datetime: 形如 "YYYY-MM-DD HH:MM:SS"
            end_datetime: 形如 "YYYY-MM-DD HH:MM:SS"
            output_type: 'df' | 'list'
        """
        self._validate_output_type(output_type)

        try:
            start_ts = pd.to_datetime(start_datetime, errors="raise")
            end_ts = pd.to_datetime(end_datetime, errors="raise")
        except Exception as e:
            raise ValueError(f"Invalid datetime format: {e}") from e

        # 分区裁剪条件：year/month（尽可能缩小扫描范围）
        year_field = ds.field("year")
        month_field = ds.field("month")
        start_year, start_month = start_ts.year, start_ts.month
        end_year, end_month = end_ts.year, end_ts.month

        partition_filter = (
            ((year_field.cast("int32") > start_year) |
             ((year_field.cast("int32") == start_year) & (month_field.cast("int32") >= start_month)))
            &
            ((year_field.cast("int32") < end_year) |
             ((year_field.cast("int32") == end_year) & (month_field.cast("int32") <= end_month)))
        )

        # 数据条件
        time_filter = (
            (ds.field("trade_time") >= pa.scalar(start_ts, type=pa.timestamp("ms"))) &
            (ds.field("trade_time") <= pa.scalar(end_ts, type=pa.timestamp("ms")))
        )
        if symbol in ("all", None) or (isinstance(symbol, list) and len(symbol) == 0):
            symbol_filter = None
        elif isinstance(symbol, list):
            symbol_filter = ds.field("ts_code").isin(symbol)
        else:
            symbol_filter = (ds.field("ts_code") == symbol)

        data_filter = time_filter if symbol_filter is None else (time_filter & symbol_filter)
        filter_cond = partition_filter & data_filter

        dataset = self._build_dataset()
        return self._apply_filter_and_collect(dataset, filter_cond, output_type)

    def fetch_daily_data(
        self,
        symbol: Union[str, List[str], None],
        start_date: str,
        end_date: str,
        output_type: str = "df",
    ):
        """
        以日期区间读取（按天，上下界自动扩展到全天）。
        start_date/end_date: 形如 "YYYYMMDD"
        """
        self._validate_output_type(output_type)

        try:
            start_ts = pd.to_datetime(start_date, format="%Y%m%d", errors="raise")
            end_ts = pd.to_datetime(end_date, format="%Y%m%d", errors="raise")
            # 扩到全天
            end_ts = end_ts.replace(hour=23, minute=59, second=59, microsecond=999000)
        except Exception as e:
            raise ValueError(f"Invalid date format: {e}") from e

        year_field = ds.field("year")
        month_field = ds.field("month")
        start_year, start_month = start_ts.year, start_ts.month
        end_year, end_month = end_ts.year, end_ts.month

        partition_filter = (
            ((year_field.cast("int32") > start_year) |
             ((year_field.cast("int32") == start_year) & (month_field.cast("int32") >= start_month)))
            &
            ((year_field.cast("int32") < end_year) |
             ((year_field.cast("int32") == end_year) & (month_field.cast("int32") <= end_month)))
        )

        time_filter = (
            (ds.field("trade_time") >= pa.scalar(start_ts, type=pa.timestamp("ms"))) &
            (ds.field("trade_time") <= pa.scalar(end_ts, type=pa.timestamp("ms")))
        )
        if symbol in ("all", None) or (isinstance(symbol, list) and len(symbol) == 0):
            symbol_filter = None
        elif isinstance(symbol, list):
            symbol_filter = ds.field("ts_code").isin(symbol)
        else:
            symbol_filter = (ds.field("ts_code") == symbol)

        data_filter = time_filter if symbol_filter is None else (time_filter & symbol_filter)
        filter_cond = partition_filter & data_filter

        dataset = self._build_dataset()
        return self._apply_filter_and_collect(dataset, filter_cond, output_type)


def get_minute_data_from_minio(
    symbol: Union[str, List[str], None],
    start: str,
    end: str,
    *,
    by: str = "datetime",  # 'datetime' | 'date'
    output_type: str = "df",
    config: Optional[MinIOConfig] = None,
    bucket_type: str = "data",
    base_prefix: Optional[str] = 'minutely',
    builder: Optional[Callable[[pd.Series], Any]] = None,
) -> Union[pd.DataFrame, List[Any]]:
    """
    便捷函数：
      - symbol=None/"all": 读取所有股票数据.
      - by='datetime': start/end 传 "YYYY-MM-DD HH:MM:SS"
      - by='date':     start/end 传 "YYYYMMDD"
    """
    client = MinIOMinuteDataClient(
        config=config,
        bucket_type=bucket_type,
        base_prefix=base_prefix,
        builder=builder,
    )
    if by == "datetime":
        return client.fetch_minute_data(symbol, start, end, output_type=output_type)
    elif by == "date":
        return client.fetch_daily_data(symbol, start, end, output_type=output_type)
    else:
        raise ValueError("by 参数仅支持 'datetime' 或 'date'")