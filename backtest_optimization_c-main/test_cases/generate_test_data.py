"""
测试数据生成脚本

生成用于验证 C++ 实现正确性的测试数据和期望输出
"""
import numpy as np
import pandas as pd
import argparse
import sys
import os

# 添加参考实现到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from reference_impl import (
    process_signals_python,
    run_backtest_python,
    evaluate_weights_batch_python
)


def generate_price_data(n_timesteps=1000, initial_price=100.0, volatility=0.02, seed=42):
    """
    生成模拟价格数据（几何布朗运动）
    """
    np.random.seed(seed)
    
    # 生成日收益率
    returns = np.random.normal(0.0005, volatility, n_timesteps)
    
    # 累积生成价格
    prices = initial_price * np.exp(np.cumsum(returns))
    prices = prices.astype(np.float32)
    
    # 生成 OHLCV 数据
    noise = np.random.uniform(-0.01, 0.01, n_timesteps)
    df = pd.DataFrame({
        'timestamp': pd.date_range('2020-01-01', periods=n_timesteps, freq='D'),
        'open': prices * (1 + noise),
        'high': prices * (1 + np.abs(noise) + 0.005),
        'low': prices * (1 - np.abs(noise) - 0.005),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, n_timesteps),
        'vol': np.random.randint(1000000, 10000000, n_timesteps)  # 别名
    })
    
    return df


def generate_signals(prices, n_signals=10, seed=42):
    """
    生成技术指标信号
    """
    np.random.seed(seed)
    n_timesteps = len(prices)
    signals = []
    
    # 趋势信号：均线差分
    for period in [5, 20, 60]:
        ma = pd.Series(prices).rolling(period).mean()
        signal = ((prices - ma) / ma).values
        signals.append(signal)
    
    # 动量信号
    for period in [5, 10, 20]:
        momentum = pd.Series(prices).pct_change(period).values
        signals.append(momentum)
    
    # RSI 信号
    for period in [14, 28]:
        delta = pd.Series(prices).diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi_normalized = ((rsi - 50) / 50).values
        signals.append(rsi_normalized)
    
    # 补充随机信号
    while len(signals) < n_signals:
        noise = np.random.randn(n_timesteps) * 0.1
        signals.append(noise)
    
    # 堆叠并处理
    signal_matrix = np.column_stack(signals[:n_signals])
    signal_matrix = np.nan_to_num(signal_matrix, nan=0.0)
    signal_matrix = np.clip(signal_matrix, -1.0, 1.0)
    
    return signal_matrix.astype(np.float32)


def generate_weights(n_signals=10, n_weights=100, seed=42):
    """
    生成权重矩阵
    """
    np.random.seed(seed)
    weights = []
    
    # 等权重
    for _ in range(int(n_weights * 0.1)):
        w = np.ones(n_signals) / n_signals
        weights.append(w)
    
    # 随机权重
    for _ in range(int(n_weights * 0.5)):
        w = np.random.randn(n_signals)
        weights.append(w)
    
    # 偏向特定信号
    for _ in range(int(n_weights * 0.3)):
        w = np.random.randn(n_signals) * 0.3
        idx = np.random.randint(n_signals)
        w[idx] += np.random.uniform(1.0, 3.0)
        weights.append(w)
    
    # 极端权重
    for _ in range(int(n_weights * 0.1)):
        w = np.zeros(n_signals)
        w[np.random.randint(n_signals)] = np.random.choice([5.0, -5.0])
        weights.append(w)
    
    # 补齐
    while len(weights) < n_weights:
        w = np.random.randn(n_signals)
        weights.append(w)
    
    weight_matrix = np.column_stack(weights[:n_weights]).astype(np.float32)
    return weight_matrix


def generate_expected_output(prices, signals, weights, threshold=0.5):
    """
    生成期望输出
    """
    print("生成期望输出...")
    
    # 信号处理
    combined, long_short, positions = process_signals_python(signals, weights, threshold)
    print(f"  ✓ 信号处理完成")
    
    # 回测
    portfolio_values, cash, quantities = run_backtest_python(
        prices, positions,
        initial_cash=1000000.0,
        trade_mode="portfolio_pct",
        max_allocation_pct=0.5
    )
    print(f"  ✓ 回测完成")
    
    # 计算指标
    from reference_impl.metrics import (
        calculate_sharpe_ratio_python,
        calculate_max_drawdown_python,
        calculate_total_return_python
    )
    
    sharpe = calculate_sharpe_ratio_python(portfolio_values)
    max_dd = calculate_max_drawdown_python(portfolio_values)
    total_ret = calculate_total_return_python(portfolio_values)
    print(f"  ✓ 指标计算完成")
    
    return {
        'combined_signals': combined,
        'long_short_matrix': long_short,
        'position_matrix': positions,
        'portfolio_values': portfolio_values,
        'cash_matrix': cash,
        'quantity_matrix': quantities,
        'sharpe_ratios': sharpe,
        'max_drawdowns': max_dd,
        'total_returns': total_ret
    }


def main():
    parser = argparse.ArgumentParser(description='生成测试数据')
    parser.add_argument('--timesteps', type=int, default=1000, help='时间步数')
    parser.add_argument('--signals', type=int, default=10, help='信号数')
    parser.add_argument('--weights', type=int, default=100, help='权重组合数')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    parser.add_argument('--output-dir', type=str, default='.', help='输出目录')
    
    args = parser.parse_args()
    
    print("="*60)
    print("测试数据生成")
    print("="*60)
    print(f"配置:")
    print(f"  时间步数: {args.timesteps}")
    print(f"  信号数: {args.signals}")
    print(f"  权重组合数: {args.weights}")
    print(f"  随机种子: {args.seed}")
    print()
    
    # 生成价格数据
    print("1. 生成价格数据...")
    df = generate_price_data(args.timesteps, seed=args.seed)
    prices = df['close'].values
    print(f"   价格范围: [{prices.min():.2f}, {prices.max():.2f}]")
    
    # 保存价格数据
    output_path = os.path.join(args.output_dir, 'sample_data.parquet')
    df.to_parquet(output_path)
    print(f"   已保存: {output_path}")

    # ✅ 同时保存 close 价格为 .npy 格式，供 C++ 读取
    npy_price_path = os.path.join(args.output_dir, 'sample_prices.npy')
    np.save(npy_price_path, prices.astype(np.float32))
    print(f"   ✅ 已保存 numpy 二进制文件: {npy_price_path}")
    
    # 生成信号数据
    print("\n2. 生成信号数据...")
    signals = generate_signals(prices, args.signals, seed=args.seed)
    print(f"   信号矩阵形状: {signals.shape}")
    print(f"   信号范围: [{signals.min():.4f}, {signals.max():.4f}]")
    
    # 保存信号数据
    output_path = os.path.join(args.output_dir, 'sample_signals.npy')
    np.save(output_path, signals)
    print(f"   已保存: {output_path}")
    
    # 生成权重数据
    print("\n3. 生成权重数据...")
    weights = generate_weights(args.signals, args.weights, seed=args.seed)
    print(f"   权重矩阵形状: {weights.shape}")
    print(f"   权重范围: [{weights.min():.4f}, {weights.max():.4f}]")
    
    # 保存权重数据
    output_path = os.path.join(args.output_dir, 'sample_weights.npy')
    np.save(output_path, weights)
    print(f"   已保存: {output_path}")
    
    # 生成期望输出
    print("\n4. 生成期望输出...")
    expected = generate_expected_output(prices, signals, weights)
    
    print(f"   组合价值形状: {expected['portfolio_values'].shape}")
    print(f"   夏普比率统计: min={expected['sharpe_ratios'].min():.4f}, "
          f"max={expected['sharpe_ratios'].max():.4f}, "
          f"mean={expected['sharpe_ratios'].mean():.4f}")
    
    # 保存期望输出
    output_path = os.path.join(args.output_dir, 'expected_output.npz')
    np.savez_compressed(output_path, **expected)
    print(f"   已保存: {output_path}")

    # ✅ 同时导出主要矩阵为单独的 .npy 文件（C++ 更容易读）
    for key in ['portfolio_values', 'cash_matrix', 'quantity_matrix']:
        np.save(os.path.join(args.output_dir, f"{key}.npy"), expected[key])
        print(f"   ✅ 导出单独矩阵: {key}.npy  shape={expected[key].shape}")
    
    print("\n" + "="*60)
    print("✓ 测试数据生成完成！")
    print("="*60)
    print(f"\n生成的文件:")
    print(f"  - sample_data.parquet   ({os.path.getsize(os.path.join(args.output_dir, 'sample_data.parquet')) / 1024:.1f} KB)")
    print(f"  - sample_signals.npy    ({os.path.getsize(os.path.join(args.output_dir, 'sample_signals.npy')) / 1024:.1f} KB)")
    print(f"  - sample_weights.npy    ({os.path.getsize(os.path.join(args.output_dir, 'sample_weights.npy')) / 1024:.1f} KB)")
    print(f"  - expected_output.npz   ({os.path.getsize(os.path.join(args.output_dir, 'expected_output.npz')) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

