"""
Python 参考实现模块

提供核心算法的纯 Python 实现，用于：
1. 生成测试数据的期望输出
2. 验证 C++ 实现的正确性
3. 性能对比基准
"""

from .signal_combination import process_signals_python
from .core_engine import run_backtest_python
from .core_engine_vectorized import run_multi_weight_vectorized
from .metrics import (
    calculate_sharpe_ratio_python,
    calculate_max_drawdown_python,
    calculate_returns_python,
    calculate_total_return_python,
    calculate_all_metrics_python
)
from .optimization_kernel import evaluate_weights_batch_python

__all__ = [
    'process_signals_python',
    'run_backtest_python',
    'run_multi_weight_vectorized',  # 原版向量化实现
    'calculate_sharpe_ratio_python',
    'calculate_max_drawdown_python',
    'calculate_returns_python',
    'calculate_total_return_python',
    'calculate_all_metrics_python',
    'evaluate_weights_batch_python'
]

