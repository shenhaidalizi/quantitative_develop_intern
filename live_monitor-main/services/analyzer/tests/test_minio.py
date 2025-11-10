import pandas as pd
from minio import Minio

#"accessKey":"pcijlDXYHY7dqqFAv9E4","secretKey":"isRi7vDzEUKoZjiRr0bTmgd3WjUC8ZTbpOWfQ5sk"

# 假设 final_data 是你要上传的数据
final_data = pd.DataFrame({
    'col1': [1, 2, 3],
    'col2': ['A', 'B', 'C']
})

# 保存到临时 CSV 文件
csv_file_path = "/tmp/data.csv"
final_data.to_csv(csv_file_path, index=False)

# 配置 MinIO 客户端


# 上传 CSV 文件到 MinIO 存储桶
bucket_name = "live-data"
object_name = "data.csv"

# 检查存储桶是否存在，如果不存在则创建
if not client.bucket_exists(bucket_name):
    client.make_bucket(bucket_name)

# 上传文件到 MinIO
try:
    client.fput_object(bucket_name, object_name, csv_file_path)
    print(f"File '{object_name}' uploaded successfully to bucket '{bucket_name}'.")
except Exception as e:
    print(f"Error uploading file: {e}")
