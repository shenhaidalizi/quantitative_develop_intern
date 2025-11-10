#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 live_futuresinstruments.dat 提取前 N 个合约 name，输出逗号分隔的 CSV，并打印可直接粘贴到 test_bridge.py 的字节串示例。
默认只选择 is_trading=True 的合约。
"""

import argparse
import json
import sys
from typing import List, Dict, Any


DEFAULT_PATH = "/home/zhousiyuan/ctp_c/demo期货api-6.6.8/demo/live_futuresinstruments.dat"


def load_instruments(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        s = f.read()
    # 该文件首行是日期，JSON 从第一个 '{' 开始
    l = s.find("{")
    r = s.rfind("}")
    if l == -1 or r == -1 or r <= l:
        raise ValueError("无法在文件中定位 JSON 主体")
    body = s[l : r + 1]
    return json.loads(body)


def pick_names(data: Dict[str, Any], n: int, only_trading: bool = True) -> List[str]:
    names: List[str] = []
    for key, meta in data.items():
        if not isinstance(meta, dict):
            continue
        if only_trading and not meta.get("is_trading", False):
            continue
        name = meta.get("name") or key
        if isinstance(name, str):
            names.append(name.strip())
    # 去重、去空、稳定排序后取前 n
    uniq = sorted({x for x in names if x})
    return uniq[:n]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("-p", "--path", default=DEFAULT_PATH, help="live_futuresinstruments.dat 路径")
    p.add_argument("-n", "--num", type=int, default=1500, help="提取数量")
    p.add_argument("--all", action="store_true", help="包含非交易合约（默认只选 is_trading=True）")
    args = p.parse_args()

    try:
        data = load_instruments(args.path)
        names = pick_names(data, args.num, only_trading=not args.all)
    except Exception as e:
        print(f"读取/解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not names:
        print("未找到合约名称", file=sys.stderr)
        sys.exit(2)

    csv_str = ",".join(names)
    # 输出 CSV（供 ctp_md_subscribe 使用）
    print(csv_str)

    # 额外打印便于直接粘贴到 test_bridge.py 的字节串示例
    print("\n# 粘贴到 test_bridge.py 示例：")
    print(f'inst_csv = b"{csv_str}"')
    print("# 使用: lib.ctp_md_subscribe(inst_csv)")


if __name__ == "__main__":
    main()