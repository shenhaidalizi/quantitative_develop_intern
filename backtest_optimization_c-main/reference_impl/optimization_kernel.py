"""
优化器核心 - Python 参考实现

整合信号处理、回测和指标计算
提取自: src/trader_backtest/optimizer/candle_weight_optimizer.py:evaluate_weights()
"""
import numpy as np
from typing import Union
import sys
import os

# 支持直接运行和模块导入两种方式
if __name__ == "__main__":
    # 直接运行时使用绝对导入
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from reference_impl.signal_combination import process_signals_python
    from reference_impl.core_engine import run_backtest_python
    from reference_impl.metrics import calculate_sharpe_ratio_python
else:
    # 作为模块导入时使用相对导入
    from .signal_combination import process_signals_python
    from .core_engine import run_backtest_python
    from .metrics import calculate_sharpe_ratio_python


def evaluate_weights_batch_python(
    weights_batch: np.ndarray,
    signal_matrix: np.ndarray,
    prices: np.ndarray,
    threshold: float = 0.5,
    initial_cash: float = 1000000.0,
    trade_mode: str = "portfolio_pct",
    max_allocation_pct: float = 0.5,
    fixed_cash_amount: float = 100000.0
) -> np.ndarray:
    """
    批量评估权重组合 - Python 参考实现
    
    这是优化算法的核心函数，用于批量计算多个权重组合的性能得分
    
    Args:
        weights_batch: (n_signals, n_candidates) 候选权重矩阵
        signal_matrix: (n_timesteps, n_signals) 信号矩阵
        prices: (n_timesteps,) 价格序列
        threshold: 信号阈值
        initial_cash: 初始资金
        trade_mode: 交易模式
        max_allocation_pct: 最大仓位比例
        fixed_cash_amount: 固定交易金额
    
    Returns:
        scores: (n_candidates,) 每个权重组合的夏普比率
    
    流程:
        1. 信号组合 → 生成持仓矩阵
        2. 回测 → 生成组合价值序列
        3. 计算夏普比率 → 返回得分
    """
    # Step 1: 信号组合
    combined_signals, long_short, position_matrix = process_signals_python(
        signal_matrix, weights_batch, threshold
    )
    
    # Step 2: 回测
    portfolio_values, _, _ = run_backtest_python(
        prices, position_matrix,
        initial_cash=initial_cash,
        trade_mode=trade_mode,
        max_allocation_pct=max_allocation_pct,
        fixed_cash_amount=fixed_cash_amount
    )
    
    # Step 3: 计算夏普比率
    sharpe_ratios = calculate_sharpe_ratio_python(portfolio_values)
    
    return sharpe_ratios


def evaluate_single_weight_python(
    weights: np.ndarray,
    signal_matrix: np.ndarray,
    prices: np.ndarray,
    threshold: float = 0.5,
    initial_cash: float = 1000000.0,
    trade_mode: str = "portfolio_pct"
) -> float:
    """
    评估单个权重组合（便捷接口）
    
    Args:
        weights: (n_signals,) 单个权重向量
    
    Returns:
        score: float 夏普比率
    """
    # 转换为列向量
    weights_batch = weights.reshape(-1, 1)
    
    scores = evaluate_weights_batch_python(
        weights_batch, signal_matrix, prices, threshold, initial_cash, trade_mode
    )
    
    return float(scores[0])


def evaluate_weights_with_metrics_python(
    weights_batch: np.ndarray,
    signal_matrix: np.ndarray,
    prices: np.ndarray,
    threshold: float = 0.5,
    initial_cash: float = 1000000.0,
    trade_mode: str = "portfolio_pct"
) -> dict:
    """
    批量评估并返回详细指标
    
    Returns:
        result: dict 包含所有中间结果和指标
    """
    from .metrics import calculate_all_metrics_python
    
    # 信号组合
    combined_signals, long_short, position_matrix = process_signals_python(
        signal_matrix, weights_batch, threshold
    )
    
    # 回测
    portfolio_values, cash_matrix, quantity_matrix = run_backtest_python(
        prices, position_matrix,
        initial_cash=initial_cash,
        trade_mode=trade_mode
    )
    
    # 计算所有指标
    metrics = calculate_all_metrics_python(portfolio_values)
    
    return {
        'combined_signals': combined_signals,
        'long_short_matrix': long_short,
        'position_matrix': position_matrix,
        'portfolio_values': portfolio_values,
        'cash_matrix': cash_matrix,
        'quantity_matrix': quantity_matrix,
        'metrics': metrics
    }


if __name__ == "__main__":
    # 测试
    np.random.seed(42)
    
    # 生成测试数据
    n_timesteps = 100000
    n_signals = 1000
    n_candidates = 100
    
    signals = np.random.randn(n_timesteps, n_signals).astype(np.float32)
    weights_batch = np.random.randn(n_signals, n_candidates).astype(np.float32)
    prices = (np.cumsum(np.random.randn(n_timesteps) * 0.01) + 100).astype(np.float32)
    prices = np.maximum(prices, 1.0)
    
    print("=== 批量评估测试 ===")
    print(f"信号矩阵: {signals.shape}")
    print(f"权重批次: {weights_batch.shape}")
    print(f"价格序列: {prices.shape}")
    
    # 批量评估
    import time
    start = time.perf_counter()
    scores = evaluate_weights_batch_python(
        weights_batch, signals, prices,
        threshold=0.5,
        initial_cash=1000000.0,
        trade_mode="cash_all"
    )
    elapsed = time.perf_counter() - start
    
    print(f"\n耗时: {elapsed:.2f} 秒")
    print(f"得分形状: {scores.shape}")
    print(f"得分统计: min={scores.min():.4f}, max={scores.max():.4f}, mean={scores.mean():.4f}")
    
    # 找到最佳权重
    best_idx = np.argmax(scores)
    print(f"\n最佳权重索引: {best_idx}")
    print(f"最佳得分: {scores[best_idx]:.4f}")
    print(f"最佳权重: {weights_batch[:, best_idx]}")
    
    # 单个评估测试
    print("\n=== 单个评估测试 ===")
    single_weight = weights_batch[:, best_idx]
    single_score = evaluate_single_weight_python(
        single_weight, signals, prices, threshold=0.5
    )
    print(f"单个评估得分: {single_score:.4f}")
    assert np.isclose(single_score, scores[best_idx], rtol=1e-3, atol=1e-4), \
        f"误差: {abs(single_score - scores[best_idx]):.6f}"

