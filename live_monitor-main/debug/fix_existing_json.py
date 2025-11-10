# debug/fix_existing_json.py
import json
import glob
import pandas as pd
import numpy as np
import re
import os
import shutil

print("=" * 70)
print("🔧 修复现有 JSON 文件的 rolling_full 和 Vol")
print("=" * 70)

# 创建输出目录
output_dir = "/home/ubuntu/TradeNew/live/live_monitor/debug/fixed_json"
os.makedirs(output_dir, exist_ok=True)
print(f"\n📁 输出目录: {output_dir}")

# 读取预处理数据
df = pd.read_parquet("/home/ubuntu/TradeNew/live/live_monitor/shared/statistic_data/time_data_2025-10-10.parquet")
df['time'] = df['time'].astype(str)

# 获取所有 JSON 文件
json_files = glob.glob("/home/ubuntu/TradeNew/live/live_monitor/shared/data/test_result/test_*.json")

print(f"\n📁 找到 {len(json_files)} 个 JSON 文件")

fixed_files = []

for json_path in sorted(json_files)[-5:]:  # 只处理最新的5个文件
    # 提取时间
    match = re.search(r'test_(\d{2})(\d{2})(\d{2})_idx', json_path)
    if not match:
        continue
    
    time_str = f"{match.group(1)}:{match.group(2)}:{match.group(3)}"
    
    print(f"\n处理: {os.path.basename(json_path)} (时间: {time_str})")
    
    try:
        # 读取 JSON
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # 获取该时间点的预处理数据
        rolling_full_data = df[(df['time'] == time_str) & (df['window_type'] == 'rolling_full')]
        
        if len(rolling_full_data) == 0:
            print(f"  ⚠️ 跳过：预处理数据中没有时间 {time_str}")
            continue
        
        # 标准化股票代码并创建查找字典
        rolling_full_data = rolling_full_data.copy()
        rolling_full_data['stock_code'] = rolling_full_data['stock_code'].str.replace(r'\.(SZ|SH|BJ)$', '', regex=True)
        
        preprocess_dict = {}
        for _, row in rolling_full_data.iterrows():
            preprocess_dict[row['stock_code']] = {
                'mean': row['mean'],
                'std': row['std']
            }
        
        # 修复每只股票的数据
        fixed_count = 0
        positive_count = 0
        negative_count = 0
        
        for item in data:
            code = item['code']
            
            # 修复 Vol（除以100）
            old_vol = item['Vol']
            item['Vol'] = round(old_vol / 100, 2)
            
            # 重新计算 rolling_full
            if code in preprocess_dict:
                mean = preprocess_dict[code]['mean']
                std = preprocess_dict[code]['std']
                vol = item['Vol']  # 使用修复后的 Vol
                
                # 计算 z-score
                if std > 1e-6:
                    z_score = (vol - mean) / std
                else:
                    if abs(vol - mean) < 1e-6:
                        z_score = 0
                    else:
                        z_score = np.sign(vol - mean) * 3
                
                item['rolling_full'] = round(z_score, 2)
                fixed_count += 1
                
                # 统计正负值
                if z_score > 0:
                    positive_count += 1
                elif z_score < 0:
                    negative_count += 1
        
        # 保存修复后的文件到新目录
        output_path = os.path.join(output_dir, os.path.basename(json_path))
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        
        fixed_files.append(output_path)
        
        print(f"  ✅ 修复完成: {fixed_count} 只股票")
        print(f"  📊 正值: {positive_count} ({positive_count/fixed_count*100:.1f}%)")
        print(f"  📊 负值: {negative_count} ({negative_count/fixed_count*100:.1f}%)")
        print(f"  💾 保存到: {os.path.basename(output_path)}")
        
    except Exception as e:
        print(f"  ❌ 错误: {e}")

print("\n" + "=" * 70)
print(f"✅ 处理完成，修复了 {len(fixed_files)} 个文件")
print(f"📁 修复后的文件位于: {output_dir}")
print("\n💡 验证修复效果:")
print(f"   python debug/check_vol_unit.py")
print("\n💡 如果确认无误，可以复制回原目录:")
print(f"   sudo cp {output_dir}/*.json /home/ubuntu/TradeNew/live/live_monitor/shared/data/test_result/")
print("=" * 70)