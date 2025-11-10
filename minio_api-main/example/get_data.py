from minio_api import MinIOStockDataClient

# 创建客户端
client = MinIOStockDataClient()

# 获取不同类型的数据 - 直接返回DataFrame
# 可获取的参考数据类型见README.md
cnstock_data = client.get_data("CNSTOCK", "20240101", "20241231")
cnindex_data = client.get_data("CNINDEX", "20240101", "20241231") 
moneyflow_data = client.get_data("CNSTOCK_MONEYFLOW", "20240101", "20241231")
print(cnstock_data.head())
print(cnindex_data.head())
print(moneyflow_data.head())


# 便捷函数也直接返回DataFrame
from minio_api import get_cnstock_data, get_cnstock_basic_data, get_cnstock_moneyflow_data
df1 = get_cnstock_data("20240101", "20241231")
df2 = get_cnstock_basic_data("20240101", "20241231")
df3 = get_cnstock_moneyflow_data("20240101", "20241231")
print(df1.head())
print(df2.head())
print(df3.head())
