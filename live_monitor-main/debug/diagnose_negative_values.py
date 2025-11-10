# debug/diagnose_negative_values.py
import json
import pandas as pd
import numpy as np

print("=" * 70)
print("🔍 诊断为什么全是负值")
print("=" * 70)

# 读取修复后的文件
with open('/home/ubuntu/TradeNew/live/live_monitor/debug/fixed_json/test_145900_idx238.json', 'r') as f:
    data = json.load(f)

# 读取预处理数据
df = pd.read_parquet("/home/ubuntu/TradeNew/live/live_monitor/shared/statistic_data/time_data_2025-10-10.parquet")
df['time'] = df['time'].astype(str)

time_str = "14:59:00"
rolling_full_data = df[(df['time'] == time_str) & (df['window_type'] == 'rolling_full')]
rolling_full_data = rolling_full_data.copy()
rolling_full_data['stock_code'] = rolling_full_data['stock_code'].str.replace(r'\.(SZ|SH|BJ)$', '', regex=True)

# 创建字典
preprocess_dict = {}
for _, row in rolling_full_data.iterrows():
    preprocess_dict[row['stock_code']] = {
        'mean': row['mean'],
        'std': row['std']
    }

# 分析几只有交易量的股票
print(f"\n分析时间: {time_str}")
print(f"预处理数据股票数: {len(preprocess_dict)}")

active_stocks = [item for item in data if item['Vol'] > 1000][:10]

print(f"\n找到 {len(active_stocks)} 只活跃股票，分析前10只:")
print("=" * 70)

for i, item in enumerate(active_stocks, 1):
    code = item['code']
    vol = item['Vol']
    rolling_full = item['rolling_full']
    
    if code in preprocess_dict:
        mean = preprocess_dict[code]['mean']
        std = preprocess_dict[code]['std']
        
        print(f"\n{i}. {code} - {item['Name']}")
        print(f"   当前累积交易量 (Vol): {vol:,.2f}")
        print(f"   预处理 mean: {mean:,.2f}")
        print(f"   预处理 std:  {std:,.2f}")
        print(f"   偏差 (Vol - mean): {vol - mean:,.2f}")
        
        # 手动计算
        if std > 1e-6:
            calc_z = (vol - mean) / std
        else:
            calc_z = 0 if abs(vol - mean) < 1e-6 else np.sign(vol - mean) * 3
        
        print(f"   手动计算 z: {calc_z:.2f}")
        print(f"   JSON中的 rolling_full: {rolling_full:.2f}")
        
        # 检查是否应该为正值
        if vol > mean:
            print(f"   ⚠️ Vol > mean，应该是正值！")
        else:
            print(f"   ✓ Vol < mean，负值正常")
    else:
        print(f"\n{i}. {code} - 预处理数据中不存在")

# 统计分析
print("\n" + "=" * 70)
print("📊 全局统计:")
print("=" * 70)

vol_values = [item['Vol'] for item in data if item['Vol'] > 0]
rolling_full_values = [item['rolling_full'] for item in data if item['rolling_full'] != 0]

print(f"有交易量的股票数: {len(vol_values)}")
print(f"Vol 范围: [{min(vol_values):,.2f}, {max(vol_values):,.2f}]")
print(f"Vol 平均值: {np.mean(vol_values):,.2f}")
print(f"Vol 中位数: {np.median(vol_values):,.2f}")

# 对比预处理的mean值分布
all_means = [preprocess_dict[code]['mean'] for code in preprocess_dict.keys() if preprocess_dict[code]['mean'] > 0]
print(f"\n预处理 mean 范围: [{min(all_means):,.2f}, {max(all_means):,.2f}]")
print(f"预处理 mean 平均值: {np.mean(all_means):,.2f}")
print(f"预处理 mean 中位数: {np.median(all_means):,.2f}")

# 关键检查：Vol 和 mean 的数量级对比
print("\n" + "=" * 70)
print("🔍 关键发现:")
print("=" * 70)

vol_avg = np.mean(vol_values)
mean_avg = np.mean(all_means)
ratio = vol_avg / mean_avg

print(f"实时 Vol 平均值: {vol_avg:,.2f}")
print(f"预处理 mean 平均值: {mean_avg:,.2f}")
print(f"比例: {ratio:.2f}")

if ratio < 0.5:
    print(f"\n❌ 问题：实时 Vol 远小于预处理 mean！")
    print(f"   可能原因：")
    print(f"   1. 时间不对（14:59是收盘前，应该累积量很大）")
    print(f"   2. Vol 还需要再除以100？")
    print(f"   3. 预处理数据的单位不对？")
elif ratio > 2:
    print(f"\n❌ 问题：实时 Vol 远大于预处理 mean！")
    print(f"   可能原因：Vol 不应该除以100")
else:
    print(f"\n✅ 比例正常（0.5-2之间）")
    print(f"   如果仍然全是负值，说明今天交易量普遍低于历史均值")

print("\n" + "=" * 70)