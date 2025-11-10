# 获取Tick数据
from minio_api import get_tick_data_from_minio
# tick_data = get_tick_data_from_minio("AG_1.SHF", "20240101", "20240131")
tick_data = get_tick_data_from_minio("AP_1.ZCE", "20240101", "20240105")
print(tick_data.head())
print(tick_data.tail())
print(len(tick_data))