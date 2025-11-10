# debug/check_rolling_full.py
import pandas as pd
import numpy as np
import json
import glob

print("=" * 70)
print("📊 诊断 rolling_full (allz) 计算")
print("=" * 70)

# 1. 读取最新的JSON结果
json_files = glob.glob("/home/ubuntu/TradeNew/live/live_monitor/shared/data/test_result/test_*.json")
latest_json = max(json_files, key=lambda x: x)

with open(latest_json, 'r') as f:
    result_data = json.load(f)

# 提取时间信息
import re
match = re.search(r'test_(\d{2})(\d{2})(\d{2})_idx', latest_json)
if match:
    time_str = f"{match.group(1)}:{match.group(2)}:{match.group(3)}"
    print(f"\n⏰ 分析时间: {time_str}")

# 2. 读取预处理数据
df = pd.read_parquet("/home/ubuntu/TradeNew/live/live_monitor/shared/statistic_data/time_data_2025-10-10.parquet")
df['time'] = df['time'].astype(str)

# 筛选 rolling_full 数据
rolling_full_data = df[(df['time'] == time_str) & (df['window_type'] == 'rolling_full')]

if len(rolling_full_data) == 0:
    print(f"\n⚠️ 警告：预处理数据中没有时间 {time_str} 的数据")
    print("可用的时间点示例：", df['time'].unique()[:10])
else:
    # 标准化股票代码
    rolling_full_data = rolling_full_data.copy()
    rolling_full_data['stock_code'] = rolling_full_data['stock_code'].str.replace(r'\.(SZ|SH|BJ)$', '', regex=True)
    
    # 创建快速查找字典
    preprocess_dict = {}
    for _, row in rolling_full_data.iterrows():
        preprocess_dict[row['stock_code']] = {
            'mean': row['mean'],
            'std': row['std']
        }
    
    # 3. 对比几只股票
    print("\n" + "=" * 70)
    print("📈 样本股票对比（前5只）:")
    print("=" * 70)
    
    for i, item in enumerate(result_data[:5]):
        code = item['code']
        vol = item['Vol']
        rolling_full_z = item['rolling_full']
        
        print(f"\n{i+1}. {code} - {item['Name']}")
        print(f"   当前累积交易量 (Vol): {vol:,.0f}")
        
        if code in preprocess_dict:
            mean = preprocess_dict[code]['mean']
            std = preprocess_dict[code]['std']
            
            # 手动计算 z-score
            if std > 1e-6:
                calculated_z = (vol - mean) / std
            else:
                # 标准差为0的情况
                if abs(vol - mean) < 1e-6:
                    calculated_z = 0
                else:
                    calculated_z = np.sign(vol - mean) * 3
            
            print(f"   预处理 mean: {mean:,.2f}")
            print(f"   预处理 std:  {std:,.2f}")
            print(f"   偏差 (Vol - mean): {vol - mean:,.2f}")
            print(f"   手动计算 z-score: {calculated_z:.2f}")
            print(f"   JSON中的 rolling_full: {rolling_full_z:.2f}")
            
            # 检查是否一致
            if abs(calculated_z - rolling_full_z) > 0.1:
                print(f"   ⚠️ 警告：计算不一致！差异 = {abs(calculated_z - rolling_full_z):.2f}")
            else:
                print(f"   ✅ 计算一致")
        else:
            print(f"   ❌ 预处理数据中没有此股票")
    
    # 4. 统计分析
    print("\n" + "=" * 70)
    print("📊 rolling_full 统计分析:")
    print("=" * 70)
    
    rolling_full_values = [item['rolling_full'] for item in result_data if item['rolling_full'] != 0]
    
    print(f"总股票数: {len(result_data)}")
    print(f"有效 rolling_full 值: {len(rolling_full_values)}")
    print(f"rolling_full 范围: [{min(rolling_full_values):.2f}, {max(rolling_full_values):.2f}]")
    print(f"rolling_full 均值: {np.mean(rolling_full_values):.2f}")
    print(f"rolling_full 中位数: {np.median(rolling_full_values):.2f}")
    
    # 分布统计
    positive = sum(1 for v in rolling_full_values if v > 0)
    negative = sum(1 for v in rolling_full_values if v < 0)
    print(f"\n正值: {positive} ({positive/len(rolling_full_values)*100:.1f}%)")
    print(f"负值: {negative} ({negative/len(rolling_full_values)*100:.1f}%)")
    
    # 异常值检测
    extreme_positive = sum(1 for v in rolling_full_values if v > 10)
    extreme_negative = sum(1 for v in rolling_full_values if v < -10)
    print(f"极端正值 (>10): {extreme_positive}")
    print(f"极端负值 (<-10): {extreme_negative}")

print("\n" + "=" * 70)