"""
回测引擎核心 - 向量化版本（原版逻辑）

完全复制自: src/trader_backtest/engine/candle.py:run_multi_weight()
用于性能对比和验证 C++ 实现的正确性
"""
import numpy as np
from typing import Tuple


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
    n_timestamps = len(prices)
    n_weights = position_matrix.shape[1]
    print(f"n_timestamps: {n_timestamps}, n_weights: {n_weights}")
    # exit()
    # 输入验证
    if position_matrix.shape[0] != n_timestamps:
        raise ValueError(f"持仓矩阵时间步数不匹配: {position_matrix.shape[0]} vs {n_timestamps}")
    
    # 初始化输出矩阵（使用原版变量名）
    cash_matrix = np.zeros((n_timestamps, n_weights), dtype=np.float32)
    real_position_matrix = np.zeros((n_timestamps, n_weights), dtype=np.float32)  # 实际持仓数量
    portfolio_value_matrix = np.zeros((n_timestamps, n_weights), dtype=np.float32)
    
    # 初始化第一行
    cash_matrix[0, :] = initial_cash
    portfolio_value_matrix[0, :] = initial_cash
    
    # 计算持仓变化矩阵
    position_change_matrix = np.diff(
        np.vstack([np.zeros((1, n_weights)), position_matrix]), 
        axis=0
    )
    
    # 向量化处理所有时间点
    for idx in range(1, n_timestamps):
        # 继承前一时间点状态
        cash_matrix[idx] = cash_matrix[idx-1]
        real_position_matrix[idx] = real_position_matrix[idx-1]
        
        # 处理持仓变化
        buys = position_change_matrix[idx] > 0
        sells = position_change_matrix[idx] < 0
        
        if np.any(buys) or np.any(sells):
            price = prices[idx]
            
            # 买入处理（向量化）
            if np.any(buys):
                # 根据交易模式决定买入数量
                if trade_mode == "fixed":
                    # 原有模式：固定仓位大小
                    buy_positions = np.ones(n_weights) * position_size
                
                elif trade_mode == "cash_all":
                    # 方式1：全部可用现金买入
                    buy_positions = np.floor(cash_matrix[idx] / price)
                
                elif trade_mode == "portfolio_pct":
                    # 方式2：考虑投资组合最大分配比例
                    portfolio_value = cash_matrix[idx] + real_position_matrix[idx] * price
                    max_position = np.floor(portfolio_value * max_allocation_pct / price)
                    buy_positions = np.maximum(0, np.minimum(
                        max_position - real_position_matrix[idx],
                        np.floor(cash_matrix[idx] / price)
                    ))
                
                elif trade_mode == "fixed_cash":
                    # 方式3：固定现金金额
                    buy_positions = np.floor(fixed_cash_amount / price)
                
                else:
                    # 默认使用固定仓位
                    buy_positions = np.ones(n_weights) * position_size
                
                # 只对买入信号的位置计算
                buy_positions[~buys] = 0
                
                # 确保不会使现金变为负数
                max_affordable = np.floor(cash_matrix[idx] / price)
                buy_positions = np.minimum(buy_positions, max_affordable)
                
                # 买入成本
                buy_cost = buy_positions * price
                cash_matrix[idx, buys] -= buy_cost[buys]
                real_position_matrix[idx, buys] += buy_positions[buys]
            
            # 卖出处理（向量化）
            if np.any(sells):
                sell_volumes = real_position_matrix[idx-1, sells]
                
                # 卖出收益
                sell_revenue = sell_volumes * price
                cash_matrix[idx, sells] += sell_revenue
                real_position_matrix[idx, sells] = 0
        
        # 更新组合价值
        portfolio_value_matrix[idx] = cash_matrix[idx] + real_position_matrix[idx] * prices[idx]
    
    return portfolio_value_matrix, cash_matrix, real_position_matrix


# import numpy as np
# import time
# from candle import run_multi_weight_vectorized  # 原 Python 函数

# # 构造测试数据
# n_timestamps = 10000
# n_weights = 500
# prices = np.random.rand(n_timestamps).astype(np.float32) * 100
# position_matrix = np.random.randint(-1, 2, size=(n_timestamps, n_weights)).astype(np.float32)

# start_time = time.time()
# portfolio, cash, real_pos = run_multi_weight_vectorized(prices, position_matrix)
# end_time = time.time()
# print(f"Python 原函数耗时: {end_time - start_time:.3f} 秒")


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
    
    # ✨ 新增：保存结果到文件
    output_dir = "output/"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "python_vectorized_output.npz")
    np.savez_compressed(
        output_file,
        # 输入数据
        prices=prices,
        positions=positions,
        # 配置参数
        initial_cash=np.array([1000000.0]),
        trade_mode=np.array([trade_mode]),
        max_allocation_pct=np.array([0.5]),
        # 输出结果
        portfolio_values=portfolio,
        cash_matrix=cash,
        quantity_matrix=qty,
        # 元数据
        n_timestamps=np.array([n_timestamps]),
        n_weights=np.array([n_weights]),
        elapsed_time_ms=np.array([elapsed * 1000])
    )
    print(f"\n✓ 结果已保存到: {output_file}")
    
    # 对比简化版
    # print("\n=== 性能对比 ===")
    # from core_engine import run_backtest_python
    
    # start = time.perf_counter()
    # portfolio2, cash2, qty2 = run_backtest_python(
    #     prices, positions, 
    #     initial_cash=1000000.0,
    #     trade_mode="portfolio_pct",
    #     max_allocation_pct=0.5
    # )
    # elapsed2 = time.perf_counter() - start
    
    # print(f"简化版耗时: {elapsed2*1000:.2f} ms")
    print(f"向量化版耗时: {elapsed*1000:.2f} ms")
    # print(f"加速比: {elapsed2/elapsed:.2f}x")
    
    # 验证结果一致性
    # max_error = np.abs(portfolio - portfolio2).max()
    # print(f"\n数值误差: {max_error:.2e}")
    # if max_error < 1e-4:
    #     print("✓ 两个版本结果一致")
    # else:
    #     print("⚠ 两个版本结果有差异")
    
    # ✨ 新增：保存简化版结果
    # output_file2 = os.path.join(output_dir, "python_simple_output.npz")
    # np.savez_compressed(
    #     output_file2,
    #     portfolio_values=portfolio2,
    #     cash_matrix=cash2,
    #     quantity_matrix=qty2,
    #     elapsed_time_ms=np.array([elapsed2 * 1000])
    # )
    # print(f"\n✓ 简化版结果已保存到: {output_file2}")