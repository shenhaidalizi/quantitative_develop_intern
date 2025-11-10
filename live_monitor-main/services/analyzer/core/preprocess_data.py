import pandas as pd
import os
import glob
from collections import defaultdict
from tqdm import tqdm
import numpy as np
import warnings
from datetime import datetime
import dotenv
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import pickle
from functools import partial
import pyarrow.parquet as pq
import gzip
import pandas as pd
from minio import Minio
import os
from datetime import datetime
import pandas as pd
from minio import Minio
import os
from minio import Minio
from dotenv import load_dotenv
from data_fetcher import get_server_data

# 加载 .env 文件
load_dotenv()  # 默认会在当前工作目录查找 .env

# 读取环境变量
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = "live-data"

# =============== 初始化设置 ===============
# 忽略所有警告
warnings.filterwarnings("ignore")
# 加载环境变量
dotenv.load_dotenv()
ON_SERVER = os.getenv("ON_SERVER", "false") == "true"

# =============== 基础配置 ===============
# 设置路径（支持环境变量配置，与 timely_data.py 保持一致）
DATA_ROOT = os.getenv('DATA_ROOT', os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(DATA_ROOT, "app/data")
OUTPUT_DIR = os.path.join(DATA_ROOT, "statistic_data")  # 现在会指向 /app/statistic_data ✅

# 时间设置
TODAY_DATE = datetime.now().strftime('%Y-%m-%d')
if ON_SERVER:
    TARGET_DATE = TODAY_DATE
else:
    TARGET_DATE = "2025-07-01"  # 设置固定日期用于测试

# 数据处理参数
WINDOW_LENGTH_LIST = [1, 5, 10, 30]  # 滚动窗口长度
INCLUDE_FULL_ROLLING = True  # 是否包含全量滚动计算
DATE_INTERVAL = int(os.getenv("DATE_INTERVAL", 15))  # 日期间隔改为30天
BATCH_SIZE = 100  # 每批处理的股票数量
NUM_PROCESSES = int(os.getenv("NUM_PROCESSES", max(1, mp.cpu_count() - 1)))  # 进程数（留一个核心给系统）
KEEP_FILE_COUNT = 2  # 保留的历史文件数量


"""
优化的数据预处理脚本
直接处理原始数据到最终的时间序列数据，不保存中间文件
最终输出：statistic_data/time_data_{target_date}.json
"""

def get_stock_data() -> pd.DataFrame:
    """
    获取股票数据的统一接口
    根据环境自动选择数据源
    """
    try:
        
        print("使用服务器数据源...")
        df = get_server_data()
        df['vol'] = df['vol']
        print(f"成功获取服务器数据，共 {len(df)} 条记录")
        return df
    except ImportError:
        print("使用本地测试数据源...")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(current_dir, "data", "stock_minute_data_test.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"测试数据文件不存在: {csv_path}")
        df = pd.read_csv(csv_path)
        df['vol'] = df['vol']
        print(f"成功读取测试数据，共 {len(df)} 条记录")
        return df
    except Exception as e:
        print(f"数据获取失败: {str(e)}")
        raise

def preprocess_stock_minute_data(df: pd.DataFrame) -> pd.DataFrame:
    """数据预处理 - 现在接受DataFrame而不是文件路径"""
    print("正在预处理股票分钟数据...")
    
    # 优化：使用categorical类型减少内存使用
    df['ts_code'] = df['ts_code'].astype('category')
    df['trade_time'] = pd.to_datetime(df['trade_time'])
    df['trade_date'] = df['trade_time'].dt.date
    df['time_only'] = df['trade_time'].dt.time
    df = df.sort_values(['trade_date', 'ts_code', 'trade_time'])
    
    return df

def process_single_group(group_data):
    """处理单个股票组的数据"""
    result = {}
    
    # 计算所有窗口的滚动求和（改为sum）
    for window_length in WINDOW_LENGTH_LIST:
        rolling_vol = group_data['vol'].rolling(
            window=window_length,
            min_periods=1
        ).sum().values  # 改为sum()
        
        rolling_dict = {
            time.strftime("%H:%M:%S"): val
            for time, val in zip(group_data['time_only'], rolling_vol)
        }
        
        result[f'rolling{window_length}'] = rolling_dict
    
    # 修改rolling_full的计算方式 - 改为累积求和
    if INCLUDE_FULL_ROLLING:
        # 计算从开盘到每个时间点的累积求和
        cumsum = np.cumsum(group_data['vol'].values)
        
        # 计算从开盘到每个时间点的标准差（基于原始值）
        indices = np.arange(1, len(group_data) + 1)
        vol_values = group_data['vol'].values
        
        # 计算累积均值用于标准差计算
        cumulative_means = cumsum / indices
        
        # 计算标准差
        squared_diff_cumsum = np.cumsum(np.square(vol_values - cumulative_means))
        stds = np.sqrt(squared_diff_cumsum / indices)
        stds = np.where(stds == 0, 1e-8, stds)  # 避免除以0
        
        # 创建累积求和和标准差的字典
        sum_dict = {
            time.strftime("%H:%M:%S"): float(cumsum_val)
            for time, cumsum_val in zip(group_data['time_only'], cumsum)
        }
        
        std_dict = {
            time.strftime("%H:%M:%S"): float(std)
            for time, std in zip(group_data['time_only'], stds)
        }
        
        # 保存累积求和和标准差
        result['rolling_full'] = {
            'mean': sum_dict,  # 这里存储的实际是累积求和
            'std': std_dict
        }
    
    return result

def process_stock_chunk(stock_chunk, window_lengths, include_full_rolling):
    """
    处理一批股票的数据 - 优化后的批处理函数
    Args:
        stock_chunk: [(date, stock_code, group_data), ...]
        window_lengths: 窗口长度列表
        include_full_rolling: 是否包含全量滚动
    """
    results = {}
    
    for trade_date, ts_code, group_data in stock_chunk:
        try:
            # 使用向量化操作计算滚动数据
            result = {}
            
            # 批量计算所有窗口的滚动求和（改为sum）
            for window_length in window_lengths:
                rolling_vol = group_data['vol'].rolling(
                    window=window_length,
                    min_periods=1
                ).sum()  # 改为sum()
                
                result[f'rolling{window_length}'] = {
                    time.strftime("%H:%M:%S"): val
                    for time, val in zip(group_data['time_only'], rolling_vol)
                }
            
            # 优化的rolling_full计算 - 改为累积求和
            if include_full_rolling:
                vol_values = group_data['vol'].values
                indices = np.arange(1, len(vol_values) + 1)
                
                # 计算累积求和
                cumsum = np.cumsum(vol_values)
                
                # 计算累积均值用于标准差计算
                cumulative_means = cumsum / indices
                
                # 更高效的标准差计算
                cumsum_sq = np.cumsum(vol_values ** 2)
                stds = np.sqrt((cumsum_sq / indices) - (cumulative_means ** 2))
                stds = np.where(stds == 0, 1e-8, stds)
                
                result['rolling_full'] = {
                    'mean': {  # 这里存储的实际是累积求和
                        time.strftime("%H:%M:%S"): float(cumsum_val)
                        for time, cumsum_val in zip(group_data['time_only'], cumsum)
                    },
                    'std': {
                        time.strftime("%H:%M:%S"): float(std)
                        for time, std in zip(group_data['time_only'], stds)
                    }
                }
            
            # 存储结果
            if trade_date not in results:
                results[trade_date] = {}
            results[trade_date][ts_code] = result
            
        except Exception as e:
            print(f"处理股票 {ts_code} 时发生错误: {str(e)}")
            continue
    
    return results

def calculate_rolling_data_parallel_optimized(df: pd.DataFrame) -> dict:
    """优化后的并行滚动数据计算"""
    print("正在计算滚动数据（优化版本）...")
    
    # 预处理：按股票分组，减少分组操作
    print("正在分组数据...")
    groups = []
    for (trade_date, ts_code), group_data in df.groupby(['trade_date', 'ts_code']):
        if not group_data.empty:
            # 预排序并重置索引，减少子进程中的操作
            sorted_data = group_data.sort_values('trade_time').reset_index(drop=True)
            groups.append((str(trade_date), ts_code, sorted_data))
    
    # 计算最优的批大小
    optimal_chunk_size = max(1, len(groups) // (NUM_PROCESSES * 4))  # 每个进程处理4批
    print(f"总共 {len(groups)} 个股票组，每批 {optimal_chunk_size} 个")
    
    # 将任务分成更大的块
    chunks = []
    for i in range(0, len(groups), optimal_chunk_size):
        chunk = groups[i:i + optimal_chunk_size]
        chunks.append(chunk)
    
    print(f"分成 {len(chunks)} 个批次进行并行处理")
    
    # 使用部分函数来传递配置参数
    process_func = partial(
        process_stock_chunk,
        window_lengths=WINDOW_LENGTH_LIST,
        include_full_rolling=INCLUDE_FULL_ROLLING
    )
    
    # 并行处理
    final_data = {}
    with ProcessPoolExecutor(max_workers=NUM_PROCESSES) as executor:
        # 提交所有批次
        future_to_chunk = {
            executor.submit(process_func, chunk): chunk 
            for chunk in chunks
        }
        
        # 收集结果
        for future in tqdm(as_completed(future_to_chunk), 
                          total=len(future_to_chunk), 
                          desc="处理股票批次"):
            try:
                chunk_result = future.result()
                
                # 合并结果
                for date, stocks_data in chunk_result.items():
                    if date not in final_data:
                        final_data[date] = {}
                    final_data[date].update(stocks_data)
                    
            except Exception as e:
                print(f"处理批次时发生错误: {str(e)}")
                continue
    
    return final_data

def get_trading_stocks_for_date(data_dict: dict, target_date_str: str):
    """获取目标日期的交易股票列表"""
    try:
        target_date = pd.to_datetime(target_date_str)
    except ValueError:
        print(f"Error: Invalid date format: {target_date_str}")
        return [], None
    
    # 获取所有可用日期并排序
    available_dates = sorted([pd.to_datetime(date) for date in data_dict.keys()])
    valid_dates = [date for date in available_dates if date <= target_date]
    
    if not valid_dates:
        print(f"Warning: No trading data found on or before {target_date_str}")
        return [], None
    
    # 使用最近的交易日
    actual_date = max(valid_dates)
    actual_date_str = actual_date.strftime('%Y-%m-%d')
    
    if actual_date_str in data_dict:
        trading_stocks = list(data_dict[actual_date_str].keys())
        return trading_stocks, actual_date_str
    
    return [], None

def get_previous_n_trading_dates(data_dict: dict, target_date_str: str, stock_code: str, n: int = 3) -> list:
    """获取指定股票的前n个交易日"""
    try:
        target_date = pd.to_datetime(target_date_str)
    except ValueError:
        return []
    
    # 收集该股票有数据的所有日期
    valid_dates = []
    for date_str, stocks_data in data_dict.items():
        date_obj = pd.to_datetime(date_str)
        if date_obj <= target_date and stock_code in stocks_data:
            valid_dates.append(date_str)
    
    # 排序并取前n个
    valid_dates.sort(key=pd.to_datetime, reverse=True)
    return valid_dates[:n]

def process_single_stock_stats(stock_code, dates_list, stock_data_subset, window_lengths):
    """处理单个股票的统计数据"""
    stock_stats = {}
    
    # 处理常规滚动窗口
    for window_length in window_lengths:
        window_key = f'rolling{window_length}'
        daily_data_list = []
        
        for date_str in dates_list:
            if window_key in stock_data_subset.get(date_str, {}):
                daily_data_list.append(stock_data_subset[date_str][window_key])
        
        if daily_data_list:
            time_values = defaultdict(list)
            for daily_data in daily_data_list:
                for time, value in daily_data.items():
                    time_values[time].append(value)
            
            mean_dict = {
                time: round(float(np.mean(values)), 2)
                for time, values in time_values.items()
            }
            std_dict = {
                time: round(float(np.std(values)), 2)
                for time, values in time_values.items()
            }
            
            stock_stats[window_key] = {
                "mean": mean_dict,
                "std": std_dict
            }
        else:
            stock_stats[window_key] = {
                "mean": {},
                "std": {}
            }
    
    # 处理rolling_full
    if INCLUDE_FULL_ROLLING:
        daily_mean_list = []
        daily_values_dict = defaultdict(list)  # 用于存储每个时间点的原始值
        
        for date_str in dates_list:
            if 'rolling_full' in stock_data_subset.get(date_str, {}):
                data = stock_data_subset[date_str]['rolling_full']
                daily_mean_list.append(data['mean'])
                
                # 收集每个时间点的原始值
                for time, mean_val in data['mean'].items():
                    daily_values_dict[time].append(mean_val)
        
        if daily_mean_list:
            # 处理均值
            mean_time_values = defaultdict(list)
            for daily_mean in daily_mean_list:
                for time, value in daily_mean.items():
                    mean_time_values[time].append(value)
            
            # 计算最终的均值和标准差
            final_mean_dict = {
                time: round(float(np.mean(values)), 2)
                for time, values in mean_time_values.items()
            }
            
            # 直接对原始值计算标准差
            final_std_dict = {
                time: round(float(np.std(values)), 2)
                for time, values in daily_values_dict.items()
            }
            
            stock_stats['rolling_full'] = {
                "mean": final_mean_dict,
                "std": final_std_dict
            }
        else:
            stock_stats['rolling_full'] = {
                "mean": {},
                "std": {}
            }
    
    return stock_stats

def process_statistics_batch(batch_data):
    """处理统计数据批次"""
    batch_results = {}
    
    for stock_code, (dates_list, stock_data_subset) in batch_data.items():
        try:
            stock_stats = {}
            
            # 处理常规滚动窗口 - 向量化操作
            for window_length in WINDOW_LENGTH_LIST:
                window_key = f'rolling{window_length}'
                
                # 收集所有日期的数据
                all_time_values = defaultdict(list)
                for date_str in dates_list:
                    if window_key in stock_data_subset.get(date_str, {}):
                        daily_data = stock_data_subset[date_str][window_key]
                        for time, value in daily_data.items():
                            all_time_values[time].append(value)
                
                if all_time_values:
                    # 向量化计算均值和标准差
                    mean_dict = {}
                    std_dict = {}
                    
                    for time, values in all_time_values.items():
                        values_array = np.array(values)
                        mean_dict[time] = round(float(np.mean(values_array)), 2)
                        std_dict[time] = round(float(np.std(values_array)), 2)
                    
                    stock_stats[window_key] = {
                        "mean": mean_dict,
                        "std": std_dict
                    }
                else:
                    stock_stats[window_key] = {"mean": {}, "std": {}}
            
            # 处理rolling_full - 同样向量化
            if INCLUDE_FULL_ROLLING:
                all_mean_values = defaultdict(list)
                
                for date_str in dates_list:
                    if 'rolling_full' in stock_data_subset.get(date_str, {}):
                        data = stock_data_subset[date_str]['rolling_full']
                        for time, mean_val in data['mean'].items():
                            all_mean_values[time].append(mean_val)
                
                if all_mean_values:
                    final_mean_dict = {}
                    final_std_dict = {}
                    
                    for time, values in all_mean_values.items():
                        values_array = np.array(values)
                        final_mean_dict[time] = round(float(np.mean(values_array)), 2)
                        final_std_dict[time] = round(float(np.std(values_array)), 2)
                    
                    stock_stats['rolling_full'] = {
                        "mean": final_mean_dict,
                        "std": final_std_dict
                    }
                else:
                    stock_stats['rolling_full'] = {"mean": {}, "std": {}}
            
            batch_results[stock_code] = stock_stats
            
        except Exception as e:
            print(f"处理股票 {stock_code} 统计数据时发生错误: {str(e)}")
            continue
    
    return batch_results

def process_statistics_data_optimized(data_dict: dict, target_date: str, date_interval: int):
    """优化后的统计数据处理"""
    print("正在处理统计数据（优化版本）...")
    
    # 获取交易股票列表
    stock_list, actual_date = get_trading_stocks_for_date(data_dict, target_date)
    print(f"找到 {len(stock_list)} 只股票，实际日期: {actual_date}")
    
    if not stock_list:
        return {}
    
    # 并行获取股票有效日期
    print("正在获取股票有效交易日期...")
    
    # 使用部分函数来传递参数
    get_dates_func = partial(
        get_stock_dates_batch,
        data_dict=data_dict,

        
        actual_date=actual_date,
        date_interval=date_interval
    )
    
    # 将股票列表分批
    stock_chunks = [stock_list[i:i+100] for i in range(0, len(stock_list), 100)]
    
    stock_dates = {}
    with ThreadPoolExecutor(max_workers=min(4, len(stock_chunks))) as executor:
        future_to_chunk = {
            executor.submit(get_dates_func, chunk): chunk 
            for chunk in stock_chunks
        }
        
        for future in as_completed(future_to_chunk):
            batch_result = future.result()
            stock_dates.update(batch_result)
    
    print(f"获取到 {len(stock_dates)} 只股票的有效日期数据")
    
    # 预处理数据
    processed_data = {}
    for stock_code, dates_list in stock_dates.items():
        processed_data[stock_code] = (
            dates_list,
            {
                date: {
                    k: v for k, v in data_dict[date][stock_code].items()
                    if k.startswith('rolling') or k == 'rolling_full'
                }
                for date in dates_list
                if date in data_dict and stock_code in data_dict[date]
            }
        )
    
    # 优化的批处理
    optimal_batch_size = max(10, len(processed_data) // (NUM_PROCESSES * 2))
    print(f"使用批大小: {optimal_batch_size}")
    
    # 将处理数据分批
    data_items = list(processed_data.items())
    batches = []
    for i in range(0, len(data_items), optimal_batch_size):
        batch = dict(data_items[i:i + optimal_batch_size])
        batches.append(batch)
    
    # 并行处理统计数据
    stats_data = {}
    with ProcessPoolExecutor(max_workers=NUM_PROCESSES) as executor:
        future_to_batch = {
            executor.submit(process_statistics_batch, batch): batch 
            for batch in batches
        }
        
        for future in tqdm(as_completed(future_to_batch), 
                          total=len(future_to_batch), 
                          desc="处理统计数据批次"):
            try:
                batch_result = future.result()
                stats_data.update(batch_result)
            except Exception as e:
                print(f"处理统计批次时发生错误: {str(e)}")
                continue
    
    return stats_data

def get_stock_dates_batch(stocks_batch, data_dict, actual_date, date_interval):
    """批处理获取股票有效日期 - 提取到模块级别以支持多进程"""
    batch_result = {}
    for stock in stocks_batch:
        dates = get_previous_n_trading_dates(data_dict, actual_date, stock, date_interval)
        if dates:
            batch_result[stock] = dates
    return batch_result

def process_time_chunk(chunk_data):
    """处理时间数据块 - 提取到模块级别以支持多进程"""
    time_data = {}
    
    for stock_code, stock_data in chunk_data.items():
        for window_type, window_data in stock_data.items():
            for metric_type, time_series_data in window_data.items():
                for time, value in time_series_data.items():
                    if time not in time_data:
                        time_data[time] = {}
                    if stock_code not in time_data[time]:
                        time_data[time][stock_code] = {}
                    if window_type not in time_data[time][stock_code]:
                        time_data[time][stock_code][window_type] = {}
                    
                    time_data[time][stock_code][window_type][metric_type] = value
    
    return time_data

def convert_to_time_format_parallel(stats_data: dict) -> dict:
    """并行转换为时间序列格式"""
    print("正在转换为时间序列格式（并行版本）...")
    
    # 将股票数据分块
    stock_items = list(stats_data.items())
    chunk_size = max(50, len(stock_items) // NUM_PROCESSES)
    
    chunks = []
    for i in range(0, len(stock_items), chunk_size):
        chunk = dict(stock_items[i:i + chunk_size])
        chunks.append(chunk)
    
    # 并行处理
    final_time_data = {}
    with ProcessPoolExecutor(max_workers=NUM_PROCESSES) as executor:
        future_to_chunk = {
            executor.submit(process_time_chunk, chunk): chunk 
            for chunk in chunks
        }
        
        for future in tqdm(as_completed(future_to_chunk), 
                          total=len(future_to_chunk), 
                          desc="转换时间格式"):
            try:
                chunk_result = future.result()
                
                # 合并时间数据
                for time, time_data in chunk_result.items():
                    if time not in final_time_data:
                        final_time_data[time] = {}
                    
                    for stock_code, stock_data in time_data.items():
                        if stock_code not in final_time_data[time]:
                            final_time_data[time][stock_code] = {}
                        
                        for window_type, window_data in stock_data.items():
                            final_time_data[time][stock_code][window_type] = window_data
                            
            except Exception as e:
                print(f"转换时间格式时发生错误: {str(e)}")
                continue
    
    return final_time_data


def upload_to_minio(file_path: str, object_name: str):
    """
    上传本地文件到 MinIO
    """
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )

    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)
    
    try:
        client.fput_object(MINIO_BUCKET, object_name, file_path)
        print(f"☁️ 文件已上传至 MinIO: {MINIO_BUCKET}/{object_name}")
    except Exception as e:
        print(f"❌ 上传 MinIO 失败: {e}")


def save_data_as_parquet(final_data: dict, output_path: str):
    """将数据保存为Parquet格式（优化版本）"""
    rows = []
    for time_str, stocks_data in final_data.items():
        for stock_code, stock_data in stocks_data.items():
            for window_type, metrics in stock_data.items():
                rows.append({
                    'time': time_str,
                    'stock_code': stock_code,
                    'window_type': window_type,
                    'mean': metrics.get('mean', 0.0),
                    'std': metrics.get('std', 0.0)
                })
    
    df = pd.DataFrame(rows)
    
    # 优化数据类型
    df['time'] = pd.to_datetime(df['time'], format='%H:%M:%S').dt.time
    df['stock_code'] = df['stock_code'].astype('category')
    df['window_type'] = df['window_type'].astype('category')
    df['mean'] = df['mean'].astype('float32')
    df['std'] = df['std'].astype('float32')
    
    # 使用快速压缩算法
    parquet_path = output_path.replace('.json', '.parquet')
    df.to_parquet(
        parquet_path, 
        engine='pyarrow',
        compression='snappy',
        index=False,
        use_dictionary=True,
        compression_level=None
    )
    
    file_size = os.path.getsize(parquet_path) / (1024 * 1024)
    print(f"💾 Parquet文件保存至: {parquet_path} ({file_size:.2f} MB)")

    # 生成对象名，比如用日期时间区分
    target_date = datetime.now().strftime("%Y%m%d")
    object_name = f"time_data_{target_date}.parquet"

    # 上传到 MinIO
    upload_to_minio(parquet_path, object_name)
    return parquet_path

def load_data_from_parquet(parquet_path: str) -> dict:
    """从Parquet文件读取数据并转换回原格式（超快版本）"""
    import pyarrow.parquet as pq
    
    # 读取数据
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    
    # 转换时间为字符串
    df['time_str'] = df['time'].astype(str)
    
    # 使用numpy数组加速（避免pandas的开销）
    times = df['time_str'].values
    stocks = df['stock_code'].values
    windows = df['window_type'].values
    means = df['mean'].values
    stds = df['std'].values
    
    # 构建结果字典 - 单次遍历 O(n)
    final_data = {}
    
    for i in range(len(df)):
        time_str = times[i]
        stock_code = stocks[i]
        window_type = windows[i]
        
        if time_str not in final_data:
            final_data[time_str] = {}
        
        if stock_code not in final_data[time_str]:
            final_data[time_str][stock_code] = {}
        
        final_data[time_str][stock_code][window_type] = {
            'mean': float(means[i]),
            'std': float(stds[i])
        }
    
    return final_data

def save_data_as_csv_gz(final_data: dict, output_path: str):
    """将数据保存为压缩CSV格式"""
    rows = []
    for time_str, stocks_data in final_data.items():
        for stock_code, stock_data in stocks_data.items():
            for window_type, metrics in stock_data.items():
                rows.append([
                    time_str, stock_code, window_type, 
                    metrics.get('mean', 0.0), metrics.get('std', 0.0)
                ])
    
    df = pd.DataFrame(rows, columns=['time', 'stock_code', 'window_type', 'mean', 'std'])
    
    csv_gz_path = output_path.replace('.json', '.csv.gz')
    df.to_csv(csv_gz_path, compression='gzip', index=False)
    print(f"💾 CSV.gz文件保存至: {csv_gz_path}")
    return csv_gz_path

def save_data_as_pickle_gz(final_data: dict, output_path: str):
    """将数据保存为压缩Pickle格式"""
    pickle_gz_path = output_path.replace('.json', '.pkl.gz')
    
    with gzip.open(pickle_gz_path, 'wb') as f:
        pickle.dump(final_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    print(f"💾 Pickle.gz文件保存至: {pickle_gz_path}")
    return pickle_gz_path

def load_data_from_pickle_gz(pickle_gz_path: str) -> dict:
    """从Pickle.gz文件读取数据"""
    with gzip.open(pickle_gz_path, 'rb') as f:
        return pickle.load(f)

def clean_old_output_files(output_dir: str, current_file: str, keep_count: int = 2):
    """删除旧的输出文件，保留最新的几个 - 修改为支持parquet"""
    try:
        # 查找所有 time_data_*.parquet 文件
        pattern = os.path.join(output_dir, "time_data_*.parquet")
        all_files = glob.glob(pattern)
        
        # 排除当前文件
        other_files = [f for f in all_files if f != current_file]
        
        if not other_files:
            print("📁 没有找到历史输出文件")
            return
        
        # 按修改时间排序，最新的在后面
        other_files.sort(key=os.path.getmtime)
        
        # 如果文件数量超过保留数量，删除多余的旧文件
        if len(other_files) >= keep_count:
            files_to_delete = other_files[:-keep_count+1]  # 保留 keep_count-1 个旧文件
            
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    print(f"🗑️ 已删除旧文件: {os.path.basename(file_path)}")
                except OSError as e:
                    print(f"⚠️ 删除文件失败 {os.path.basename(file_path)}: {e}")
        
    except Exception as e:
        print(f"⚠️ 清理旧文件时发生错误: {e}")


# import pandas as pd
# import numpy as np
# from datetime import datetime
# from functools import partial
# from concurrent.futures import ProcessPoolExecutor, as_completed
# from tqdm import tqdm
# import json
# import os

# # ======================== 配置 ========================
# WINDOW_LENGTH_LIST = [1, 3, 5]   # 测试滚动窗口
# INCLUDE_FULL_ROLLING = True       # 是否包含全量滚动
# NUM_PROCESSES = 2                 # 并行进程数
# SAVE_PATH = "./test_output"       # CSV 保存路径
# os.makedirs(SAVE_PATH, exist_ok=True)


# def generate_test_data(num_stocks=3, num_minutes=5):
#     dfs = []
#     for i in range(num_stocks):
#         ts_code = f"{i:06d}"
#         trade_time = pd.date_range('2025-10-17 09:30:00', periods=num_minutes, freq='1T')
#         df = pd.DataFrame({
#             'trade_date': ['2025-10-17'] * num_minutes,
#             'ts_code': [ts_code] * num_minutes,
#             'trade_time': trade_time,
#             'time_only': trade_time.time,
#             'vol': np.random.randint(100, 500, size=num_minutes)
#         })
#         dfs.append(df)
#     return pd.concat(dfs).reset_index(drop=True)

# ======================== CSV 输出函数 ========================
def save_rolling_to_csv(rolling_result, save_path):
    os.makedirs(save_path, exist_ok=True)
    
    for trade_date, stocks_data in rolling_result.items():
        rows = []
        for ts_code, stock_data in stocks_data.items():
            row = {'ts_code': ts_code}
            for k, v in stock_data.items():
                if k == 'rolling_full':
                    # rolling_full 是带 mean 和 std 的字典
                    for sub_k, sub_v in v['mean'].items():
                        row[f"{k}_mean_{sub_k}"] = sub_v
                    for sub_k, sub_v in v['std'].items():
                        row[f"{k}_std_{sub_k}"] = sub_v
                else:
                    # 普通 rolling 窗口
                    for time_k, val in v.items():
                        row[f"{k}_{time_k}"] = val
            rows.append(row)
        df = pd.DataFrame(rows)
        file_path = os.path.join(save_path, f"rolling_{trade_date}.csv")
        df.to_csv(file_path, index=False)
        print(f"💾 已保存: {file_path}")

# # ======================== 测试脚本 ========================
# if __name__ == "__main__":
#     df_test = generate_test_data(num_stocks=3, num_minutes=5)
    
#     # 单批次测试
#     test_chunk = [('2025-10-17', '000000', df_test[df_test['ts_code']=='000000'])]
#     single_result = process_stock_chunk(test_chunk, WINDOW_LENGTH_LIST, INCLUDE_FULL_ROLLING)
#     print("=== 单批次结果 ===")
#     print(json.dumps(single_result, indent=2, ensure_ascii=False))
    
#     # 并行计算测试
#     parallel_result = calculate_rolling_data_parallel_optimized(df_test)
#     print("=== 并行计算结果 ===")
#     print(json.dumps(parallel_result, indent=2, ensure_ascii=False))
    
#     # 保存 CSV
#     save_rolling_to_csv(parallel_result, SAVE_PATH)

def main():
    """优化后的主函数"""
    print("=== 开始数据处理（优化版本）===")
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 修改输出文件扩展名
    output_path = os.path.join(OUTPUT_DIR, f"time_data_{TARGET_DATE}.parquet")
    
    if os.path.exists(output_path):
        print(f"✅ 输出文件已存在: {os.path.basename(output_path)}")
        print("❌ 跳过处理")
        return
    
    print(f"📝 目标文件: {os.path.basename(output_path)}")
    print(f"🖥️ 使用 {NUM_PROCESSES} 个CPU进程进行并行处理")
    
    try:
        # 步骤1: 获取和预处理数据
        print("📊 获取原始数据...")
        raw_data = get_stock_data()
        
        print("🔄 预处理数据...")
        df = preprocess_stock_minute_data(raw_data)
        
        print("⚡ 并行计算滚动数据...")
        rolling_data = calculate_rolling_data_parallel_optimized(df)
        
        # 步骤2: 并行处理统计数据
        print("📈 并行处理统计数据...")
        stats_data = process_statistics_data_optimized(rolling_data, TARGET_DATE, DATE_INTERVAL)
        
        # 步骤3: 并行转换为时间序列格式
        print("🔄 并行转换时间序列格式...")
        final_data = convert_to_time_format_parallel(stats_data)
        
        # 步骤4: 保存最终结果 (修改这部分)
        print(f"💾 保存最终结果...")
        final_path = save_data_as_parquet(final_data, output_path)
        
        print(f"✅ 数据处理完成")
        print(f"包含 {len(final_data)} 个时间点的数据")
        
        # 步骤5: 清理旧文件 (需要修改pattern)
        print("🧹 清理历史文件...")
        clean_old_output_files(OUTPUT_DIR, final_path)
        
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

# ======================== 测试脚本 ========================
if __name__ == "__main__":
    main()