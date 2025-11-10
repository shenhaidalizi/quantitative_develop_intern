"""
NPZ 结果查看器 - 将回测结果转换为 DataFrame 并展示
"""
import numpy as np
import pandas as pd
import sys
import os
from pathlib import Path


def load_npz_to_dataframes(npz_file):
    """
    读取 NPZ 文件并转换为多个 DataFrame
    
    Args:
        npz_file: .npz 文件路径
    
    Returns:
        dict: 包含多个 DataFrame 的字典
    """
    print(f"正在加载: {npz_file}")
    data = np.load(npz_file, allow_pickle=True)
    
    print(f"包含的数据项: {list(data.keys())}")
    
    results = {}
    
    # 1. 基本信息
    if 'n_timestamps' in data and 'n_weights' in data:
        n_timestamps = int(data['n_timestamps'])
        n_weights = int(data['n_weights'])
        print(f"\n数据规模: {n_timestamps} 时间步 × {n_weights} 权重组合")
    else:
        # 从矩阵形状推断
        portfolio = data['portfolio_values']
        n_timestamps, n_weights = portfolio.shape
        print(f"\n数据规模: {n_timestamps} 时间步 × {n_weights} 权重组合")
    
    # 2. 组合价值 DataFrame
    if 'portfolio_values' in data:
        portfolio = data['portfolio_values']
        
        # 创建 DataFrame（每列是一个权重组合）
        columns = [f'W{i}' for i in range(n_weights)]
        
        if 'prices' in data:
            # 使用价格索引作为时间
            index = np.arange(n_timestamps)
        else:
            index = np.arange(n_timestamps)
        
        df_portfolio = pd.DataFrame(portfolio, columns=columns, index=index)
        df_portfolio.index.name = 'Timestep'
        results['portfolio_values'] = df_portfolio
        
        print(f"\n✓ 组合价值 DataFrame: {df_portfolio.shape}")
    
    # 3. 现金 DataFrame
    if 'cash_matrix' in data:
        cash = data['cash_matrix']
        df_cash = pd.DataFrame(cash, columns=columns, index=index)
        df_cash.index.name = 'Timestep'
        results['cash'] = df_cash
        
        print(f"✓ 现金 DataFrame: {df_cash.shape}")
    
    # 4. 持仓数量 DataFrame
    if 'quantity_matrix' in data:
        qty = data['quantity_matrix']
        df_qty = pd.DataFrame(qty, columns=columns, index=index)
        df_qty.index.name = 'Timestep'
        results['quantity'] = df_qty
        
        print(f"✓ 持仓数量 DataFrame: {df_qty.shape}")
    
    # 5. 价格序列 DataFrame
    if 'prices' in data:
        prices = data['prices']
        df_prices = pd.DataFrame({
            'Price': prices
        }, index=index)
        df_prices.index.name = 'Timestep'
        results['prices'] = df_prices
        
        print(f"✓ 价格 DataFrame: {df_prices.shape}")
    
    # 6. 持仓信号 DataFrame
    if 'positions' in data:
        positions = data['positions']
        df_positions = pd.DataFrame(positions, columns=columns, index=index)
        df_positions.index.name = 'Timestep'
        results['positions'] = df_positions
        
        print(f"✓ 持仓信号 DataFrame: {df_positions.shape}")
    
    return results, data


def calculate_summary_stats(results):
    """计算汇总统计信息"""
    if 'portfolio_values' not in results:
        return None
    
    df = results['portfolio_values']
    
    # 计算每个权重组合的统计信息
    stats = pd.DataFrame({
        'Initial_Value': df.iloc[0],
        'Final_Value': df.iloc[-1],
        'Total_Return_Pct': (df.iloc[-1] / df.iloc[0] - 1) * 100,
        'Max_Value': df.max(),
        'Min_Value': df.min(),
        'Mean_Value': df.mean(),
        'Std_Value': df.std(),
    })
    
    # 计算收益率
    returns = df.pct_change().fillna(0)
    
    stats['Mean_Return_Pct'] = returns.mean() * 100
    stats['Std_Return_Pct'] = returns.std() * 100
    stats['Sharpe_Ratio'] = (returns.mean() / returns.std()) * np.sqrt(252)  # 年化
    
    # 最大回撤
    cummax = df.cummax()
    drawdown = (df - cummax) / cummax
    stats['Max_Drawdown_Pct'] = drawdown.min() * 100
    
    return stats


def display_results(npz_file, top_n=10, save_csv=False):
    """
    显示 NPZ 结果
    
    Args:
        npz_file: .npz 文件路径
        top_n: 显示前 N 个最佳权重组合
        save_csv: 是否保存为 CSV
    """
    print("="*70)
    print("回测结果查看器")
    print("="*70)
    
    # 加载数据
    results, raw_data = load_npz_to_dataframes(npz_file)
    
    # 显示配置信息
    print("\n" + "="*70)
    print("配置信息")
    print("="*70)
    
    if 'initial_cash' in raw_data:
        print(f"初始资金: {float(raw_data['initial_cash']):,.2f}")
    
    if 'trade_mode' in raw_data:
        trade_mode = str(raw_data['trade_mode'])
        print(f"交易模式: {trade_mode}")
    
    if 'max_allocation_pct' in raw_data:
        print(f"最大仓位比例: {float(raw_data['max_allocation_pct']):.1%}")
    
    if 'elapsed_time_ms' in raw_data:
        print(f"计算耗时: {float(raw_data['elapsed_time_ms']):.2f} ms")
    
    # 计算汇总统计
    print("\n" + "="*70)
    print("汇总统计")
    print("="*70)
    
    stats = calculate_summary_stats(results)
    
    if stats is not None:
        # 按总收益率排序
        stats_sorted = stats.sort_values('Total_Return_Pct', ascending=False)
        
        print(f"\n前 {top_n} 个最佳权重组合:")
        print("-"*70)
        
        # 只显示关键列
        display_cols = ['Final_Value', 'Total_Return_Pct', 'Sharpe_Ratio', 
                       'Max_Drawdown_Pct']
        print(stats_sorted[display_cols].head(top_n).to_string())
        
        print("\n\n全体权重组合统计:")
        print("-"*70)
        print(stats[display_cols].describe().to_string())
        
        # 找出最佳权重组合
        best_idx = stats_sorted.index[0]
        print(f"\n🏆 最佳权重组合: {best_idx}")
        print("-"*70)
        print(stats_sorted.loc[best_idx].to_string())
    
    # 显示价格信息
    if 'prices' in results:
        df_prices = results['prices']
        print("\n" + "="*70)
        print("价格序列统计")
        print("="*70)
        print(df_prices.describe().to_string())
    
    # 保存为 CSV
    if save_csv:
        output_dir = Path(npz_file).parent / "csv_output"
        output_dir.mkdir(exist_ok=True)
        
        base_name = Path(npz_file).stem
        
        for key, df in results.items():
            csv_file = output_dir / f"{base_name}_{key}.csv"
            df.to_csv(csv_file)
            print(f"\n✓ 已保存: {csv_file}")
        
        if stats is not None:
            stats_file = output_dir / f"{base_name}_summary_stats.csv"
            stats.to_csv(stats_file)
            print(f"✓ 已保存: {stats_file}")
    
    return results, stats


def compare_two_results(file1, file2):
    """对比两个 NPZ 文件的结果"""
    print("="*70)
    print("对比两个结果文件")
    print("="*70)
    
    print(f"\n文件 1: {file1}")
    print(f"文件 2: {file2}")
    
    data1 = np.load(file1)
    data2 = np.load(file2)
    
    # 对比组合价值
    portfolio1 = data1['portfolio_values']
    portfolio2 = data2['portfolio_values']
    
    diff = np.abs(portfolio1 - portfolio2)
    
    print(f"\n组合价值矩阵差异:")
    print(f"  最大误差: {diff.max():.2e}")
    print(f"  平均误差: {diff.mean():.2e}")
    print(f"  中位数误差: {np.median(diff):.2e}")
    print(f"  标准差: {diff.std():.2e}")
    
    # 误差分布
    print(f"\n误差分布:")
    print(f"  < 1e-8: {(diff < 1e-8).sum()} ({(diff < 1e-8).mean()*100:.1f}%)")
    print(f"  < 1e-6: {(diff < 1e-6).sum()} ({(diff < 1e-6).mean()*100:.1f}%)")
    print(f"  < 1e-4: {(diff < 1e-4).sum()} ({(diff < 1e-4).mean()*100:.1f}%)")
    print(f"  >= 1e-4: {(diff >= 1e-4).sum()} ({(diff >= 1e-4).mean()*100:.1f}%)")
    
    # 最大误差位置
    max_idx = np.unravel_index(diff.argmax(), diff.shape)
    print(f"\n最大误差位置: 时间步 {max_idx[0]}, 权重 {max_idx[1]}")
    print(f"  文件1 值: {portfolio1[max_idx]:.6f}")
    print(f"  文件2 值: {portfolio2[max_idx]:.6f}")
    print(f"  差异: {diff[max_idx]:.6e}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  查看单个文件:")
        print("    python view_results.py <file.npz> [--save-csv] [--top N]")
        print("  对比两个文件:")
        print("    python view_results.py <file1.npz> <file2.npz> --compare")
        print("\n示例:")
        print("  python view_results.py ../output/python_vectorized_output.npz")
        print("  python view_results.py ../output/python_vectorized_output.npz --save-csv --top 20")
        print("  python view_results.py ../output/python_output.npz ../output/cpp_output.npz --compare")
        sys.exit(1)
    
    # 解析参数
    npz_file = sys.argv[1]
    save_csv = '--save-csv' in sys.argv
    compare_mode = '--compare' in sys.argv
    
    top_n = 10
    if '--top' in sys.argv:
        idx = sys.argv.index('--top')
        if idx + 1 < len(sys.argv):
            top_n = int(sys.argv[idx + 1])
    
    if not os.path.exists(npz_file):
        print(f"错误: 文件不存在: {npz_file}")
        sys.exit(1)
    
    # 对比模式
    if compare_mode:
        if len(sys.argv) < 3:
            print("错误: 对比模式需要两个文件")
            sys.exit(1)
        
        file2 = sys.argv[2]
        if not os.path.exists(file2):
            print(f"错误: 文件不存在: {file2}")
            sys.exit(1)
        
        compare_two_results(npz_file, file2)
    else:
        # 查看模式
        display_results(npz_file, top_n=top_n, save_csv=save_csv)


if __name__ == "__main__":
    main()