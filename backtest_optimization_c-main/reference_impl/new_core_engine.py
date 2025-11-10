import numpy as np
import time
from typing import Tuple
from core_engine_vectorized import run_multi_weight_vectorized as run_multi_weight_vectorized_core

MODE_PORTFOLIO_PCT = 0
MODE_CASH_ALL = 1
MODE_FIXED = 2
MODE_FIXED_CASH = 3

def _mode_to_id(mode: str) -> int:
    if mode == "portfolio_pct":
        return MODE_PORTFOLIO_PCT
    if mode == "cash_all":
        return MODE_CASH_ALL
    if mode == "fixed":
        return MODE_FIXED
    if mode == "fixed_cash":
        return MODE_FIXED_CASH
    return MODE_PORTFOLIO_PCT


def run_multi_weight_vectorized( 
    prices: np.ndarray,
    position_matrix: np.ndarray,
    initial_cash: float = 1000000.0,
    trade_mode: str = "portfolio_pct",
    max_allocation_pct: float = 0.5,
    fixed_cash_amount: float = 100000.0,
    position_size: float = 100.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    多权重回测引擎 - 向量化版本（原版实现）
    
    完全复制原始 candle.py 的向量化逻辑，用于：
    1. 性能基准对比
    2. 验证 C++ 实现正确性
    
    Args:
        prices: (n_timestamps,) 价格序列
        position_matrix: (n_timestamps, n_weights) 持仓信号矩阵 {-1, 0, 1}
        initial_cash: 初始资金
        trade_mode: 交易模式
            - "fixed": 固定仓位大小
            - "cash_all": 全部可用现金买入
            - "portfolio_pct": 组合价值的固定比例分配
            - "fixed_cash": 每次交易固定金额
        max_allocation_pct: 最大仓位比例（仅 portfolio_pct 模式）
        fixed_cash_amount: 固定交易金额（仅 fixed_cash 模式）
        position_size: 固定仓位大小（仅 fixed 模式）
    
    Returns:
        portfolio_value_matrix: (n_timestamps, n_weights) 组合价值矩阵
        cash_matrix: (n_timestamps, n_weights) 现金矩阵
        real_position_matrix: (n_timestamps, n_weights) 实际持仓数量矩阵
    """
    prices = np.asarray(prices, dtype=np.float32)
    position_matrix = np.ascontiguousarray(position_matrix)  # 不强制类型，支持 int8/float32 等

    n_timestamps = prices.shape[0]
    n_weights = position_matrix.shape[1]

    
    # 输入验证
    if position_matrix.shape[0] != n_timestamps:
        raise ValueError(f"持仓矩阵时间步数不匹配: {position_matrix.shape[0]} vs {n_timestamps}")
    

    # 初始化输出矩阵（使用原版变量名）
    cash_matrix = np.zeros((n_timestamps, n_weights), dtype=np.float32)
    real_position_matrix = np.zeros((n_timestamps, n_weights), dtype=np.float32)  # 实际持仓数量
    portfolio_value_matrix = np.zeros((n_timestamps, n_weights), dtype=np.float32)


    # 初始化第一行
    cash_matrix[0].fill(np.float32(initial_cash))
    portfolio_value_matrix[0].fill(np.float32(initial_cash))

    # 循环外预分配缓冲，避免反复分配
    pos_change = np.empty(n_weights, dtype=position_matrix.dtype)
    buys_mask = np.empty(n_weights, dtype=bool)
    sells_mask = np.empty(n_weights, dtype=bool)
    buy_qty = np.empty(n_weights, dtype=np.float32)
    max_afford = np.empty(n_weights, dtype=np.float32)
    tmp = np.empty(n_weights, dtype=np.float32)
    tmp2 = np.empty(n_weights, dtype=np.float32)



  
    mode_id = _mode_to_id(trade_mode)
    # 向量化处理所有时间点
    for idx in range(1, n_timestamps):
        # 视图（不分配）
        prev_cash = cash_matrix[idx - 1]
        cash = cash_matrix[idx]
        prev_pos = real_position_matrix[idx - 1]
        pos = real_position_matrix[idx]

        # 继承状态（原地拷贝）
        np.copyto(cash, prev_cash)
        np.copyto(pos, prev_pos)

        # 本行持仓变化与买卖掩码（按行计算、原地）
        np.subtract(position_matrix[idx], position_matrix[idx - 1], out=pos_change)
        np.greater(pos_change, 0, out=buys_mask)
        np.less(pos_change, 0, out=sells_mask)

        has_buys = bool(buys_mask.any())
        has_sells = bool(sells_mask.any())
        price32 = prices[idx]

        # 买入
        if has_buys:
            if mode_id == MODE_FIXED:
                buy_qty.fill(np.float32(position_size))

            elif mode_id == MODE_CASH_ALL:
                np.divide(cash, price32, out=buy_qty)
                np.floor(buy_qty, out=buy_qty)

            elif mode_id == MODE_PORTFOLIO_PCT:
                # portfolio_val = cash + pos * price
                np.multiply(pos, price32, out=tmp)                       # tmp = pos * price
                np.add(cash, tmp, out=tmp)                               # tmp = portfolio_val
                np.multiply(tmp, np.float32(max_allocation_pct), out=buy_qty)
                np.divide(buy_qty, price32, out=buy_qty)                 # buy_qty = portfolio_val*pct/price
                np.floor(buy_qty, out=buy_qty)                           # floor(max_pos)
                np.subtract(buy_qty, pos, out=buy_qty)                   # buy_qty = max_pos - pos
                np.divide(cash, price32, out=max_afford)
                np.floor(max_afford, out=max_afford)
                np.maximum(buy_qty, 0.0, out=buy_qty)
                np.minimum(buy_qty, max_afford, out=buy_qty)

            elif mode_id == MODE_FIXED_CASH:
                buy_qty.fill(np.floor(np.float32(fixed_cash_amount) / price32))

            else:
                buy_qty.fill(np.float32(position_size))

            # 现金上限再约束一次
            np.divide(cash, price32, out=max_afford)
            np.floor(max_afford, out=max_afford)
            np.minimum(buy_qty, max_afford, out=buy_qty)

            # 仅对买入信号生效（掩码原地零化）
            np.multiply(buy_qty, buys_mask, out=buy_qty)

            # 现金与头寸更新（原地）
            np.multiply(buy_qty, price32, out=tmp)   # tmp = buy_cost
            np.subtract(cash, tmp, out=cash)
            np.add(pos, buy_qty, out=pos)

        # 卖出
        if has_sells:
            np.multiply(prev_pos, sells_mask, out=tmp2)  # tmp2 = sell_qty
            np.multiply(tmp2, price32, out=tmp)          # tmp = sell_revenue
            np.add(cash, tmp, out=cash)
            np.subtract(pos, tmp2, out=pos)

        # 组合价值
        np.multiply(pos, price32, out=tmp)
        np.add(cash, tmp, out=portfolio_value_matrix[idx])

    return portfolio_value_matrix, cash_matrix, real_position_matrix


if __name__ == "__main__":
    import time
    import os
    np.random.seed(42)
    
    # 生成测试数据
    n_timestamps = 100000
    n_weights = 10000
    
    prices = (np.cumsum(np.random.randn(n_timestamps) * 0.01) + 100).astype(np.float32)
    prices = np.maximum(prices, 1.0)
    
    positions = np.random.choice([-1, 0, 1], size=(n_timestamps, n_weights)).astype(np.int8)
    trade_mode="portfolio_pct"
    # 运行向量化回测
    print("=== 向量化回测测试 ===")
    start = time.perf_counter()
    portfolio, cash, qty = run_multi_weight_vectorized(
        prices, positions, 
        initial_cash=1000000.0,
        trade_mode=trade_mode,
        max_allocation_pct=0.5
    )
    elapsed = time.perf_counter() - start
    
    print(f"耗时: {elapsed*1000:.2f} ms")
    print(f"Portfolio values shape: {portfolio.shape}")
    print(f"Initial portfolio value: {portfolio[0, 0]:.2f}")
    print(f"Final portfolio values (前3个): {portfolio[-1, :3]}")
    
    # 验证组合价值计算
    final_check = cash[-1] + qty[-1] * prices[-1]
    assert np.allclose(portfolio[-1], final_check), "组合价值计算错误"
    print("✓ 组合价值验证通过")
    
    # # ✨ 新增：保存结果到文件
    # output_dir = "output/"
    # os.makedirs(output_dir, exist_ok=True)
    
    # output_file = os.path.join(output_dir, "python_vectorized_output.npz")
    # np.savez_compressed(
    #     output_file,
    #     # 输入数据
    #     prices=prices,
    #     positions=positions,
    #     # 配置参数
    #     initial_cash=np.array([1000000.0]),
    #     trade_mode=np.array([trade_mode]),
    #     max_allocation_pct=np.array([0.5]),
    #     # 输出结果
    #     portfolio_values=portfolio,
    #     cash_matrix=cash,
    #     quantity_matrix=qty,
    #     # 元数据
    #     n_timestamps=np.array([n_timestamps]),
    #     n_weights=np.array([n_weights]),
    #     elapsed_time_ms=np.array([elapsed * 1000])
    # )
    # print(f"\n✓ 结果已保存到: {output_file}")
    
    # 对比简化版
    print("\n=== 性能对比 ===")
    # from core_engine import run_backtest_python
    
    start = time.perf_counter()
    portfolio2, cash2, qty2 = run_multi_weight_vectorized_core(
        prices, positions, 
        initial_cash=1000000.0,
        trade_mode="portfolio_pct",
        max_allocation_pct=0.5
    )
    elapsed2 = time.perf_counter() - start
    
    print(f"简化版耗时: {elapsed2*1000:.2f} ms")
    print(f"向量化版耗时: {elapsed*1000:.2f} ms")
    print(f"加速比: {elapsed2/elapsed:.2f}x")
    
    # 验证结果一致性
    max_error = np.abs(portfolio - portfolio2).max()
    print(f"\n数值误差: {max_error:.2e}")
    if max_error < 1e-4:
        print("✓ 两个版本结果一致")
    else:
        print("⚠ 两个版本结果有差异")
    
    # # ✨ 新增：保存简化版结果
    # output_file2 = os.path.join(output_dir, "python_simple_output.npz")
    # np.savez_compressed(
    #     output_file2,
    #     portfolio_values=portfolio2,
    #     cash_matrix=cash2,
    #     quantity_matrix=qty2,
    #     elapsed_time_ms=np.array([elapsed2 * 1000])
    # )
    # print(f"\n✓ 简化版结果已保存到: {output_file2}")