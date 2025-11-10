"""
回测引擎核心 - Python 参考实现

提取自: src/trader_backtest/engine/candle.py:run_multi_weight()
"""
import numpy as np
from typing import Tuple


def run_backtest_python(
    prices: np.ndarray,
    position_matrix: np.ndarray,
    initial_cash: float = 1000000.0,
    trade_mode: str = "portfolio_pct",
    max_allocation_pct: float = 0.5,
    fixed_cash_amount: float = 100000.0,
    position_size: float = 100.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    多权重回测引擎 - Python 参考实现
    
    Args:
        prices: (n_timesteps,) 价格序列
        position_matrix: (n_timesteps, n_weights) 持仓信号矩阵 {-1, 0, 1}
        initial_cash: 初始资金
        trade_mode: 交易模式
            - "cash_all": 全部现金买入
            - "portfolio_pct": 组合价值的固定比例分配
            - "fixed_cash": 每次交易固定金额
            - "fixed": 固定仓位数量
        max_allocation_pct: 最大仓位比例（仅 portfolio_pct 模式）
        fixed_cash_amount: 固定交易金额（仅 fixed_cash 模式）
        position_size: 固定仓位大小（仅 fixed 模式）
    
    Returns:
        portfolio_values: (n_timesteps, n_weights) 组合价值矩阵
        cash_matrix: (n_timesteps, n_weights) 现金矩阵
        quantity_matrix: (n_timesteps, n_weights) 持仓数量矩阵
    
    算法逻辑:
        对每个时间步和每个权重组合：
        1. 检测持仓变化（买入/卖出信号）
        2. 根据交易模式计算交易数量
        3. 更新现金和持仓
        4. 计算组合价值
    """
    n_timesteps = len(prices)
    n_weights = position_matrix.shape[1]
    
    # 输入验证
    if position_matrix.shape[0] != n_timesteps:
        raise ValueError(f"持仓矩阵时间步数不匹配: {position_matrix.shape[0]} vs {n_timesteps}")
    
    # 初始化输出矩阵
    portfolio_values = np.zeros((n_timesteps, n_weights), dtype=np.float32)
    cash_matrix = np.zeros((n_timesteps, n_weights), dtype=np.float32)
    quantity_matrix = np.zeros((n_timesteps, n_weights), dtype=np.float32)
    
    # 第一时间步初始化
    cash_matrix[0, :] = initial_cash
    portfolio_values[0, :] = initial_cash
    
    # 计算持仓变化矩阵
    position_changes = np.diff(
        np.vstack([np.zeros((1, n_weights)), position_matrix]),
        axis=0
    )
    
    # 主循环：遍历时间步
    for t in range(1, n_timesteps):
        price = prices[t]
        
        # 继承前一时刻状态
        cash_matrix[t] = cash_matrix[t-1]
        quantity_matrix[t] = quantity_matrix[t-1]
        
        # 处理每个权重组合
        for w in range(n_weights):
            change = position_changes[t, w]
            
            # 买入信号（持仓增加）
            if change > 0:
                buy_qty = 0.0
                
                if trade_mode == "cash_all":
                    # 全部现金买入
                    buy_qty = np.floor(cash_matrix[t, w] / price)
                
                elif trade_mode == "portfolio_pct":
                    # 组合价值的固定比例
                    portfolio_val = cash_matrix[t, w] + quantity_matrix[t, w] * price
                    max_position = np.floor(portfolio_val * max_allocation_pct / price)
                    available_cash_qty = np.floor(cash_matrix[t, w] / price)
                    
                    buy_qty = max(0.0, min(
                        max_position - quantity_matrix[t, w],
                        available_cash_qty
                    ))
                
                elif trade_mode == "fixed_cash":
                    # 固定金额
                    buy_qty = np.floor(fixed_cash_amount / price)
                
                elif trade_mode == "fixed":
                    # 固定仓位数量
                    buy_qty = position_size
                
                else:
                    raise ValueError(f"不支持的交易模式: {trade_mode}")
                
                # 资金约束
                buy_qty = min(buy_qty, np.floor(cash_matrix[t, w] / price))
                
                # 更新状态
                cash_matrix[t, w] -= buy_qty * price
                quantity_matrix[t, w] += buy_qty
            
            # 卖出信号（持仓减少）
            elif change < 0:
                sell_qty = quantity_matrix[t-1, w]
                
                # 更新状态
                cash_matrix[t, w] += sell_qty * price
                quantity_matrix[t, w] = 0.0
        
        # 更新组合价值
        portfolio_values[t] = cash_matrix[t] + quantity_matrix[t] * price
    
    return portfolio_values, cash_matrix, quantity_matrix


def run_backtest_vectorized(
    prices: np.ndarray,
    position_matrix: np.ndarray,
    initial_cash: float = 1000000.0,
    trade_mode: str = "cash_all"
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    向量化优化版本 - 仅支持 cash_all 模式
    
    此版本通过向量化买卖操作提升性能，但仅实现最简单的 cash_all 模式
    """
    n_timesteps = len(prices)
    n_weights = position_matrix.shape[1]
    
    portfolio_values = np.zeros((n_timesteps, n_weights), dtype=np.float32)
    cash_matrix = np.zeros((n_timesteps, n_weights), dtype=np.float32)
    quantity_matrix = np.zeros((n_timesteps, n_weights), dtype=np.float32)
    
    cash_matrix[0, :] = initial_cash
    portfolio_values[0, :] = initial_cash
    
    position_changes = np.diff(
        np.vstack([np.zeros((1, n_weights)), position_matrix]),
        axis=0
    )
    
    for t in range(1, n_timesteps):
        price = prices[t]
        
        cash_matrix[t] = cash_matrix[t-1]
        quantity_matrix[t] = quantity_matrix[t-1]
        
        # 向量化买入
        buy_mask = position_changes[t] > 0
        if buy_mask.any():
            buy_qty = cash_matrix[t, buy_mask] / price
            buy_cost = buy_qty * price
            cash_matrix[t, buy_mask] -= buy_cost
            quantity_matrix[t, buy_mask] += buy_qty
        
        # 向量化卖出
        sell_mask = position_changes[t] < 0
        if sell_mask.any():
            sell_qty = quantity_matrix[t-1, sell_mask]
            sell_revenue = sell_qty * price
            cash_matrix[t, sell_mask] += sell_revenue
            quantity_matrix[t, sell_mask] = 0.0
        
        portfolio_values[t] = cash_matrix[t] + quantity_matrix[t] * price
    
    return portfolio_values, cash_matrix, quantity_matrix


if __name__ == "__main__":
    # 简单测试
    np.random.seed(42)
    
    # 生成测试数据
    n_timesteps = 100
    n_weights = 10
    
    prices = (np.cumsum(np.random.randn(n_timesteps) * 0.01) + 100).astype(np.float32)
    prices = np.maximum(prices, 1.0)
    
    positions = np.random.choice([-1, 0, 1], size=(n_timesteps, n_weights)).astype(np.int8)
    
    # 运行回测
    portfolio, cash, qty = run_backtest_python(
        prices, positions, 
        initial_cash=10000.0,
        trade_mode="cash_all"
    )
    
    print(f"Portfolio values shape: {portfolio.shape}")
    print(f"Initial portfolio value: {portfolio[0, 0]:.2f}")
    print(f"Final portfolio values: {portfolio[-1, :3]}")
    print(f"Cash matrix shape: {cash.shape}")
    print(f"Quantity matrix shape: {qty.shape}")
    
    # 验证组合价值计算
    final_check = cash[-1] + qty[-1] * prices[-1]
    assert np.allclose(portfolio[-1], final_check), "组合价值计算错误"
    print("✓ 组合价值验证通过")

