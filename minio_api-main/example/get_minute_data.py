from minio_api.minute_client import get_minute_data_from_minio

# 读取 2024-01-03 09:30 到 2024-01-03 15:00 的某一只股票分钟数据
df = get_minute_data_from_minio(
    symbol=None, # 读取所有股票数据
    start="2025-10-14 09:30:00",
    end="2025-10-14 15:00:00",
    by="datetime",
    output_type="df",
    base_prefix="minutely",  # 或用环境变量 MINIO_MINUTE_PREFIX
)
print(df.head())
print(df.tail())
print(len(df))