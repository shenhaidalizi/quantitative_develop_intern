"""
增量预处理：只处理新增的日期数据
避免每次都重新计算全部30天的历史数据

注意：继承了 preprocess_data.py 的 DATA_ROOT 配置
     OUTPUT_DIR 会自动使用 $DATA_ROOT/statistic_data
"""

import os
import glob
import time
from datetime import datetime, timedelta
from preprocess_data import *

def get_latest_processed_date(output_dir: str) -> str:
    """获取最近一次处理的日期"""
    pattern = os.path.join(output_dir, "time_data_*.parquet")
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    latest_file = max(files, key=os.path.getmtime)
    filename = os.path.basename(latest_file)
    date_str = filename.replace('time_data_', '').replace('.parquet', '')
    
    return date_str


def incremental_main():
    """增量处理主函数"""
    print("=== 增量数据处理模式 ===")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"time_data_{TARGET_DATE}.parquet")
    
    # 检查今天的文件是否已存在
    if os.path.exists(output_path):
        print(f"✅ 今日数据已存在: {os.path.basename(output_path)}")
        
        # 检查文件是否过期（超过1小时）
        file_age = time.time() - os.path.getmtime(output_path)
        if file_age < 3600:  # 1小时内
            print(f"⏱️ 文件创建于 {file_age/60:.1f} 分钟前，跳过处理")
            return
        else:
            print(f"⚠️ 文件已超过1小时，将重新生成")
    
    try:
        # 步骤1: 获取和预处理数据
        print("📊 获取原始数据...")
        raw_data = get_stock_data()
        
        # 只处理最近DATE_INTERVAL天的数据
        print(f"🔄 预处理数据（最近{DATE_INTERVAL}天）...")
        df = preprocess_stock_minute_data(raw_data)
        
        # 过滤最近N天的数据
        cutoff_date = pd.to_datetime(TARGET_DATE) - timedelta(days=DATE_INTERVAL)
        df = df[df['trade_date'] >= cutoff_date.date()]
        print(f"📅 过滤后数据量: {len(df)} 条记录")
        
        print("⚡ 并行计算滚动数据...")
        rolling_data = calculate_rolling_data_parallel_optimized(df)
        
        print("📈 并行处理统计数据...")
        stats_data = process_statistics_data_optimized(rolling_data, TARGET_DATE, DATE_INTERVAL)
        
        print("🔄 并行转换时间序列格式...")
        final_data = convert_to_time_format_parallel(stats_data)
        
        print(f"💾 保存最终结果...")
        final_path = save_data_as_parquet(final_data, output_path)
        
        print(f"✅ 数据处理完成")
        print(f"包含 {len(final_data)} 个时间点的数据")
        
        print("🧹 清理历史文件...")
        clean_old_output_files(OUTPUT_DIR, final_path, KEEP_FILE_COUNT)
        
        print("=== 处理完成 ===")
        
    except Exception as e:
        print(f"❌ 数据处理过程中发生错误: {e}")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                print(f"🗑️ 已删除不完整的输出文件")
            except:
                pass
        raise


if __name__ == "__main__":
    incremental_main()
