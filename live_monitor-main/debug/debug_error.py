# 诊断脚本
import pandas as pd
import os

# 读取最新的 parquet 文件
parquet_path = "/home/ubuntu/TradeNew/live/live_monitor/shared/statistic_data/time_data_2025-10-10.parquet"

print("=" * 60)
print("📊 检查 Parquet 数据文件")
print("=" * 60)

if os.path.exists(parquet_path):
    df = pd.read_parquet(parquet_path)
    
    # 转换时间列为字符串
    df['time'] = df['time'].astype(str)
    
    print(f"\n✅ 文件存在，共 {len(df)} 行数据")
    print(f"\n📋 数据列: {df.columns.tolist()}")
    print(f"\n📋 数据类型:\n{df.dtypes}")
    
    # 检查唯一的时间点
    unique_times = sorted(df['time'].unique())
    print(f"\n⏰ 唯一的时间点数量: {len(unique_times)}")
    print(f"⏰ 前5个时间点: {unique_times[:5]}")
    print(f"⏰ 后5个时间点: {unique_times[-5:]}")
    
    # 检查唯一的 window_type
    unique_windows = df['window_type'].unique()
    print(f"\n🪟 唯一的 window_type: {sorted(unique_windows)}")
    
    # 检查唯一的股票代码数量
    unique_stocks = df['stock_code'].unique()
    print(f"\n📈 唯一的股票数量: {len(unique_stocks)}")
    print(f"📈 前5个股票: {unique_stocks[:5]}")
    
    # 检查特定时间的数据
    test_time = "14:02:00"  # 使用CSV文件对应的时间
    print(f"\n🔍 检查时间 {test_time} 的数据:")
    time_data = df[df['time'] == test_time]
    
    if len(time_data) == 0:
        print(f"❌ 没有找到时间 {test_time} 的数据!")
        print(f"提示：请检查CSV文件时间是否与parquet文件时间匹配")
    else:
        print(f"✅ 找到 {len(time_data)} 行数据")
        print(f"\n前10行数据:")
        print(time_data.head(10))
        
        # 测试 pivot 操作
        print(f"\n🔄 测试 pivot 操作:")
        try:
            result = time_data.pivot(
                index='stock_code', 
                columns='window_type', 
                values=['mean', 'std']
            )
            result.columns = [f'{col[1]}_{col[0]}' for col in result.columns]
            print(f"✅ Pivot 成功，结果列: {result.columns.tolist()}")
            print(f"✅ Pivot 结果形状: {result.shape}")
            print(f"\n前5行pivot结果:")
            print(result.head())
        except Exception as e:
            print(f"❌ Pivot 失败: {e}")
else:
    print(f"❌ 文件不存在: {parquet_path}")

# 检查最新的CSV文件
print("\n" + "=" * 60)
print("📄 检查最新的 CSV 文件")
print("=" * 60)

csv_path = "/home/ubuntu/TradeNew/live/live_monitor/shared/data/test_result/test_140200_idx181.csv"
if os.path.exists(csv_path):
    csv_df = pd.read_csv(csv_path, index_col=0)
    print(f"✅ CSV文件存在，共 {len(csv_df)} 行数据")
    print(f"\n📋 CSV列: {csv_df.columns.tolist()}")
    print(f"\n🔍 检查前5行:")
    print(csv_df.head())
    
    # 检查是否有非零值
    z_score_cols = ['rolling1_z_score', 'rolling5_z_score', 'rolling10_z_score', 'rolling30_z_score']
    for col in z_score_cols:
        if col in csv_df.columns:
            non_null = csv_df[col].notna().sum()
            non_zero = (csv_df[col] != 0).sum()
            print(f"  {col}: 非空={non_null}, 非零={non_zero}")
else:
    print(f"❌ 文件不存在: {csv_path}")