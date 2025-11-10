import requests
import os
import json
import random
import time
from datetime import datetime


def get_stock_basic_info():
    url = "http://dataapi.trader.com/stock/basic_info"
    
    # 可根据需要添加参数
    params = {
        'format': 'json',  # 选择返回格式，json / csv.gz / parquet
    }
    
    # 指定保存文件的目录
    save_dir = './data'
    
    # 确保目录存在
    os.makedirs(save_dir, exist_ok=True)
    
    # 保存的文件路径
    save_file_path = os.path.join(save_dir, 'stock_basic_info.json')

    try:
        # 发送GET请求
        response = requests.get(url, params=params)
        
        # 检查请求是否成功
        if response.status_code == 200:
            data = response.json()  # 将响应的JSON数据转换为Python字典
            
            # 将数据保存到文件
            with open(save_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)  # 将数据保存为 JSON 格式

            print(f"数据已保存到 {save_file_path}")
        else:
            print(f"请求失败，状态码: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"请求出错: {e}")

def get_stock_live_cn_all():
    url = "http://dataapi.trader.com/live/cn/all"
    
    # 可根据需要添加参数
    params = {
        'format': 'json',  # 选择返回格式，json / csv.gz / parquet
    }
    
    # 指定保存文件的目录
    save_dir = './data'
    
    # 确保目录存在
    os.makedirs(save_dir, exist_ok=True)
    
    # 保存的文件路径
    save_file_path = os.path.join(save_dir, 'stock_live_cn_all.json')

    try:
        # 发送GET请求
        response = requests.get(url, params=params)
        
        # 检查请求是否成功
        if response.status_code == 200:
            data = response.json()  # 将响应的JSON数据转换为Python字典
            
            # 将数据保存到文件
            with open(save_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)  # 将数据保存为 JSON 格式

            print(f"数据已保存到 {save_file_path}")
        else:
            print(f"请求失败，状态码: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"请求出错: {e}")

# 读取基础股票信息文件
def load_stock_basic_info(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 生成伪数据函数，使用固定的股票对象
def generate_fake_stock_data(stock_info):
    fake_data = []
    for stock in stock_info:
        stock_data = {
            "Symbol": stock["ts_code"].split('.')[0],  # 只保留股票代码部分
            "StockName": stock["name"],  # 股票名称
            "Latest": round(random.uniform(10, 100), 2),
            "ChangePercent": round(random.uniform(-5, 5), 2),
            "ChangeAmount": round(random.uniform(-1, 1), 2),
            "TradingVolume": random.randint(10000, 1000000),
            "TradingAmount": random.randint(100000000, 10000000000),
            "Swing": round(random.uniform(0, 10), 2),
            "High": round(random.uniform(10, 100), 2),
            "Low": round(random.uniform(10, 100), 2),
            "Open": round(random.uniform(10, 100), 2),
            "PreClose": round(random.uniform(10, 100), 2),
            "QuantityRatio": round(random.uniform(0, 100), 2),
            "TurnoverRate": round(random.uniform(0, 5), 2),
            "PERatioDynamic": round(random.uniform(1, 20), 2),
            "PBRatio": round(random.uniform(0, 5), 2),
            "IsLimitUp": False
        }
        fake_data.append(stock_data)
    return fake_data

def save_fake_data_to_file(fake_data, batch_index, output_dir="data"):
    os.makedirs(output_dir, exist_ok=True)
    last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    final_data = {
        "message": "中国股票实时数据",
        "count": len(fake_data),
        "last_update": last_update,
        "data": fake_data
    }

    filename = os.path.join(output_dir, f"fake_stock_data_batch_{batch_index + 1}.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
    
    print(f"✅ 保存第 {batch_index + 1} 批数据到 {filename}")
    return filename


def generate_fake_data_stream(
    stock_basic_info_path, 
    interval_seconds=1, 
    total_records=1000, 
    batch_size=100, 
    output_dir="data"
):
    # 加载基础股票信息
    stock_basic_info = load_stock_basic_info(stock_basic_info_path)['data']
    
    # 固定选择股票对象，用于每批次生成相同的股票数据结构
    fixed_stock_info = stock_basic_info[:batch_size]

    # 计算批次数
    num_batches = total_records // batch_size
    generated_files = []
    
    for i in range(num_batches):
        print(f"生成第 {i + 1} 批伪数据 ({batch_size} 条)...")
        
        # 每批次生成伪数据
        batch_data = generate_fake_stock_data(fixed_stock_info)
        
        # 保存每批次数据到不同文件
        filename = save_fake_data_to_file(batch_data, i, output_dir)
        generated_files.append(filename)
        
        # 等待时间间隔（最后一批不等待）
        if i < num_batches - 1:
            print(f"等待 {interval_seconds} 秒...")
            time.sleep(interval_seconds)
    
    print("✅ 所有批次数据生成完毕！")
    return generated_files


    





