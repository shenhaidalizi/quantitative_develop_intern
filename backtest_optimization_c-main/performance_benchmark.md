# 性能基准测试说明

## 1. 测试环境规范

### 1.1 硬件要求
- **CPU**: 现代 x86_64 处理器（AVX2 支持）
- **内存**: >= 8GB RAM
- **核心数**: >= 4 核心（用于并行测试）

### 1.2 软件环境
```bash
# Python 环境
Python 3.8+
NumPy 1.20+
Pandas 1.3+

# C++ 编译器
GCC 9+ / Clang 10+
CMake 3.15+
Eigen3 3.3+
```

---

## 2. 基准测试用例

### 2.1 小规模测试 (Smoke Test)

**目的**: 验证功能正确性

| 参数             | 值      |
|------------------|---------|
| 时间步数 (T)     | 100     |
| 信号数 (N)       | 5       |
| 权重组合数 (W)   | 10      |
| 初始资金         | 100000  |

**预期结果**:
- C++ 实现加速比: >= 5x
- 数值误差: < 1e-6

---

### 2.2 中等规模测试 (Medium Test)

**目的**: 常规回测场景

| 参数             | 值      |
|------------------|---------|
| 时间步数 (T)     | 1000    |
| 信号数 (N)       | 10      |
| 权重组合数 (W)   | 100     |
| 初始资金         | 1000000 |

**预期结果**:
- 单线程加速比: >= 15x
- 4 线程加速比: >= 40x
- 内存占用: <= 100 MB

---

### 2.3 大规模测试 (Large Test)

**目的**: 优化器场景（遗传算法、梯度优化）

| 参数             | 值      |
|------------------|---------|
| 时间步数 (T)     | 1000    |
| 信号数 (N)       | 10      |
| 权重组合数 (W)   | 10000   |
| 初始资金         | 1000000 |

**预期结果**:
- 单线程加速比: >= 20x
- 4 线程加速比: >= 60x
- 8 线程加速比: >= 100x
- 内存占用: <= 500 MB

---

### 2.4 超大规模测试 (Stress Test)

**目的**: 压力测试

| 参数             | 值      |
|------------------|---------|
| 时间步数 (T)     | 5000    |
| 信号数 (N)       | 20      |
| 权重组合数 (W)   | 50000   |
| 初始资金         | 1000000 |

**预期结果**:
- 能够在合理时间内完成（< 5 分钟）
- 无内存泄漏
- 内存占用: <= 2 GB

---

## 3. 性能测试脚本

### 3.1 基准测试代码

```python
# test_cases/benchmark.py
import time
import numpy as np
import pandas as pd
from typing import Dict, List

# Python 参考实现
from reference_impl import (
    process_signals_python,
    run_backtest_python,
    evaluate_weights_batch_python
)

# C++ 实现
try:
    from backtest_cpp import (
        process_signals,
        run_backtest,
        evaluate_weights_batch
    )
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False
    print("警告: C++ 模块未安装，仅运行 Python 基准测试")


class BenchmarkRunner:
    """性能基准测试运行器"""
    
    def __init__(self, n_runs: int = 5):
        self.n_runs = n_runs
        self.results = []
    
    def generate_test_data(self, n_timesteps: int, n_signals: int, n_weights: int):
        """生成测试数据"""
        np.random.seed(42)
        
        signals = np.random.randn(n_timesteps, n_signals).astype(np.float32)
        weights = np.random.randn(n_signals, n_weights).astype(np.float32)
        prices = (np.cumsum(np.random.randn(n_timesteps) * 0.01) + 100).astype(np.float32)
        prices = np.maximum(prices, 1.0)  # 确保价格为正
        
        return signals, weights, prices
    
    def benchmark_signal_processing(self, signals, weights, threshold=0.5):
        """基准测试：信号处理"""
        print(f"\n=== 信号处理基准测试 ===")
        print(f"数据规模: signals {signals.shape}, weights {weights.shape}")
        
        # Python 版本
        python_times = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            py_combined, py_long_short, py_positions = process_signals_python(
                signals, weights, threshold
            )
            python_times.append(time.perf_counter() - start)
        
        py_time = np.median(python_times)
        print(f"Python 耗时: {py_time*1000:.2f} ms")
        
        if not CPP_AVAILABLE:
            return
        
        # C++ 版本
        cpp_times = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            cpp_combined, cpp_long_short, cpp_positions = process_signals(
                signals, weights, threshold
            )
            cpp_times.append(time.perf_counter() - start)
        
        cpp_time = np.median(cpp_times)
        speedup = py_time / cpp_time
        
        print(f"C++ 耗时: {cpp_time*1000:.2f} ms")
        print(f"加速比: {speedup:.2f}x")
        
        # 验证正确性
        max_error = np.abs(py_combined - cpp_combined).max()
        print(f"数值误差: {max_error:.2e}")
        
        assert max_error < 1e-5, f"数值误差过大: {max_error}"
        
        self.results.append({
            'test': 'signal_processing',
            'shape': signals.shape,
            'python_time': py_time,
            'cpp_time': cpp_time,
            'speedup': speedup,
            'error': max_error
        })
        
        return speedup
    
    def benchmark_backtest_engine(self, prices, positions, initial_cash=1000000.0):
        """基准测试：回测引擎"""
        print(f"\n=== 回测引擎基准测试 ===")
        print(f"数据规模: prices {prices.shape}, positions {positions.shape}")
        
        # Python 版本
        python_times = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            py_portfolio, py_cash, py_qty = run_backtest_python(
                prices, positions, initial_cash, "cash_all"
            )
            python_times.append(time.perf_counter() - start)
        
        py_time = np.median(python_times)
        print(f"Python 耗时: {py_time*1000:.2f} ms")
        
        if not CPP_AVAILABLE:
            return
        
        # C++ 版本
        cpp_times = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            cpp_portfolio, cpp_cash, cpp_qty = run_backtest(
                prices, positions, initial_cash, "cash_all"
            )
            cpp_times.append(time.perf_counter() - start)
        
        cpp_time = np.median(cpp_times)
        speedup = py_time / cpp_time
        
        print(f"C++ 耗时: {cpp_time*1000:.2f} ms")
        print(f"加速比: {speedup:.2f}x")
        
        # 验证正确性
        max_error = np.abs(py_portfolio - cpp_portfolio).max()
        print(f"数值误差: {max_error:.2e}")
        
        assert max_error < 1e-4, f"数值误差过大: {max_error}"
        
        self.results.append({
            'test': 'backtest_engine',
            'shape': positions.shape,
            'python_time': py_time,
            'cpp_time': cpp_time,
            'speedup': speedup,
            'error': max_error
        })
        
        return speedup
    
    def benchmark_optimizer_kernel(self, weights_batch, signals, prices, threshold=0.5):
        """基准测试：优化器核心"""
        print(f"\n=== 优化器核心基准测试 ===")
        print(f"数据规模: weights {weights_batch.shape}, signals {signals.shape}")
        
        # Python 版本
        python_times = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            py_scores = evaluate_weights_batch_python(
                weights_batch, signals, prices, threshold
            )
            python_times.append(time.perf_counter() - start)
        
        py_time = np.median(python_times)
        print(f"Python 耗时: {py_time:.2f} s")
        
        if not CPP_AVAILABLE:
            return
        
        # C++ 版本
        cpp_times = []
        for _ in range(self.n_runs):
            start = time.perf_counter()
            cpp_scores = evaluate_weights_batch(
                weights_batch, signals, prices, threshold
            )
            cpp_times.append(time.perf_counter() - start)
        
        cpp_time = np.median(cpp_times)
        speedup = py_time / cpp_time
        
        print(f"C++ 耗时: {cpp_time:.2f} s")
        print(f"加速比: {speedup:.2f}x")
        
        # 验证正确性
        max_error = np.abs(py_scores - cpp_scores).max()
        print(f"数值误差: {max_error:.2e}")
        
        assert max_error < 1e-3, f"数值误差过大: {max_error}"
        
        self.results.append({
            'test': 'optimizer_kernel',
            'shape': weights_batch.shape,
            'python_time': py_time,
            'cpp_time': cpp_time,
            'speedup': speedup,
            'error': max_error
        })
        
        return speedup
    
    def run_all_benchmarks(self):
        """运行所有基准测试"""
        test_configs = [
            ('Small', 100, 5, 10),
            ('Medium', 1000, 10, 100),
            ('Large', 1000, 10, 10000),
            # ('Stress', 5000, 20, 50000),  # 可选
        ]
        
        for name, T, N, W in test_configs:
            print(f"\n{'='*60}")
            print(f"测试配置: {name} (T={T}, N={N}, W={W})")
            print(f"{'='*60}")
            
            signals, weights, prices = self.generate_test_data(T, N, W)
            
            # 测试 1: 信号处理
            self.benchmark_signal_processing(signals, weights)
            
            # 测试 2: 回测引擎
            _, _, positions = process_signals_python(signals, weights, 0.5)
            self.benchmark_backtest_engine(prices, positions)
            
            # 测试 3: 优化器核心（仅大规模）
            if W >= 100:
                weights_batch = weights  # 复用权重矩阵
                self.benchmark_optimizer_kernel(weights_batch, signals, prices)
    
    def generate_report(self):
        """生成测试报告"""
        if not self.results:
            print("没有测试结果")
            return
        
        df = pd.DataFrame(self.results)
        
        print("\n" + "="*60)
        print("性能基准测试报告")
        print("="*60)
        print(df.to_string(index=False))
        
        # 保存到文件
        df.to_csv('benchmark_results.csv', index=False)
        print("\n结果已保存到 benchmark_results.csv")
        
        # 检查性能目标
        print("\n" + "="*60)
        print("性能目标检查")
        print("="*60)
        
        for _, row in df.iterrows():
            test_name = row['test']
            speedup = row['speedup']
            
            # 设定目标
            if test_name == 'signal_processing':
                target = 5.0
            elif test_name == 'backtest_engine':
                target = 15.0
            elif test_name == 'optimizer_kernel':
                target = 20.0
            else:
                continue
            
            status = "✓ PASS" if speedup >= target else "✗ FAIL"
            print(f"{test_name}: {speedup:.2f}x (目标: {target:.1f}x) {status}")


if __name__ == "__main__":
    runner = BenchmarkRunner(n_runs=5)
    runner.run_all_benchmarks()
    runner.generate_report()
```

---

## 4. 性能分析工具

### 4.1 使用 Perf 分析瓶颈

```bash
# 编译 Debug 版本（包含符号）
cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo ..
make

# 运行性能分析
python -c "import backtest_cpp; perf record -g python benchmark.py"
perf report
```

### 4.2 使用 Valgrind 检测内存泄漏

```bash
valgrind --leak-check=full --show-leak-kinds=all python benchmark.py
```

### 4.3 使用 Google Benchmark（可选）

```cpp
// benchmark/cpp_benchmark.cpp
#include <benchmark/benchmark.h>
#include "backtest_engine.h"

static void BM_BacktestEngine(benchmark::State& state) {
    int n_timesteps = state.range(0);
    int n_weights = state.range(1);
    
    // 准备数据
    Eigen::VectorXf prices = Eigen::VectorXf::Random(n_timesteps);
    Eigen::MatrixXi positions = Eigen::MatrixXi::Random(n_timesteps, n_weights);
    
    BacktestConfig config;
    config.initial_cash = 1000000.0f;
    config.trade_mode = TradeMode::CASH_ALL;
    
    for (auto _ : state) {
        auto result = BacktestEngine::run_backtest(prices, positions, config);
    }
}

BENCHMARK(BM_BacktestEngine)
    ->Args({1000, 100})
    ->Args({1000, 1000})
    ->Args({1000, 10000})
    ->Unit(benchmark::kMillisecond);

BENCHMARK_MAIN();
```

---

## 5. 性能目标总结

| 测试场景          | 数据规模       | 单线程目标 | 4 线程目标 | 8 线程目标 |
|-------------------|----------------|------------|------------|------------|
| 信号处理 (Small)  | 100x5x10       | >= 5x      | >= 10x     | >= 15x     |
| 信号处理 (Medium) | 1000x10x100    | >= 10x     | >= 20x     | >= 30x     |
| 回测引擎 (Medium) | 1000x100       | >= 15x     | >= 40x     | >= 60x     |
| 回测引擎 (Large)  | 1000x10000     | >= 20x     | >= 60x     | >= 100x    |
| 优化器核心 (Large)| 1000x10x10000  | >= 30x     | >= 80x     | >= 120x    |

---

## 6. 验收标准

### 6.1 功能验收
- [ ] 通过所有单元测试
- [ ] 数值误差 < 1e-5（单精度）或 < 1e-10（双精度）
- [ ] 无内存泄漏（Valgrind 检测）

### 6.2 性能验收
- [ ] 小规模测试加速比 >= 5x
- [ ] 中等规模测试单线程加速比 >= 15x
- [ ] 大规模测试 4 线程加速比 >= 60x
- [ ] 超大规模测试能在 5 分钟内完成

### 6.3 稳定性验收
- [ ] 连续运行 100 次无崩溃
- [ ] 内存占用稳定，无持续增长
- [ ] 支持多线程并发调用

---

## 7. 常见性能问题排查

### 7.1 性能未达标
1. **检查编译优化**: 确保使用 `-O3 -march=native`
2. **检查 OpenMP**: 确认多线程已启用
3. **检查 Eigen 配置**: 确保 Eigen 使用 SIMD
4. **分析热点**: 使用 Perf/VTune 定位瓶颈

### 7.2 数值误差过大
1. **检查数据类型**: float32 vs float64
2. **检查运算顺序**: 浮点数运算非结合律
3. **检查边界条件**: NaN/Inf 处理

### 7.3 内存占用过高
1. **检查临时变量**: 使用 `.noalias()` 避免临时矩阵
2. **检查内存对齐**: Eigen 默认 16 字节对齐
3. **检查缓冲区复用**: 高频调用场景使用对象池

