import pandas as pd
import dotenv
import os
import datetime
from minio_api.minute_client import get_minute_data_from_minio


dotenv.load_dotenv()
DATE_INTERVAL = int(os.getenv("DATE_INTERVAL", 30))  # 日期间隔

today_date = datetime.date.today()
start_date = today_date - datetime.timedelta(days=DATE_INTERVAL)
print(f"start_date: {start_date}, today_date: {today_date}")

def get_server_data():
    # 明确将日期对象格式化为 'YYYYmmdd' 字符串
    start_date_str = start_date.strftime('%Y%m%d')
    today_date_str = today_date.strftime('%Y%m%d')

    # 对齐接口参数进行调用
    minute_data = get_minute_data_from_minio(
        symbol=None,          # 传 None 以匹配接口定义，表示获取所有股票
        start=start_date_str,
        end=today_date_str,
        by="date",            # 按日期范围查询
        output_type="df",      # 显式指定返回 DataFrame
        base_prefix="minutely",
    )
    return minute_data

# --- 在这里添加测试代码 ---
if __name__ == "__main__":
    print("🚀 开始独立测试 get_server_data 函数...")
    
    # 记录开始时间
    start_time = datetime.datetime.now()
    
    # 调用函数获取数据
    df = get_server_data()
    
    # 记录结束时间
    end_time = datetime.datetime.now()
    
    # 打印测试结果
    print("\n✅ 数据获取成功！")
    
    # 检查返回的是否为 DataFrame
    if df is not None:
        print(f"   - 返回类型: {type(df)}")
        print(f"   - 数据行数: {len(df)}")
        print(f"   - 数据列名: {df.columns.tolist()}")
        # 打印前 5 行数据以供预览
        print("   - 数据预览 (前 5 行):")
        print(df.head())
    else:
        print("   - 注意：返回的数据为 None")
    
    # 打印执行耗时
    duration = (end_time - start_time).total_seconds()
    print(f"\n⏱️ 测试耗时: {duration:.2f} 秒")
    print("🏁 测试结束。")
