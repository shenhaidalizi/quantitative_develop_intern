#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
示例: 读取 MinIO 上 info/ 与 manual_files/ 的本地辅助数据

本示例展示以下便捷函数的使用：
 - get_code_list / get_basicacc_code_list
 - get_index_list / get_fund_code_list / get_fut_main_code_list
 - get_us_code_list / get_star_list
 - get_basic_df / get_code_dict

运行前，请确保已配置以下环境变量（或在项目根目录提供 .env）：
 - MINIO_ENDPOINT
 - MINIO_ACCESS_KEY
 - MINIO_SECRET_KEY
 - MINIO_BUCKET_TRADER_DATA（localdata 使用，例如 trader-data，对象路径 trader-data/info/...）
可选：MINIO_BUCKET_DATA（parquet 日线数据，默认 stock-data）
"""

import sys
from typing import Mapping, Sequence

from minio_api.config import get_config
import minio_api.localdata as localdata


def _print_list_preview(title: str, items: Sequence[str], limit: int = 10) -> None:
    count = 0 if items is None else len(items)
    print(f"\n{title}: 共 {count} 条")
    if count:
        preview = list(items)[:limit]
        print("示例:", ", ".join(preview))


def _print_dict_preview(title: str, data: Mapping[str, dict], limit: int = 3) -> None:
    size = 0 if data is None else len(data)
    print(f"\n{title}: 共 {size} 项")
    if size:
        keys = sorted(data.keys())[:limit]
        for k in keys:
            print(f"- {k}: {data[k]}")


def _ensure_minio_config() -> bool:
    try:
        cfg = get_config()
        # 触发属性访问进行基本校验
        _ = cfg.endpoint
        _ = cfg.bucket_data
        print(
            "已加载 MinIO 配置: "
            f"endpoint={cfg.endpoint}, data_bucket={cfg.bucket_data}, "
            f"trader_data_bucket={cfg.get_bucket('trader_data')}"
        )
        return True
    except Exception as e:
        print("未正确配置 MinIO 环境变量，请设置 MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY。", file=sys.stderr)
        print(f"错误: {e}", file=sys.stderr)
        return False


def main() -> None:
    if not _ensure_minio_config():
        return

    # 代码列表（示例：过滤上交所，且上市日期不晚于 2010-01-01）
    codes = localdata.get_code_list(exclude_exch_list=["SH"], list_date_before="20100101")
    _print_list_preview("A股代码（排除SH，上市<=20100101）", codes)

    # 基础板块（剔除科创/创业/中小）
    basicacc_codes = localdata.get_basicacc_code_list()
    _print_list_preview("A股基础板块代码", basicacc_codes)

    # 指数列表
    idx_all = localdata.get_index_list("all")
    _print_list_preview("指数列表（ALL）", idx_all)
    idx_sz = localdata.get_index_list(["SZ"])
    _print_list_preview("指数列表（仅SZ）", idx_sz)

    # 基金、期货主力
    fund_codes = localdata.get_fund_code_list()
    _print_list_preview("基金代码", fund_codes)
    fut_main = localdata.get_fut_main_code_list()
    _print_list_preview("期货主力合约代码", fut_main)

    # 美股代码与自选列表
    us_codes = localdata.get_us_code_list()
    _print_list_preview("美股代码", us_codes)
    stars = localdata.get_star_list()
    _print_list_preview("自选/星标列表", stars)

    # 基础信息与代码字典
    df_basic = localdata.get_basic_df()
    print(f"\n基础信息DataFrame: shape={getattr(df_basic, 'shape', None)}")
    if getattr(df_basic, 'empty', True) is False:
        try:
            print(df_basic.head().to_string())
        except Exception:
            print(str(df_basic.head()))

    code_map = localdata.get_code_dict()
    _print_dict_preview("代码字典", code_map, limit=3)


if __name__ == "__main__":
    main()


