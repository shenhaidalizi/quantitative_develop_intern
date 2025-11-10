"""
综合测试脚本：验证所有优化功能
"""

import time
import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preprocess_data import (
    save_data_as_parquet, 
    load_data_from_parquet,
    OUTPUT_DIR
)
from timely_data import get_z_score, CONFIG


class TestResults:
    """测试结果收集器"""
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
    
    def add_result(self, test_name, passed, message="", duration=None):
        self.results[test_name] = {
            'passed': passed,
            'message': message,
            'duration': duration
        }
    
    def print_summary(self):
        print("\n" + "="*70)
        print("测试总结")
        print("="*70)
        
        passed_count = sum(1 for r in self.results.values() if r['passed'])
        total_count = len(self.results)
        
        for test_name, result in self.results.items():
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            duration_str = f" ({result['duration']:.2f}秒)" if result['duration'] else ""
            print(f"{status} | {test_name}{duration_str}")
            if result['message']:
                print(f"       {result['message']}")
        
        print("="*70)
        print(f"总计: {passed_count}/{total_count} 测试通过")
        print(f"总耗时: {time.time() - self.start_time:.2f}秒")
        print("="*70)


def generate_time_str(index):
    """生成合法的交易时间字符串"""
    base_time = datetime.strptime("09:31:00", "%H:%M:%S")
    new_time = base_time + timedelta(minutes=index)
    return new_time.strftime("%H:%M:%S")


def generate_test_data(num_times=10, num_stocks=100):
    """生成测试数据"""
    print(f"📊 生成测试数据: {num_times}个时间点 × {num_stocks}只股票...")
    
    final_data = {}
    for i in range(num_times):
        time_str = generate_time_str(i)
        final_data[time_str] = {}
        
        for j in range(num_stocks):
            stock_code = f"60{j:04d}"
            final_data[time_str][stock_code] = {
                'rolling1': {
                    'mean': round(np.random.uniform(100, 10000), 2),
                    'std': round(np.random.uniform(10, 500), 2)
                },
                'rolling5': {
                    'mean': round(np.random.uniform(500, 50000), 2),
                    'std': round(np.random.uniform(50, 2500), 2)
                },
                'rolling10': {
                    'mean': round(np.random.uniform(1000, 100000), 2),
                    'std': round(np.random.uniform(100, 5000), 2)
                },
                'rolling30': {
                    'mean': round(np.random.uniform(3000, 300000), 2),
                    'std': round(np.random.uniform(300, 15000), 2)
                },
                'rolling_full': {
                    'mean': round(np.random.uniform(5000, 500000), 2),
                    'std': round(np.random.uniform(500, 25000), 2)
                }
            }
    
    return final_data


def test_parquet_performance(test_data, results):
    """测试1: Parquet读写性能"""
    print("\n📈 测试1: Parquet读写性能...")
    
    test_file = os.path.join(OUTPUT_DIR, "test_performance.parquet")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 写入测试
    start_time = time.time()
    save_data_as_parquet(test_data, test_file.replace('.parquet', '.json'))
    write_time = time.time() - start_time
    
    file_size = os.path.getsize(test_file) / (1024 * 1024)
    print(f"  ✓ 写入耗时: {write_time:.3f}秒")
    print(f"  ✓ 文件大小: {file_size:.2f} MB")
    
    # 读取测试
    start_time = time.time()
    loaded_data = load_data_from_parquet(test_file)
    read_time = time.time() - start_time
    
    print(f"  ✓ 读取耗时: {read_time:.3f}秒")
    
    # 清理
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # 性能判断
    passed = write_time < 5 and read_time < 3
    message = f"写入: {write_time:.3f}秒, 读取: {read_time:.3f}秒, 文件: {file_size:.2f}MB"
    results.add_result("Parquet读写性能", passed, message, write_time + read_time)


def test_data_integrity(test_data, results):
    """测试2: 数据完整性"""
    print("\n🔍 测试2: 数据完整性检查...")
    
    test_file = os.path.join(OUTPUT_DIR, "test_integrity.parquet")
    
    # 保存和读取
    save_data_as_parquet(test_data, test_file.replace('.parquet', '.json'))
    loaded_data = load_data_from_parquet(test_file)
    
    # 检查时间点数量
    time_check = len(test_data) == len(loaded_data)
    print(f"  {'✓' if time_check else '✗'} 时间点数量: {len(test_data)} == {len(loaded_data)}")
    
    # 检查股票数量
    stock_counts_match = True
    for time_str in test_data.keys():
        if len(test_data[time_str]) != len(loaded_data.get(time_str, {})):
            stock_counts_match = False
            break
    print(f"  {'✓' if stock_counts_match else '✗'} 股票数量匹配")
    
    # 检查数值精度
    precision_check = True
    sample_time = list(test_data.keys())[0]
    sample_stock = list(test_data[sample_time].keys())[0]
    
    original = test_data[sample_time][sample_stock]['rolling5']['mean']
    loaded = loaded_data[sample_time][sample_stock]['rolling5']['mean']
    diff = abs(original - loaded)
    
    if diff > 0.01:
        precision_check = False
    print(f"  {'✓' if precision_check else '✗'} 数值精度: 误差={diff:.6f}")
    
    # 清理
    if os.path.exists(test_file):
        os.remove(test_file)
    
    passed = time_check and stock_counts_match and precision_check
    message = f"时间点: {time_check}, 股票数: {stock_counts_match}, 精度: {precision_check}"
    results.add_result("数据完整性", passed, message)


def test_zero_handling(results):
    """测试3: 0值处理优化"""
    print("\n🔢 测试3: 0值处理优化...")
    
    test_df = pd.DataFrame({
        'rolling5': [100, 200, 100, 150],
        'rolling5_mean': [100, 200, 100, 150],
        'rolling5_std': [10, 0, 0, 20]
    })
    
    print("  测试场景:")
    print("  - 场景1: std=10, diff=0 → 期望z-score=0")
    print("  - 场景2: std=0, diff=0 → 期望z-score=0")
    print("  - 场景3: std=0, diff=0 → 期望z-score=0")
    print("  - 场景4: std=20, diff=0 → 期望z-score=0")
    
    result_df = get_z_score(test_df, [5])
    z_scores = result_df['rolling5_z_score'].values
    
    finite_check = np.all(np.isfinite(z_scores))
    print(f"  {'✓' if finite_check else '✗'} 所有z-score为有限值: {z_scores}")
    
    zero_diff_zero_std = z_scores[1] == 0 and z_scores[2] == 0
    print(f"  {'✓' if zero_diff_zero_std else '✗'} std=0且diff=0时z-score=0")
    
    normal_zero = z_scores[0] == 0 and z_scores[3] == 0
    print(f"  {'✓' if normal_zero else '✗'} 正常情况下z-score正确")
    
    passed = finite_check and zero_diff_zero_std and normal_zero
    message = f"有限值: {finite_check}, 零处理: {zero_diff_zero_std}, 正常值: {normal_zero}"
    results.add_result("0值处理优化", passed, message)


def test_extreme_std_handling(results):
    """测试4: 极端标准差处理"""
    print("\n⚡ 测试4: 极端标准差处理...")
    
    test_df = pd.DataFrame({
        'rolling5': [1000, 2000, 3000, 100],
        'rolling5_mean': [100, 100, 100, 100],
        'rolling5_std': [0.000001, 0, 0.000001, 10]
    })
    
    result_df = get_z_score(test_df, [5])
    z_scores = result_df['rolling5_z_score'].values
    
    print(f"  测试结果:")
    print(f"  - 极小std (1e-6), 大diff (900): z={z_scores[0]:.2f}")
    print(f"  - 零std, 大diff (1900): z={z_scores[1]:.2f}")
    print(f"  - 极小std, 大diff (2900): z={z_scores[2]:.2f}")
    print(f"  - 正常std (10), 小diff (0): z={z_scores[3]:.2f}")
    
    extreme_handled = np.all(np.abs(z_scores[:3]) >= 3) and np.all(np.abs(z_scores[:3]) <= 5)
    normal_correct = z_scores[3] == 0
    
    passed = extreme_handled and normal_correct
    message = f"极端处理: {extreme_handled}, 正常处理: {normal_correct}"
    results.add_result("极端标准差处理", passed, message)


def test_file_size_reduction(test_data, results):
    """测试5: 文件大小优化"""
    print("\n💾 测试5: 文件大小优化（15天 vs 30天）...")
    
    large_data_15 = {}
    large_data_30 = {}
    
    for i in range(240):
        time_str = generate_time_str(i)
        large_data_15[time_str] = test_data[list(test_data.keys())[0]].copy()
    
    for i in range(480):
        time_str = generate_time_str(i)
        large_data_30[time_str] = test_data[list(test_data.keys())[0]].copy()
    
    file_15 = os.path.join(OUTPUT_DIR, "test_15days.parquet")
    file_30 = os.path.join(OUTPUT_DIR, "test_30days.parquet")
    
    save_data_as_parquet(large_data_15, file_15.replace('.parquet', '.json'))
    size_15 = os.path.getsize(file_15) / (1024 * 1024)
    
    save_data_as_parquet(large_data_30, file_30.replace('.parquet', '.json'))
    size_30 = os.path.getsize(file_30) / (1024 * 1024)
    
    reduction_percent = (1 - size_15 / size_30) * 100
    
    print(f"  ✓ 15天数据文件: {size_15:.2f} MB")
    print(f"  ✓ 30天数据文件: {size_30:.2f} MB")
    print(f"  ✓ 减少比例: {reduction_percent:.1f}%")
    
    for f in [file_15, file_30]:
        if os.path.exists(f):
            os.remove(f)
    
    passed = reduction_percent > 40
    message = f"15天: {size_15:.2f}MB, 30天: {size_30:.2f}MB, 减少: {reduction_percent:.1f}%"
    results.add_result("文件大小优化", passed, message)


def test_nan_handling(results):
    """测试6: NaN处理"""
    print("\n🔍 测试6: NaN处理（缺失数据时不再设为0）...")
    
    test_df = pd.DataFrame({
        'rolling5': [100, 200, 300],
        'rolling5_mean': [90, 180, np.nan],
        'rolling5_std': [10, 20, 30]
    })
    
    try:
        result_df = get_z_score(test_df, [5])
        z_scores = result_df['rolling5_z_score'].values
        
        first_two_finite = np.isfinite(z_scores[0]) and np.isfinite(z_scores[1])
        third_is_nan = np.isnan(z_scores[2])
        
        print(f"  ✓ 正常数据z-score: [{z_scores[0]:.2f}, {z_scores[1]:.2f}]")
        print(f"  ✓ 缺失数据z-score: {z_scores[2]} (应为nan)")
        
        passed = first_two_finite and third_is_nan
        message = f"正常数据有限: {first_two_finite}, 缺失数据为NaN: {third_is_nan}"
    except Exception as e:
        passed = False
        message = f"处理异常: {str(e)}"
    
    results.add_result("NaN处理", passed, message)


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("股票分析优化功能综合测试")
    print("="*70)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python版本: {sys.version}")
    print("="*70)
    
    results = TestResults()
    
    test_data = generate_test_data(num_times=10, num_stocks=50)
    
    test_parquet_performance(test_data, results)
    test_data_integrity(test_data, results)
    test_zero_handling(results)
    test_extreme_std_handling(results)
    test_file_size_reduction(test_data, results)
    test_nan_handling(results)
    
    results.print_summary()
    
    return all(r['passed'] for r in results.results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
