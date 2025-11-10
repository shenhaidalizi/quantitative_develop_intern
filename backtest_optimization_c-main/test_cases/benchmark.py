"""
性能基准测试脚本

对比 Python 参考实现和 C++ 实现的性能
"""
import numpy as np
import time
import sys
import os
import argparse
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from reference_impl import (
    process_signals_python,
    run_backtest_python,
    run_multi_weight_vectorized,  # 原版向量化实现
    calculate_sharpe_ratio_python,
    evaluate_weights_batch_python
)


class BenchmarkRunner:
    """性能基准测试运行器"""
    
    def __init__(self, n_runs=5):
        self.n_runs = n_runs
        self.results = []
        
        try:
            import backtest_cpp
            self.cpp_module = backtest_cpp
            self.cpp_available = True
        except ImportError:
            self.cpp_module = None
            self.cpp_available = False
            print("⚠ C++ 模块未安装，仅运行 Python 基准测试")
    
    def generate_data(self, n_timesteps, n_signals, n_weights, seed=42):
        """生成测试数据"""
        np.random.seed(seed)
        
        signals = np.random.randn(n_timesteps, n_signals).astype(np.float32)
        weights = np.random.randn(n_signals, n_weights).astype(np.float32)
        prices = (np.cumsum(np.random.randn(n_timesteps) * 0.01) + 100).astype(np.float32)
        prices = np.maximum(prices, 1.0)
        
        return signals, weights, prices
    
    def benchmark_module(self, name, func, *args):
        """基准测试单个函数"""
        times = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            result = func(*args)
            times.append(time.perf_counter() - start)
        
        median_time = np.median(times)
        return median_time, result
    
    def benchmark_signal_processing(self, signals, weights, threshold=0.5):
        """基准测试：信号处理"""
        print(f"\n{'='*60}")
        print(f"基准测试 1: 信号处理")
        print(f"{'='*60}")
        print(f"数据规模: signals {signals.shape}, weights {weights.shape}")
        
        # Python
        py_time, py_result = self.benchmark_module(
            'Python', process_signals_python, signals, weights, threshold
        )
        print(f"Python 耗时: {py_time*1000:.2f} ms")
        
        if not self.cpp_available:
            return
        
        # C++
        cpp_time, cpp_result = self.benchmark_module(
            'C++', self.cpp_module.process_signals, signals, weights, threshold
        )
        speedup = py_time / cpp_time
        
        print(f"C++ 耗时: {cpp_time*1000:.2f} ms")
        print(f"加速比: {speedup:.2f}x")
        
        # 验证正确性
        error = np.abs(py_result[0] - cpp_result[0]).max()
        print(f"数值误差: {error:.2e}")
        
        self.results.append({
            'test': 'signal_processing',
            'shape': f"{signals.shape}x{weights.shape}",
            'python_time_ms': py_time * 1000,
            'cpp_time_ms': cpp_time * 1000,
            'speedup': speedup,
            'error': error
        })
    
    def benchmark_backtest(self, prices, positions):
        """基准测试：回测引擎"""
        print(f"\n{'='*60}")
        print(f"基准测试 2: 回测引擎")
        print(f"{'='*60}")
        print(f"数据规模: prices {prices.shape}, positions {positions.shape}")
        
        # Python 简化版
        py_simple_time, py_simple_result = self.benchmark_module(
            'Python (简化版)', run_backtest_python, prices, positions, 1000000.0, "cash_all"
        )
        print(f"Python 简化版耗时: {py_simple_time*1000:.2f} ms")
        
        # Python 向量化版（原版）
        py_vec_time, py_vec_result = self.benchmark_module(
            'Python (向量化版)', run_multi_weight_vectorized, prices, positions, 1000000.0, "cash_all"
        )
        print(f"Python 向量化版耗时: {py_vec_time*1000:.2f} ms")
        print(f"向量化加速: {py_simple_time/py_vec_time:.2f}x")
        
        # 验证两个 Python 版本一致性
        error_py = np.abs(py_simple_result[0] - py_vec_result[0]).max()
        print(f"Python 版本间误差: {error_py:.2e}")
        
        if not self.cpp_available:
            return
        
        # C++
        cpp_time, cpp_result = self.benchmark_module(
            'C++', self.cpp_module.run_backtest, prices, positions, 1000000.0, "cash_all"
        )
        speedup_simple = py_simple_time / cpp_time
        speedup_vec = py_vec_time / cpp_time
        
        print(f"\nC++ 耗时: {cpp_time*1000:.2f} ms")
        print(f"相比简化版加速: {speedup_simple:.2f}x")
        print(f"相比向量化版加速: {speedup_vec:.2f}x")
        
        # 验证
        error = np.abs(py_vec_result[0] - cpp_result[0]).max()
        print(f"C++ vs Python 误差: {error:.2e}")
        
        self.results.append({
            'test': 'backtest_engine',
            'shape': f"{prices.shape}x{positions.shape}",
            'python_time_ms': py_vec_time * 1000,  # 使用向量化版本作为基准
            'cpp_time_ms': cpp_time * 1000,
            'speedup': speedup_vec,
            'error': error
        })
    
    def benchmark_optimizer(self, weights_batch, signals, prices):
        """基准测试：优化器核心"""
        print(f"\n{'='*60}")
        print(f"基准测试 3: 优化器核心")
        print(f"{'='*60}")
        print(f"数据规模: weights {weights_batch.shape}, signals {signals.shape}")
        
        # Python
        py_time, py_scores = self.benchmark_module(
            'Python', evaluate_weights_batch_python,
            weights_batch, signals, prices, 0.5, 1000000.0
        )
        print(f"Python 耗时: {py_time:.3f} s")
        
        if not self.cpp_available:
            return
        
        # C++
        cpp_time, cpp_scores = self.benchmark_module(
            'C++', self.cpp_module.evaluate_weights_batch,
            weights_batch, signals, prices, 0.5, 1000000.0
        )
        speedup = py_time / cpp_time
        
        print(f"C++ 耗时: {cpp_time:.3f} s")
        print(f"加速比: {speedup:.2f}x")
        
        # 验证
        error = np.abs(py_scores - cpp_scores).max()
        print(f"数值误差: {error:.2e}")
        
        self.results.append({
            'test': 'optimizer_kernel',
            'shape': f"{weights_batch.shape}x{signals.shape}",
            'python_time_ms': py_time * 1000,
            'cpp_time_ms': cpp_time * 1000,
            'speedup': speedup,
            'error': error
        })
    
    def run_scale_test(self, scale):
        """运行特定规模的测试"""
        configs = {
            'small': (100, 5, 10),
            'medium': (1000, 10, 100),
            'large': (1000, 10, 10000),
        }
        
        if scale not in configs:
            print(f"未知的测试规模: {scale}")
            return
        
        T, N, W = configs[scale]
        
        print(f"\n{'='*60}")
        print(f"测试规模: {scale.upper()} (T={T}, N={N}, W={W})")
        print(f"{'='*60}")
        
        signals, weights, prices = self.generate_data(T, N, W)
        
        # 测试 1: 信号处理
        self.benchmark_signal_processing(signals, weights)
        
        # 测试 2: 回测引擎
        combined, long_short, positions = process_signals_python(signals, weights, 0.5)
        self.benchmark_backtest(prices, positions)
        
        # 测试 3: 优化器（仅在权重数 >= 100 时）
        if W >= 100:
            self.benchmark_optimizer(weights[:, :min(W, 1000)], signals, prices)
    
    def generate_report(self):
        """生成测试报告"""
        if not self.results:
            print("\n没有测试结果")
            return
        
        df = pd.DataFrame(self.results)
        
        print(f"\n{'='*60}")
        print("性能基准测试报告")
        print(f"{'='*60}")
        print(df.to_string(index=False))
        
        # 保存CSV
        df.to_csv('benchmark_results.csv', index=False)
        print(f"\n结果已保存到 benchmark_results.csv")
        
        if not self.cpp_available:
            return
        
        # 检查性能目标
        print(f"\n{'='*60}")
        print("性能目标检查")
        print(f"{'='*60}")
        
        targets = {
            'signal_processing': 5.0,
            'backtest_engine': 15.0,
            'optimizer_kernel': 20.0
        }
        
        for _, row in df.iterrows():
            test_name = row['test']
            speedup = row['speedup']
            target = targets.get(test_name, 10.0)
            
            status = "✓ PASS" if speedup >= target else "✗ FAIL"
            print(f"{test_name:25s} {speedup:6.2f}x (目标: {target:4.1f}x) {status}")


def main():
    parser = argparse.ArgumentParser(description='性能基准测试')
    parser.add_argument('--scale', type=str, default='medium',
                        choices=['small', 'medium', 'large', 'all'],
                        help='测试规模')
    parser.add_argument('--runs', type=int, default=5, help='重复次数')
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner(n_runs=args.runs)
    
    if args.scale == 'all':
        for scale in ['small', 'medium', 'large']:
            runner.run_scale_test(scale)
    else:
        runner.run_scale_test(args.scale)
    
    runner.generate_report()


if __name__ == "__main__":
    main()

