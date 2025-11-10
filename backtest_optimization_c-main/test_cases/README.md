# 测试用例说明

## 1. 测试数据说明

### 1.1 数据文件列表

| 文件名                  | 格式      | 说明                       | 大小   |
|-------------------------|-----------|----------------------------|--------|
| `sample_data.parquet`   | Parquet   | 样本价格数据（OHLCV）      | ~100KB |
| `sample_signals.npy`    | NumPy     | 样本信号矩阵               | ~80KB  |
| `sample_weights.npy`    | NumPy     | 样本权重矩阵               | ~8KB   |
| `expected_output.npz`   | NumPy     | 期望输出结果（用于验证）   | ~200KB |

### 1.2 数据规模

```python
# 数据维度
n_timesteps = 1000    # 1000 个交易日（约 4 年）
n_signals = 10        # 10 个信号
n_weights = 100       # 100 个权重组合

# 数据类型
prices: float32       # 价格序列
signals: float32      # 信号值矩阵
weights: float32      # 权重矩阵
```

---

## 2. 测试脚本说明

### 2.1 test_runner.py

**功能**: 单元测试和正确性验证

```bash
# 运行所有测试
python test_runner.py

# 运行特定测试
python test_runner.py --test signal_processing
python test_runner.py --test backtest_engine
python test_runner.py --test optimizer_kernel
```

**测试内容**:
- 数值精度测试（与期望输出对比）
- 边界条件测试（空数组、单元素、异常输入）
- 一致性测试（C++ vs Python）

---

### 2.2 benchmark.py

**功能**: 性能基准测试

```bash
# 运行性能测试
python benchmark.py

# 指定测试规模
python benchmark.py --scale small   # 100x5x10
python benchmark.py --scale medium  # 1000x10x100
python benchmark.py --scale large   # 1000x10x10000

# 指定线程数
python benchmark.py --threads 4

# 生成详细报告
python benchmark.py --report
```

**输出**:
- 执行时间对比
- 加速比统计
- 内存使用情况
- CSV 格式报告

---

### 2.3 generate_test_data.py

**功能**: 生成测试数据文件

```bash
# 生成所有测试数据
python generate_test_data.py

# 生成特定规模数据
python generate_test_data.py --timesteps 1000 --signals 10 --weights 100
```

---

## 3. 数据生成逻辑

### 3.1 价格数据生成

模拟真实股票价格走势：

```python
def generate_price_data(n_timesteps=1000, initial_price=100.0, volatility=0.02):
    """
    生成符合几何布朗运动的价格序列
    
    dS = μ*S*dt + σ*S*dW
    """
    np.random.seed(42)
    
    # 生成日收益率
    returns = np.random.normal(0.0005, volatility, n_timesteps)
    
    # 累积收益生成价格
    prices = initial_price * np.exp(np.cumsum(returns))
    
    # 生成 OHLCV 数据
    df = pd.DataFrame({
        'timestamp': pd.date_range('2020-01-01', periods=n_timesteps, freq='D'),
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, n_timesteps)),
        'high': prices * (1 + np.random.uniform(0.0, 0.02, n_timesteps)),
        'low': prices * (1 + np.random.uniform(-0.02, 0.0, n_timesteps)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, n_timesteps)
    })
    
    return df
```

### 3.2 信号数据生成

生成多样化的技术指标信号：

```python
def generate_signals(prices, n_signals=10):
    """
    生成多个技术指标信号
    
    信号类型:
    1. 趋势信号（MA Cross, MACD）
    2. 动量信号（RSI, Momentum）
    3. 波动率信号（Bollinger Bands, ATR）
    4. 成交量信号（OBV）
    """
    signals = []
    
    # 信号 1-3: 不同周期的均线差分
    for period in [5, 20, 60]:
        ma = prices.rolling(period).mean()
        signal = (prices - ma) / ma  # 归一化
        signals.append(signal.values)
    
    # 信号 4-6: 动量指标
    for period in [5, 10, 20]:
        momentum = prices.pct_change(period)
        signals.append(momentum.values)
    
    # 信号 7-8: RSI
    for period in [14, 28]:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_normalized = (rsi - 50) / 50  # 归一化到 [-1, 1]
        signals.append(rsi_normalized.values)
    
    # 信号 9-10: 随机信号（噪声）
    for _ in range(2):
        noise = np.random.randn(len(prices)) * 0.1
        signals.append(noise)
    
    # 堆叠为矩阵并填充 NaN
    signal_matrix = np.column_stack(signals)
    signal_matrix = np.nan_to_num(signal_matrix, nan=0.0)
    
    # 截断到 [-1, 1]
    signal_matrix = np.clip(signal_matrix, -1.0, 1.0)
    
    return signal_matrix.astype(np.float32)
```

### 3.3 权重数据生成

生成多组随机权重和典型权重组合：

```python
def generate_weights(n_signals=10, n_weights=100):
    """
    生成权重矩阵
    
    权重组合策略:
    - 10% 等权重
    - 30% 纯随机权重
    - 30% 偏向趋势信号
    - 20% 偏向动量信号
    - 10% 极端权重（测试边界）
    """
    np.random.seed(42)
    weights = []
    
    # 等权重组合
    for _ in range(int(n_weights * 0.1)):
        w = np.ones(n_signals) / n_signals
        weights.append(w)
    
    # 纯随机权重
    for _ in range(int(n_weights * 0.3)):
        w = np.random.randn(n_signals)
        weights.append(w)
    
    # 偏向趋势信号（前 3 个）
    for _ in range(int(n_weights * 0.3)):
        w = np.random.randn(n_signals) * 0.3
        w[:3] += np.random.uniform(0.5, 2.0, 3)
        weights.append(w)
    
    # 偏向动量信号（4-6）
    for _ in range(int(n_weights * 0.2)):
        w = np.random.randn(n_signals) * 0.3
        w[3:6] += np.random.uniform(0.5, 2.0, 3)
        weights.append(w)
    
    # 极端权重（边界测试）
    for _ in range(int(n_weights * 0.1)):
        w = np.zeros(n_signals)
        w[np.random.randint(n_signals)] = np.random.choice([10.0, -10.0])
        weights.append(w)
    
    weight_matrix = np.column_stack(weights).astype(np.float32)
    return weight_matrix
```

---

## 4. 期望输出生成

运行 Python 参考实现生成期望输出：

```python
def generate_expected_output(prices, signals, weights, threshold=0.5):
    """
    使用 Python 参考实现生成期望输出
    """
    from reference_impl import (
        process_signals_python,
        run_backtest_python,
        calculate_sharpe_ratio_python
    )
    
    # Step 1: 信号处理
    combined, long_short, positions = process_signals_python(
        signals, weights, threshold
    )
    
    # Step 2: 回测
    portfolio_values, cash, quantities = run_backtest_python(
        prices, positions, 
        initial_cash=1000000.0,
        trade_mode="portfolio_pct"
    )
    
    # Step 3: 计算指标
    sharpe_ratios = calculate_sharpe_ratio_python(portfolio_values)
    
    # 保存
    np.savez_compressed(
        'expected_output.npz',
        combined_signals=combined,
        long_short_matrix=long_short,
        position_matrix=positions,
        portfolio_values=portfolio_values,
        cash_matrix=cash,
        quantity_matrix=quantities,
        sharpe_ratios=sharpe_ratios
    )
```

---

## 5. 测试流程

### 5.1 正确性测试流程

```
1. 加载测试数据
   ↓
2. 运行 C++ 实现
   ↓
3. 加载期望输出
   ↓
4. 逐项对比
   ↓
5. 计算误差统计
   ↓
6. 生成测试报告
```

### 5.2 测试通过标准

| 测试项            | 标准                  |
|-------------------|-----------------------|
| 信号组合          | 最大误差 < 1e-5       |
| 回测引擎          | 最大误差 < 1e-4       |
| 性能指标          | 最大误差 < 1e-3       |
| 整体流程          | 端到端误差 < 1e-3     |

---

## 6. 使用示例

### 6.1 快速测试

```bash
# 1. 生成测试数据
cd test_cases
python generate_test_data.py

# 2. 运行测试
python test_runner.py

# 预期输出:
# ✓ 信号处理测试通过 (误差: 3.2e-7)
# ✓ 回测引擎测试通过 (误差: 1.5e-5)
# ✓ 优化器核心测试通过 (误差: 8.7e-4)
# ✓ 所有测试通过!
```

### 6.2 性能测试

```bash
# 运行性能基准测试
python benchmark.py --scale medium --threads 4

# 预期输出:
# === 性能基准测试 (Medium) ===
# Python 耗时: 245.3 ms
# C++ 耗时 (1 线程): 16.8 ms (加速比: 14.6x)
# C++ 耗时 (4 线程): 5.2 ms (加速比: 47.2x)
```

### 6.3 调试单个模块

```python
# test_debug.py
import numpy as np
from backtest_cpp import process_signals

# 加载数据
data = np.load('sample_signals.npy')
weights = np.load('sample_weights.npy')

# 运行单个函数
combined, long_short, positions = process_signals(data, weights, 0.5)

# 检查输出
print(f"Combined shape: {combined.shape}")
print(f"Long/Short unique values: {np.unique(long_short)}")
print(f"Position stats: min={positions.min()}, max={positions.max()}")
```

---

## 7. 故障排除

### 7.1 数值误差过大

**问题**: 测试显示误差超过阈值

**排查步骤**:
1. 检查数据类型是否一致（float32 vs float64）
2. 检查随机种子是否固定
3. 使用小规模数据逐步对比中间结果
4. 检查边界条件处理（NaN、Inf、除零）

### 7.2 性能未达标

**问题**: C++ 实现加速比不足

**排查步骤**:
1. 确认编译优化已开启（`-O3 -march=native`）
2. 检查 OpenMP 是否生效（`echo $OMP_NUM_THREADS`）
3. 使用 Perf 分析热点函数
4. 检查内存访问模式是否缓存友好

### 7.3 测试崩溃

**问题**: 运行时段错误或内存访问违规

**排查步骤**:
1. 使用 Valgrind 检测内存问题
2. 检查数组边界访问
3. 添加 C++ 异常捕获
4. 使用调试模式编译（`-g -O0`）

---

## 8. 扩展测试

### 8.1 压力测试

```python
# stress_test.py
def stress_test():
    """压力测试：超大规模数据"""
    configs = [
        (5000, 20, 50000),   # 极大权重数
        (10000, 50, 1000),   # 极长时间序列
        (1000, 100, 10000),  # 极多信号
    ]
    
    for T, N, W in configs:
        print(f"Testing T={T}, N={N}, W={W}")
        # ... 测试逻辑
```

### 8.2 鲁棒性测试

```python
# robustness_test.py
def test_edge_cases():
    """边界条件测试"""
    # 1. 全零数据
    # 2. 全 NaN 数据
    # 3. 极端大小值
    # 4. 不连续数据
    # 5. 负价格（异常）
```

---

## 9. 参考资料

- NumPy 测试框架: https://numpy.org/doc/stable/reference/routines.testing.html
- Pytest 文档: https://docs.pytest.org/
- Google Test (C++): https://google.github.io/googletest/

