"""
性能指标计算 - Python 参考实现
"""
import numpy as np


def calculate_returns_python(portfolio_values: np.ndarray) -> np.ndarray:
    """
    计算收益率矩阵
    
    Args:
        portfolio_values: (n_timesteps, n_weights) 组合价值矩阵
    
    Returns:
        returns: (n_timesteps-1, n_weights) 收益率矩阵
    
    公式:
        returns[t] = (portfolio[t+1] / portfolio[t]) - 1
    """
    returns = np.zeros((portfolio_values.shape[0] - 1, portfolio_values.shape[1]), dtype=np.float32)
    
    # 避免除零
    with np.errstate(divide='ignore', invalid='ignore'):
        returns = (portfolio_values[1:] / portfolio_values[:-1]) - 1.0
        returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
    
    return returns


def calculate_sharpe_ratio_python(
    portfolio_values: np.ndarray,
    annualization_factor: float = 252.0
) -> np.ndarray:
    """
    计算夏普比率
    
    Args:
        portfolio_values: (n_timesteps, n_weights) 组合价值矩阵
        annualization_factor: 年化因子，默认 252（交易日）
    
    Returns:
        sharpe_ratios: (n_weights,) 夏普比率数组
    
    公式:
        Sharpe = (mean_return / std_return) * sqrt(annualization_factor)
    """
    # 计算收益率
    returns = calculate_returns_python(portfolio_values)
    
    # 计算均值和标准差
    mean_returns = np.mean(returns, axis=0)
    std_returns = np.std(returns, axis=0, ddof=1)  # 样本标准差
    
    # 计算夏普比率
    with np.errstate(divide='ignore', invalid='ignore'):
        sharpe_ratios = (mean_returns / (std_returns + 1e-8)) * np.sqrt(annualization_factor)
        sharpe_ratios = np.nan_to_num(sharpe_ratios, nan=0.0, posinf=0.0, neginf=0.0)
    
    return sharpe_ratios.astype(np.float32)


def calculate_max_drawdown_python(portfolio_values: np.ndarray) -> np.ndarray:
    """
    计算最大回撤
    
    Args:
        portfolio_values: (n_timesteps, n_weights) 组合价值矩阵
    
    Returns:
        max_drawdowns: (n_weights,) 最大回撤数组
    
    公式:
        MaxDD = max((peak - valley) / peak)
    
    算法:
        对每个权重组合：
        1. 遍历时间序列
        2. 维护历史最高点 peak
        3. 计算当前回撤 = (peak - current) / peak
        4. 更新最大回撤
    """
    n_timesteps, n_weights = portfolio_values.shape
    max_drawdowns = np.zeros(n_weights, dtype=np.float32)
    
    for w in range(n_weights):
        peak = portfolio_values[0, w]
        max_dd = 0.0
        
        for t in range(1, n_timesteps):
            value = portfolio_values[t, w]
            
            if value > peak:
                peak = value
            else:
                drawdown = (peak - value) / (peak + 1e-8)
                if drawdown > max_dd:
                    max_dd = drawdown
        
        max_drawdowns[w] = max_dd
    
    return max_drawdowns


def calculate_total_return_python(portfolio_values: np.ndarray) -> np.ndarray:
    """
    计算总收益率
    
    Args:
        portfolio_values: (n_timesteps, n_weights) 组合价值矩阵
    
    Returns:
        total_returns: (n_weights,) 总收益率数组
    
    公式:
        TotalReturn = (final_value / initial_value) - 1
    """
    initial_values = portfolio_values[0]
    final_values = portfolio_values[-1]
    
    with np.errstate(divide='ignore', invalid='ignore'):
        total_returns = (final_values / (initial_values + 1e-8)) - 1.0
        total_returns = np.nan_to_num(total_returns, nan=0.0, posinf=0.0, neginf=0.0)
    
    return total_returns.astype(np.float32)


def calculate_win_rate_python(portfolio_values: np.ndarray) -> np.ndarray:
    """
    计算胜率（正收益天数占比）
    
    Args:
        portfolio_values: (n_timesteps, n_weights) 组合价值矩阵
    
    Returns:
        win_rates: (n_weights,) 胜率数组
    """
    returns = calculate_returns_python(portfolio_values)
    win_rates = (returns > 0).sum(axis=0) / returns.shape[0]
    return win_rates.astype(np.float32)


def calculate_all_metrics_python(portfolio_values: np.ndarray) -> dict:
    """
    计算所有性能指标
    
    Returns:
        metrics: 包含所有指标的字典
    """
    return {
        'sharpe_ratio': calculate_sharpe_ratio_python(portfolio_values),
        'max_drawdown': calculate_max_drawdown_python(portfolio_values),
        'total_return': calculate_total_return_python(portfolio_values),
        'win_rate': calculate_win_rate_python(portfolio_values)
    }


if __name__ == "__main__":
    # 简单测试
    np.random.seed(42)
    
    # 生成测试数据：模拟组合价值曲线
    n_timesteps = 252  # 一年
    n_weights = 5
    
    initial_value = 1000000.0
    returns = np.random.normal(0.001, 0.02, (n_timesteps, n_weights))
    portfolio_values = initial_value * np.cumprod(1 + returns, axis=0).astype(np.float32)
    
    # 计算指标
    sharpe = calculate_sharpe_ratio_python(portfolio_values)
    max_dd = calculate_max_drawdown_python(portfolio_values)
    total_ret = calculate_total_return_python(portfolio_values)
    win_rate = calculate_win_rate_python(portfolio_values)
    
    print("=== 性能指标测试 ===")
    print(f"夏普比率: {sharpe}")
    print(f"最大回撤: {max_dd}")
    print(f"总收益率: {total_ret}")
    print(f"胜率: {win_rate}")
    
    # 验证合理性
    assert np.all(max_dd >= 0) and np.all(max_dd <= 1), "最大回撤应在 [0, 1]"
    assert np.all(win_rate >= 0) and np.all(win_rate <= 1), "胜率应在 [0, 1]"
    print("✓ 指标范围验证通过")

