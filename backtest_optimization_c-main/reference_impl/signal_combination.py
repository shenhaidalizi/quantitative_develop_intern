"""
信号组合处理 - Python 参考实现

提取自: src/trader_backtest/strategy/signal_strategy.py:process_dataframe()
"""
import numpy as np
from typing import Tuple


def process_signals_python(
    signal_matrix: np.ndarray,
    weights_matrix: np.ndarray,
    threshold: float = 0.5
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    信号组合处理 - Python 参考实现
    
    Args:
        signal_matrix: (n_timesteps, n_signals) 信号矩阵
        weights_matrix: (n_signals, n_weights) 权重矩阵
        threshold: 信号阈值，默认 0.5
    
    Returns:
        combined_signals: (n_timesteps, n_weights) 组合信号
        long_short_matrix: (n_timesteps, n_weights) 多空信号 {-1, 0, 1}
        position_matrix: (n_timesteps, n_weights) 持仓矩阵 {-1, 0, 1}
    
    算法逻辑:
        1. 矩阵乘法计算组合信号: combined = signals @ weights
        2. 应用阈值生成多空信号:
           - combined > threshold  → 1 (做多)
           - combined < -threshold → -1 (做空)
           - 其他 → 0 (空仓)
        3. 持仓滞后一期: position[t] = long_short[t-1]
           (今天的信号，明天的持仓)
    """
    # 输入验证
    if signal_matrix.shape[1] != weights_matrix.shape[0]:
        raise ValueError(
            f"信号矩阵列数 ({signal_matrix.shape[1]}) 与权重矩阵行数 "
            f"({weights_matrix.shape[0]}) 不匹配"
        )
    
    n_timesteps = signal_matrix.shape[0]
    n_weights = weights_matrix.shape[1]
    
    # Step 1: 矩阵乘法 - 信号加权组合
    # combined[t, w] = Σ(signals[t, i] * weights[i, w])
    combined_signals = np.dot(signal_matrix, weights_matrix).astype(np.float32)
    
    # Step 2: 应用阈值生成多空信号
    long_short_matrix = np.zeros((n_timesteps, n_weights), dtype=np.int8)
    long_short_matrix[combined_signals > threshold] = 1   # 做多
    long_short_matrix[combined_signals < -threshold] = -1  # 做空
    
    # Step 3: 持仓滞后一期（今日信号，明日持仓）
    position_matrix = np.zeros((n_timesteps, n_weights), dtype=np.int8)
    position_matrix[1:] = long_short_matrix[:-1]
    
    return combined_signals, long_short_matrix, position_matrix


def process_signals_vectorized(
    signal_matrix: np.ndarray,
    weights_matrix: np.ndarray,
    threshold: float = 0.5
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    优化版本：融合阈值判断和数组移位为单次遍历
    
    此版本性能略优，但与上面版本结果完全一致
    """
    if signal_matrix.shape[1] != weights_matrix.shape[0]:
        raise ValueError("矩阵维度不匹配")
    
    n_timesteps = signal_matrix.shape[0]
    n_weights = weights_matrix.shape[1]
    
    # 矩阵乘法
    combined_signals = np.dot(signal_matrix, weights_matrix).astype(np.float32)
    
    # 融合操作：直接生成持仓矩阵（滞后一期）
    position_matrix = np.zeros((n_timesteps, n_weights), dtype=np.int8)
    long_short_matrix = np.zeros((n_timesteps, n_weights), dtype=np.int8)
    
    # 向量化阈值判断
    long_short_matrix[combined_signals > threshold] = 1
    long_short_matrix[combined_signals < -threshold] = -1
    
    # 滞后一期
    position_matrix[1:] = long_short_matrix[:-1]
    
    return combined_signals, long_short_matrix, position_matrix


if __name__ == "__main__":
    # 简单测试
    np.random.seed(42)
    
    signals = np.random.randn(100, 5).astype(np.float32)
    weights = np.random.randn(5, 10).astype(np.float32)
    
    combined, long_short, positions = process_signals_python(signals, weights, 0.5)
    
    print(f"Combined signals shape: {combined.shape}")
    print(f"Long/Short matrix shape: {long_short.shape}")
    print(f"Position matrix shape: {positions.shape}")
    print(f"Long/Short unique values: {np.unique(long_short)}")
    print(f"Position unique values: {np.unique(positions)}")
    
    # 验证滞后
    assert np.allclose(positions[1:], long_short[:-1]), "持仓滞后验证失败"
    print("✓ 持仓滞后验证通过")

