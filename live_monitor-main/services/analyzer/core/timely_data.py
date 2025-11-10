import requests
import time
from datetime import datetime, timedelta, time as dt_time
import json
import os
import pandas as pd
import ast
import glob
from typing import Tuple, Dict, List, Optional, Any
from dataclasses import dataclass
import dotenv
import numpy as np # Added for np.nan and np.sign
import gzip
import pickle

# 加载环境变量
dotenv.load_dotenv()

# ==================== 配置常量 ====================
@dataclass
class TradingConfig:
    """交易配置类"""
    # 交易时间段
    MORNING_START: dt_time = dt_time(9, 31, 0)
    MORNING_END: dt_time = dt_time(11, 30, 0)
    AFTERNOON_START: dt_time = dt_time(13, 0, 0)
    AFTERNOON_END: dt_time = dt_time(15, 0, 0)
    
    # 时间常量（秒）
    MINUTE_SECONDS: int = 60
    HOUR_SECONDS: int = 3600
    SLEEP_CHECK_INTERVAL: int = 600  # 10分钟
    
    # 数据配置
    MAX_ROLLING_LENGTH: int = 30
    WINDOW_LENGTHS: List[int] = None
    MAX_RESULT_FILES: int = 5
    UPDATE_INTERVAL: int = 60
    
    def __post_init__(self):
        if self.WINDOW_LENGTHS is None:
            self.WINDOW_LENGTHS = [1, 5, 10, 30]

@dataclass
class PathConfig:
    """路径配置类"""
    # 支持通过环境变量配置数据根目录
    data_root: str = os.getenv('DATA_ROOT', os.path.dirname(os.path.abspath(__file__)))
    
    @property
    def previous_data_path(self) -> str:
        """动态获取最新的时间数据文件路径"""
        statistic_dir = os.path.join(self.data_root, "statistic_data")
        
        # 确保目录存在
        if not os.path.exists(statistic_dir):
            os.makedirs(statistic_dir)
        
        # 查找所有匹配的时间数据文件 - 改为parquet格式
        pattern = os.path.join(statistic_dir, "time_data_*.parquet")
        files = glob.glob(pattern)
        
        if files:
            # 按修改时间排序，返回最新的文件
            latest_file = max(files, key=os.path.getmtime)
            print(f"📁 使用最新的数据文件: {latest_file}")
            return latest_file
        else:
            # 如果没有找到文件，使用当前日期作为默认值
            today_date = datetime.now().strftime('%Y-%m-%d')
            default_file = os.path.join(statistic_dir, f"time_data_{today_date}.parquet")
            print(f"⚠️ 未找到历史数据文件，将使用: {default_file}")
            return default_file
    
    @property
    def save_data_path(self) -> str:
        return os.path.join(self.data_root, "data", "test_result")
    
    @property
    def test_data_path(self) -> str:
        return os.path.join(self.data_root, "data", "test_data")
    
    @property
    def index_data_path(self) -> str:
        return os.path.join(self.data_root, "data", "index_data")
    
    @property
    def index_weight_data_path(self) -> str:
        return os.path.join(self.data_root, "data", "index_weight_data.csv")

    @property
    def test_save_data_path(self) -> str:
        """测试模式专用保存路径"""
        return os.path.join(self.data_root, "data", "test_result_temp")

# 初始化配置
CONFIG = TradingConfig()
PATHS = PathConfig()

# API配置
API_URL = "http://dataapi.trader.com/live/cn/all"

# ==================== A股交易时间映射系统 ====================
def create_trading_time_map() -> Tuple[Dict[str, int], Dict[int, str]]:
    """
    创建A股交易时间映射
    使用配置中的交易时间段
    """
    time_to_index: Dict[str, int] = {}
    index_to_time: Dict[int, str] = {}
    index = 0
    
    # 生成交易时间段
    sessions = [
        (CONFIG.MORNING_START, CONFIG.MORNING_END),
        (CONFIG.AFTERNOON_START, CONFIG.AFTERNOON_END)
    ]
    
    for start_time, end_time in sessions:
        current_time = datetime.combine(datetime.today().date(), start_time)
        end_datetime = datetime.combine(datetime.today().date(), end_time)
        
        while current_time < end_datetime:
            time_str = current_time.strftime("%H:%M:%S")
            time_to_index[time_str] = index
            index_to_time[index] = time_str
            index += 1
            current_time += timedelta(minutes=1)
    
    return time_to_index, index_to_time

# 创建全局映射
TIME_TO_INDEX, INDEX_TO_TIME = create_trading_time_map()

def time_to_trading_index(time_str: str) -> Optional[int]:
    """将时间字符串转换为交易分钟索引"""
    return TIME_TO_INDEX.get(time_str)

def trading_index_to_time(index: int) -> Optional[str]:
    """将交易分钟索引转换为时间字符串"""
    return INDEX_TO_TIME.get(index)

def get_previous_trading_time(time_str: str, minutes_back: int) -> Optional[str]:
    """获取指定分钟数之前的交易时间"""
    current_index = time_to_trading_index(time_str)
    if current_index is None:
        return None
    
    target_index = max(0, current_index - minutes_back)
    return trading_index_to_time(target_index)

def is_trading_time(time_str: str) -> bool:
    """检查是否为交易时间"""
    return time_str in TIME_TO_INDEX

def print_trading_map_info() -> None:
    """打印交易时间映射信息（调试用）"""
    total_minutes = len(TIME_TO_INDEX)
    if total_minutes > 0:
        print(f"交易时间映射创建完成，共 {total_minutes} 个交易分钟")
        first_time = INDEX_TO_TIME.get(0, "N/A")
        last_time = INDEX_TO_TIME.get(total_minutes - 1, "N/A")
        print(f"交易时间范围: {first_time} - {last_time}")
        print(f"总交易时间: {total_minutes // 60}小时{total_minutes % 60}分钟")

# ==================== 指数文件管理 ====================

def read_index_weight_data(path: str):
    """
    return a dataframe with index: con_code(name = None)  col: index_code  weight 
    """
    df = pd.read_csv(path)
    df.drop(columns=['trade_date'], inplace=True)
    df["con_code"] = df["con_code"].str[:-3]
    df.set_index('con_code', inplace=True)
    df.index.name = None
    return df

def manage_index_files(save_path: str, max_files: int = 5):
    """
    管理index_data文件夹，只保留最新的指定数量的文件
    
    Args:
        save_path: 保存文件的目录路径
        max_files: 最大保留文件数量，默认5个
    """
    try:
        # 确保目录存在
        if not os.path.exists(save_path):
            os.makedirs(save_path)
            return
            
        # 获取目录中所有CSV文件
        csv_files = []
        for filename in os.listdir(save_path):
            if filename.endswith('.csv'):
                file_path = os.path.join(save_path, filename)
                # 获取文件的修改时间
                mtime = os.path.getmtime(file_path)
                csv_files.append((mtime, file_path, filename))
        
        # 如果文件数量超过限制
        if len(csv_files) > max_files:
            # 按修改时间排序（最新的在后面）
            csv_files.sort(key=lambda x: x[0])
            
            # 删除多余的旧文件
            files_to_delete = csv_files[:-max_files]
            
            for _, file_path, filename in files_to_delete:
                os.remove(file_path)
            
    except Exception as e:
        print(f"⚠️ 指数文件管理过程中发生错误: {e}")

# ==================== 原有函数 ====================

def manage_result_files(save_path: str, max_files: int = None) -> None:
    """管理结果文件，只保留最新的指定数量的文件（支持 JSON 和 CSV）"""
    if max_files is None:
        max_files = CONFIG.MAX_RESULT_FILES
        
    try:
        # 获取目录中所有结果文件（JSON 和 CSV）
        all_files = []
        for filename in os.listdir(save_path):
            if filename.startswith('test_') and (filename.endswith('.json') or filename.endswith('.csv')):
                file_path = os.path.join(save_path, filename)
                mtime = os.path.getmtime(file_path)
                all_files.append((mtime, file_path, filename))
        
        # 按文件基名分组（同一时间点的 JSON 和 CSV 是一组）
        file_groups = {}
        for mtime, file_path, filename in all_files:
            base_name = filename.rsplit('.', 1)[0]  # 去掉扩展名
            if base_name not in file_groups:
                file_groups[base_name] = []
            file_groups[base_name].append((mtime, file_path, filename))
        
        # 如果组数超过限制，删除旧的组
        if len(file_groups) > max_files:
            # 按最新修改时间排序组
            sorted_groups = sorted(
                file_groups.items(),
                key=lambda x: max(f[0] for f in x[1])  # 取组内最新的时间
            )
            
            # 删除多余的旧组
            groups_to_delete = sorted_groups[:-max_files]
            
            for base_name, files in groups_to_delete:
                for _, file_path, filename in files:
                    os.remove(file_path)
                    print(f"🗑️ 删除旧文件: {filename}")
            
            print(f"📁 文件管理完成，保留最新的 {max_files} 组文件")
                
    except Exception as e:
        print(f"⚠️ 文件管理过程中发生错误: {e}")

def _display_remaining_files(remaining_files: List[Tuple[float, str, str]]) -> None:
    """显示保留的文件列表"""
    print(f"📋 当前保留文件:")
    for i, (mtime, _, filename) in enumerate(remaining_files, 1):
        file_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {i}. {filename} ({file_time})")

# def load_data_from_parquet(parquet_path: str) -> dict:
#     """从Parquet文件读取数据并转换回原格式（超快版本）"""
#     import pyarrow.parquet as pq
    
#     # 读取数据
#     table = pq.read_table(parquet_path)
#     df = table.to_pandas()
    
#     # 转换时间为字符串
#     df['time_str'] = df['time'].astype(str)
    
#     # 使用numpy数组加速（避免pandas的开销）
#     times = df['time_str'].values
#     stocks = df['stock_code'].values
#     windows = df['window_type'].values
#     means = df['mean'].values
#     stds = df['std'].values
    
#     # 构建结果字典 - 单次遍历 O(n)
#     final_data = {}
    
#     for i in range(len(df)):
#         time_str = times[i]
#         stock_code = stocks[i]
#         window_type = windows[i]
        
#         if time_str not in final_data:
#             final_data[time_str] = {}
        
#         if stock_code not in final_data[time_str]:
#             final_data[time_str][stock_code] = {}
        
#         final_data[time_str][stock_code][window_type] = {
#             'mean': float(means[i]),
#             'std': float(stds[i])
#         }
    
#     return final_data

def load_parquet_optimized(parquet_path: str):
    """优化版：直接返回 DataFrame，不转字典"""
    import pyarrow.parquet as pq
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    df['time'] = df['time'].astype(str)
    return df  # 返回原始 DataFrame

# def read_previous_data(previous_path: str) -> Dict[str, Any]:
#     """读取历史数据文件 - 支持parquet和json格式（返回字典格式，用于向后兼容）"""
#     if previous_path.endswith('.parquet'):
#         return load_data_from_parquet(previous_path)
#     elif previous_path.endswith('.json'):
#         with open(previous_path, 'r', encoding='utf-8') as f:
#             return json.load(f)
#     else:
#         raise ValueError(f"不支持的文件格式: {previous_path}")

def read_previous_data_optimized(previous_path: str) -> pd.DataFrame:
    """读取历史数据文件 - 优化版，直接返回DataFrame"""
    # 存在性校验，提升可观测性
    if not os.path.exists(previous_path):
        raise FileNotFoundError(f"统计数据文件不存在: {previous_path}")
    if previous_path.endswith('.parquet'):
        return load_parquet_optimized(previous_path)
    elif previous_path.endswith('.json'):
        # JSON格式不支持优化：提示使用parquet格式，避免未定义函数引用
        raise ValueError("JSON格式不支持优化，请使用Parquet统计数据文件 (time_data_*.parquet)")
    else:
        raise ValueError(f"不支持的文件格式: {previous_path}")

def get_certain_time_data_optimized(parquet_df: pd.DataFrame, time: str) -> pd.DataFrame:
    """直接查询 Parquet DataFrame"""
    # 筛选特定时间的数据
    time_data = parquet_df[parquet_df['time'] == time].copy()
    
    # Pivot: 从长格式转宽格式
    result = time_data.pivot(
        index='stock_code', 
        columns='window_type', 
        values=['mean', 'std']
    )
    
    # 扁平化列名：('mean', 'rolling1') -> 'rolling1_mean'
    result.columns = [f'{col[1]}_{col[0]}' for col in result.columns]
    
    # ========== 修复：标准化股票代码格式（去掉后缀）==========
    # 如果索引包含 .SZ/.SH/.BJ 后缀，去掉它们以匹配 rolling_result 的格式
    if any('.' in str(idx) for idx in result.index):
        result.index = result.index.str.replace(r'\.(SZ|SH|BJ)$', '', regex=True)
        print(f"  🔧 已标准化股票代码格式（去除后缀），共 {len(result)} 只股票")
    # ========================================================
    
    return result

def read_snapshot_data(snapshot_path: str, analysis_variable: str) -> pd.DataFrame:
    """读取快照数据"""
    snapshot_data = pd.json_normalize(pd.read_json(snapshot_path)["data"])
    snapshot_data = snapshot_data[['Symbol', analysis_variable]].set_index('Symbol')
    snapshot_data.index.name = None
    return snapshot_data

def get_data(snapshot_data: pd.DataFrame, previous_data: pd.DataFrame) -> pd.DataFrame:
    """合并快照数据和历史数据"""
    # 展开字典类型的列
    for col_name in previous_data.columns:
        if col_name in previous_data.columns and isinstance(previous_data[col_name].iloc[0], dict):
            expanded_df = previous_data[col_name].apply(pd.Series)
            expanded_df.columns = [f'{col_name}_{sub_col}' for sub_col in expanded_df.columns]
            previous_data = pd.concat([previous_data, expanded_df], axis=1).drop(columns=[col_name])
    
    print("--------------------------------")
    return snapshot_data.join(previous_data, how='inner')

def get_z_score(final_data: pd.DataFrame, window_length_list: list, save_path: str) -> pd.DataFrame: 
    """计算Z分数（优化版本：处理标准差为0的情况）"""
    print(f"window_length_list: {window_length_list}")

    # 👇 用来存储调试信息的列表
    debug_records = []
    # 时间戳（去掉冒号，避免Windows路径问题）
    time_str = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()).replace(":", "")

    for length in window_length_list:
        mean_col = f'rolling{length}_mean'
        std_col = f'rolling{length}_std'
        rolling_col = f"rolling{length}"
        z_col = f'rolling{length}_z_score'
        
        if all(col in final_data.columns for col in [rolling_col, mean_col, std_col]):
            std_values = final_data[std_col].copy()
            std_values = std_values.replace(0, np.nan)  # 将0替换为NaN
            
            # 计算z-score，标准差为0时保持原始偏差值
            z_scores = (final_data[rolling_col] - final_data[mean_col]) / std_values
            
            # 对于std为0的情况，如果偏差也为0则设为0，否则设为±5（极端值）
            zero_std_mask = final_data[std_col] == 0
            z_scores[zero_std_mask] = 0
            final_data[z_col] = z_scores.round(2)

             # 👇 收集调试信息
            for idx, row in final_data.iterrows():
                debug_records.append({
                    "code": row['code'] if 'code' in final_data.columns else idx,
                    "window": length,
                    "rolling": row[rolling_col],
                    "mean": row[mean_col],
                    "std": row[std_col],
                    "z_score": row[z_col]
                })

    # 保存 debug 文件
    if debug_records:
        debug_df = pd.DataFrame(debug_records)
        debug_file_path = os.path.join(save_path, f'z_score_{time_str}.csv')
        debug_df.to_csv(debug_file_path, index=False, encoding='utf-8-sig')
        print(f"💾 z_score_debug 已保存为 CSV: {debug_file_path}")

    useful_columns = [f'rolling{length}' for length in window_length_list] + \
                    [f'rolling{length}_mean' for length in window_length_list] + \
                    [f'rolling{length}_z_score' for length in window_length_list]
    
    return final_data[useful_columns]

# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# from typing import List

# def get_z_score(final_data: pd.DataFrame, window_length_list: List[int], visualize: bool = True) -> pd.DataFrame:
#     """
#     计算Z分数（不再随机，输出所有行的计算过程）
#     - visualize: 是否对每个window画出可视化对比
#     """
#     print(f"📊 开始计算 Z-score，窗口列表: {window_length_list}")

#     for length in window_length_list:
#         rolling_col = f'rolling{length}'
#         mean_col = f'rolling{length}_mean'
#         std_col = f'rolling{length}_std'
#         z_col = f'rolling{length}_z_score'

#         # 检查列是否存在
#         if not all(col in final_data.columns for col in [rolling_col, mean_col, std_col]):
#             print(f"⚠️ 缺少列，跳过 {length}: {[c for c in [rolling_col, mean_col, std_col] if c not in final_data.columns]}")
#             continue

#         # 复制 std，避免修改原表
#         std_values = final_data[std_col].copy().replace(0, np.nan)

#         # 计算 z-score
#         z_scores = (final_data[rolling_col] - final_data[mean_col]) / std_values

#         # std == 0 的情况处理
#         zero_std_mask = final_data[std_col] == 0
#         z_scores[zero_std_mask] = 0

#         # 保留两位小数
#         final_data[z_col] = z_scores.round(2)

#         # 📝 输出所有行的详细计算过程
#         print(f"\n📌 [rolling{length}] 全部行计算过程：")
#         for idx, row in final_data.iterrows():
#             print(
#                 f"  行 {idx}: rolling={row[rolling_col]:.4f}, "
#                 f"mean={row[mean_col]:.4f}, std={row[std_col]:.4f}, "
#                 f"z={row[z_col]:.4f}"
#             )

#         # 📈 可视化
#         if visualize:
#             plt.figure(figsize=(10, 4))
#             x = np.arange(len(final_data))
#             plt.plot(x, final_data[rolling_col], label='rolling', marker='o')
#             plt.plot(x, final_data[mean_col], label='mean', marker='x')
#             plt.plot(x, final_data[std_col], label='std', marker='s')
#             plt.plot(x, final_data[z_col], label='z_score', marker='^')
#             plt.title(f'Z-Score 计算可视化 (window={length})')
#             plt.xlabel('行索引')
#             plt.legend()
#             plt.grid(True)
#             plt.show()

#     # 返回包含 rolling / mean / z_score 的列
#     useful_columns = []
#     for length in window_length_list:
#         useful_columns += [f'rolling{length}', f'rolling{length}_mean', f'rolling{length}_z_score']

#     return final_data[useful_columns]



def fetch_minute_data(url: str) -> Optional[Dict[str, Any]]:
    """获取分钟级数据"""
    try:
        response = requests.get(url, timeout=10,proxies={"http":None,"https":None})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求过程中发生错误: {e}")
        return None

def _fetch_cumulative_volume_map(api_url: str) -> Dict[str, float]:
    """从实时HTTP接口获取当前累积成交量（按Symbol）。获取失败返回空字典。"""
    raw = fetch_minute_data(api_url)
    if not raw or "data" not in raw:
        return {}
    # 复用已有转换逻辑：Symbol -> [Name, Latest, ChangePercent, TradingVolume(累计)]
    transformed = _transform_market_data(raw)
    return {
        symbol: float(values[3])  # TradingVolume 为累计量
        for symbol, values in transformed.items()
        if values is not None and len(values) >= 4
    }

# 数据结构说明: 0:股票名称 1:最新价 2:涨跌幅 3:交易量 4:五分钟价格变化 5:30分钟价格变化

def calculate_rolling(rolling: Dict[str, Dict[str, List]], key: str, window_lengths: List[int], certain_time_data: pd.DataFrame = None) -> pd.DataFrame:
    """计算rolling数据，使用交易时间映射考虑A股交易时间连续性"""
    print(f"🔄 开始计算rolling数据，当前时间: {key}")
    
    # 提取交易量数据 - 修复：使用分钟交易量，并保持与预处理数据一致的单位
    volume_data = {}
    for time, stocks in rolling.items():
        volume_data[time] = {}
        for stock_code, stock_data in stocks.items():
            # stock_data[3] 是 [分钟交易量, 累计交易量] 或者是单个值
            if isinstance(stock_data[3], list):
                minute_volume = stock_data[3][0]  # 分钟交易量
            else:
                minute_volume = stock_data[3]
            
            
            volume_data[time][stock_code] = minute_volume
    
    df = pd.DataFrame.from_dict(volume_data, orient='index')
    ordered_times = _get_ordered_trading_times(df.index, key)
    df = df.reindex(ordered_times)
    
    current_idx = ordered_times.index(key)
    current_trading_index = time_to_trading_index(key)
    print(f"📊 可用时间点: {len(ordered_times)}, 当前位置: {current_idx}, 交易索引: {current_trading_index}")
    
    return _calculate_rolling_windows(df, key, ordered_times, current_idx, current_trading_index, window_lengths, certain_time_data)

def _get_ordered_trading_times(time_indices: List[str], current_key: str) -> List[str]:
    """获取按交易时间索引排序的时间列表"""
    time_index_pairs = [
        (time, time_to_trading_index(time)) 
        for time in time_indices 
        if time_to_trading_index(time) is not None
    ]
    time_index_pairs.sort(key=lambda x: x[1])
    return [pair[0] for pair in time_index_pairs]

def get_realtime_trading_volume_sum() -> float:
    
    url = "http://dataapi.trader.com/live/cn/all"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data_json = resp.json()

        # 确保结构正确
        if "data" in data_json and isinstance(data_json["data"], list):
            trading_volumes = [item.get("TradingVolume", 0) for item in data_json["data"]]
            total_volume = sum(trading_volumes)
            return total_volume
        else:
            print("返回 JSON 结构异常:", data_json)
            return 0.0

    except Exception as e:
        print(f"获取实时数据失败: {e}")
        return 0.0

def _calculate_rolling_windows(df: pd.DataFrame, key: str, ordered_times: List[str], 
                             current_idx: int, current_trading_index: int, 
                             window_lengths: List[int], certain_time_data: pd.DataFrame = None) -> pd.DataFrame:
    """计算各个窗口长度的rolling数据（优化版本）"""
    result = {}
    
    # 计算从开盘到当前的累积交易量（rolling_full）
    current_data = df.loc[ordered_times[:current_idx + 1]]
    print(current_data)
    if not current_data.empty:
        # 优先用 HTTP 接口累计成交量（按 Symbol），失败回退为分钟量累加
        api_cum_map = _fetch_cumulative_volume_map(API_URL)
        if api_cum_map:
            cumulative_series = pd.Series(api_cum_map).reindex(df.columns)
            result['rolling_full_sum'] = cumulative_series
        else:
            cumulative_sum = current_data.sum()
            result['rolling_full_sum'] = cumulative_sum
        
            # 如果提供了statistic data
            if certain_time_data is not None and not certain_time_data.empty:
                # 直接检查是否有 rolling_full 列
                rolling_full_cols = [col for col in certain_time_data.columns if 'rolling_full' in col]
                if rolling_full_cols:
                    rolling_full_mean_col = [col for col in rolling_full_cols if 'mean' in col]
                    rolling_full_std_col = [col for col in rolling_full_cols if 'std' in col]
                    
                    if rolling_full_mean_col and rolling_full_std_col:
                        # 获取历史统计数据
                        preprocess_sum_all = certain_time_data[rolling_full_mean_col[0]]
                        preprocess_std_all = certain_time_data[rolling_full_std_col[0]]
                        
                        # 统一股票代码格式：尝试匹配带后缀和不带后缀的格式
                        # cumulative_sum 的 index 可能是 '000001'
                        # preprocess 的 index 可能是 '000001.SZ' 或 '000001.SH'
                        
                        # 创建映射：去掉后缀
                        preprocess_sum_normalized = preprocess_sum_all.copy()
                        preprocess_std_normalized = preprocess_std_all.copy()
                        
                        # 如果预处理数据有后缀，创建不带后缀的索引
                        if any('.' in str(idx) for idx in preprocess_sum_all.index):
                            # 去掉 .SZ/.SH 后缀
                            new_index = preprocess_sum_all.index.str.replace(r'\.(SZ|SH|BJ)$', '', regex=True)
                            preprocess_sum_normalized.index = new_index
                            preprocess_std_normalized.index = new_index
                        
                        # 找到共同的股票代码
                        common_stocks = cumulative_sum.index.intersection(preprocess_sum_normalized.index)
                        
                        if len(common_stocks) > 0:
                            # 对齐所有 Series 到相同的索引
                            cumulative_sum_aligned = cumulative_sum.loc[common_stocks]
                            preprocess_sum = preprocess_sum_normalized.loc[common_stocks]
                            preprocess_std = preprocess_std_normalized.loc[common_stocks]
                            
                            # 计算偏差
                            diff = cumulative_sum_aligned - preprocess_sum
                            
                            # 初始化 z_scores
                            z_scores = pd.Series(0.0, index=common_stocks, dtype=float)
                            
                            # 处理标准差 > 0 的情况
                            mask_valid_std = preprocess_std > 1e-6
                            if mask_valid_std.sum() > 0:
                                valid_stocks = mask_valid_std[mask_valid_std].index
                                z_scores.loc[valid_stocks] = (
                                    diff.loc[valid_stocks] / preprocess_std.loc[valid_stocks]
                                ).round(2)
                            
                            # 处理标准差 ≈ 0 的情况
                            mask_zero_std = preprocess_std <= 1e-6
                            if mask_zero_std.sum() > 0:
                                zero_stocks = mask_zero_std[mask_zero_std].index
                                z_scores.loc[zero_stocks] = np.where(
                                    abs(diff.loc[zero_stocks]) < 1e-6,
                                    0,  # 几乎没有偏差
                                    np.sign(diff.loc[zero_stocks]) * 3  # 有明显偏差
                                )
                            
                            result['rolling_full'] = z_scores
                            print(f"  📈 rolling_full: 计算了 {len(common_stocks)} 只股票的z-score")
                        else:
                            result['rolling_full'] = pd.Series(np.nan, index=cumulative_sum.index)
                            print(f"  ⚠️ rolling_full: 没有匹配的股票代码（格式可能不一致）")
                    else:
                        result['rolling_full'] = pd.Series(np.nan, index=cumulative_sum.index)
                        print(f"  📈 rolling_full: 未找到完整预处理数据列")
                else:
                    result['rolling_full'] = pd.Series(np.nan, index=cumulative_sum.index)
                    print(f"  📈 rolling_full: 未找到rolling_full列")
            else:
                result['rolling_full'] = pd.Series(np.nan, index=cumulative_sum.index)
                print(f"  ⚠️ rolling_full: 未提供预处理数据，设为NaN")
    

    # 计算其他滚动窗口
    for window in window_lengths:
        col_name = f'rolling{window}'
        
        available_minutes = current_idx + 1
        
        if available_minutes <= window:
            window_data = current_data
            print(f"  📈 rolling{window}: 时间不足{window}分钟，使用所有数据 ({available_minutes} 分钟)")
        else:
            start_time = get_previous_trading_time(key, window - 1)
            if start_time is None:
                window_data = current_data
                print(f"  📈 rolling{window}: 无法获取历史时间，使用所有数据")
            else:
                window_times = [
                    time_str for time_str in ordered_times[:current_idx + 1]
                    if time_to_trading_index(time_str) is not None
                    and time_to_trading_index(time_str) >= time_to_trading_index(start_time)
                ]
                window_data = df.loc[window_times] if window_times else current_data
                print(f"  📈 rolling{window}: 使用时间窗口 {start_time} - {key} ({len(window_times)} 个时间点)")
        
        rolling_sum = window_data.sum()
        result[col_name] = rolling_sum.round(2)
    
    return pd.DataFrame(result)



def get_time_status_and_sleep(test_mode: bool = False) -> Tuple[str, float, str, str]:
    """
    获取当前时间状态和睡眠信息
    返回: (status, wait_seconds, next_session, message)
    """
    now = datetime.now()
    current_time = now.time()
    time_str = now.strftime('%H:%M:%S')
    
    # 测试模式下，总是返回交易状态
    if test_mode:
        return 'trading', 0.0, "测试模式", f"🧪 测试模式: 当前时间 {time_str} (忽略交易时间限制)"
    
    # 判断时间状态并计算等待时间
    if current_time < CONFIG.MORNING_START:
        target_time = datetime.combine(now.date(), CONFIG.MORNING_START)
        wait_seconds = (target_time - now).total_seconds()
        return 'wait', wait_seconds, "早盘开盘", f"🌅 当前时间 {time_str} 开盘前，等待开盘..."
        
    elif CONFIG.MORNING_END < current_time < CONFIG.AFTERNOON_START:
        target_time = datetime.combine(now.date(), CONFIG.AFTERNOON_START)
        wait_seconds = (target_time - now).total_seconds()
        return 'wait', wait_seconds, "午盘开盘", f"🍽️ 当前时间 {time_str} 中午休市，等待下午开盘..."
        
    elif current_time >= CONFIG.AFTERNOON_END:
        tomorrow = now.date() + timedelta(days=1)
        target_time = datetime.combine(tomorrow, CONFIG.MORNING_START)
        wait_seconds = (target_time - now).total_seconds()
        return 'exit', wait_seconds, "明日早盘开盘", f"🌅 当前时间 {time_str} 收盘后，程序将退出..."
        
    else:
        return 'trading', 0.0, "交易时间内", f"✅ 当前时间 {time_str} 交易时间"

def format_time_duration(seconds: float) -> Tuple[int, int, int]:
    """格式化时间持续时间为时分秒"""
    return int(seconds // CONFIG.HOUR_SECONDS), int((seconds % CONFIG.HOUR_SECONDS) // CONFIG.MINUTE_SECONDS), int(seconds % CONFIG.MINUTE_SECONDS)

def handle_sleep(wait_seconds: float, next_session: str) -> None:
    """处理睡眠逻辑的辅助函数"""
    hours, minutes, seconds = format_time_duration(wait_seconds)
    
    print(f"💤 程序进入睡眠模式，等待 {next_session}")
    print(f"💤 预计等待时间: {hours}小时{minutes}分钟{seconds}秒")
    print(f"💤 将在 {(datetime.now() + timedelta(seconds=wait_seconds)).strftime('%Y-%m-%d %H:%M:%S')} 恢复运行")
    
    # 长时间睡眠时定期检查
    if wait_seconds > CONFIG.HOUR_SECONDS:
        _handle_long_sleep(wait_seconds)
    else:
        time.sleep(wait_seconds)
    
    print(f"⏰ 睡眠结束，程序恢复运行")

def _handle_long_sleep(wait_seconds: float) -> None:
    """处理长时间睡眠，定期显示进度"""
    total_sleep = 0.0
    while total_sleep < wait_seconds:
        remaining_sleep = min(CONFIG.SLEEP_CHECK_INTERVAL, wait_seconds - total_sleep)
        time.sleep(remaining_sleep)
        total_sleep += remaining_sleep
        
        if total_sleep % CONFIG.SLEEP_CHECK_INTERVAL == 0 and total_sleep < wait_seconds:
            remaining_time = wait_seconds - total_sleep
            remaining_hours, remaining_minutes = format_time_duration(remaining_time)[:2]
            print(f"💤 继续等待，剩余时间: {remaining_hours}小时{remaining_minutes}分钟")
    
def create_data_structure(current_data: Dict[str, List], rolling: Dict[str, Dict], time_str: str, 
                        start_time: str) -> Dict[str, List]:
    """创建当前时间的数据结构"""
    if not rolling:
        # 第一次初始化
        return {
            symbol: [
                current_data[symbol][0],  # 股票名称
                current_data[symbol][1],  # 最新价
                current_data[symbol][2],  # 涨跌幅
                [current_data[symbol][3], current_data[symbol][3]],  # [分钟交易量, 累计交易量]
                0,  # 五分钟价格变化
                0   # 30分钟价格变化
            ]
            for symbol in current_data
        }
    else:
        # 获取历史时间点
        last_min_time = get_previous_trading_time(time_str, 1) or start_time
        five_min_time = get_previous_trading_time(time_str, 5) or start_time
        thirty_min_time = get_previous_trading_time(time_str, 30) or start_time
        
        print(f"📅 历史时间点: 1分钟前={last_min_time}, 5分钟前={five_min_time}, 30分钟前={thirty_min_time}")
        
        # 获取历史数据
        last_min_data = rolling.get(last_min_time, rolling[start_time])
        five_min_data = rolling.get(five_min_time, rolling[start_time])
        thirty_min_data = rolling.get(thirty_min_time, rolling[start_time])
        
        return {
            symbol: [
                current_data[symbol][0],  # 股票名称
                current_data[symbol][1],  # 最新价
                current_data[symbol][2],  # 涨跌幅
                [  # [分钟交易量, 累计交易量]
                    current_data[symbol][3] - last_min_data[symbol][3][1] if symbol in last_min_data else current_data[symbol][3],
                    current_data[symbol][3]
                ],
                # 五分钟价格变化
                ((current_data[symbol][1] - five_min_data[symbol][1]) / five_min_data[symbol][1] * 100 
                 if symbol in five_min_data and five_min_data[symbol][1] != 0 else 0),
                # 30分钟价格变化
                ((current_data[symbol][1] - thirty_min_data[symbol][1]) / thirty_min_data[symbol][1] * 100 
                 if symbol in thirty_min_data and thirty_min_data[symbol][1] != 0 else 0)
            ]
            for symbol in current_data
        }

def process_data_and_save(rolling: Dict, time_str: str, statistics_data: Dict, save_path: str, index_weight_data: pd.DataFrame) -> None:
    """处理数据并保存文件"""
    current_trading_index = time_to_trading_index(time_str)
    
    # 获取历史统计数据（先定义）
    certain_time_data = get_certain_time_data_optimized(statistics_data, time_str)
    
    # 计算rolling结果（后使用）
    rolling_result = calculate_rolling(rolling, time_str, CONFIG.WINDOW_LENGTHS, certain_time_data)

    # 保存 rolling_result 为 CSV 文件（方便调试）
    rolling_csv_path = os.path.join(save_path, f'rolling_result_{time_str.replace(":", "")}.csv')
    os.makedirs(save_path, exist_ok=True)  # 确保目录存在
    rolling_result.to_csv(rolling_csv_path, index=True)  # 保存索引
    print(f"💾 rolling_result 已保存为 CSV: {rolling_csv_path}")
    rolling_dict_csv_path = os.path.join(save_path, f'rolling_{time_str.replace(":", "")}.csv')
    os.makedirs(save_path, exist_ok=True)

    # 将嵌套字典转为 DataFrame
    rolling_df = pd.DataFrame.from_dict(rolling[time_str], orient='index',
                                    columns=["Name", "Price", "Chg", "Vol", "Chg5", "Chg30"])
    rolling_df.index.name = "Symbol"  # 股票代码作为索引
    # rolling_df.to_csv(rolling_dict_csv_path)
    # print(f"💾 rolling 已保存为 CSV: {rolling_dict_csv_path}")

    
    # 创建保存数据的DataFrame
    index_list = ["Name", "Price", "Chg", "Vol", "Chg5", "Chg30"]
    save_data = {
        symbol: [
            rolling[time_str][symbol][0],  # Name
            rolling[time_str][symbol][1],  # Price
            rolling[time_str][symbol][2],  # Chg
            rolling_result.loc[symbol, 'rolling_full_sum'],  # Vol: 使用分钟成交量，保持与预处理一致的单位
            rolling[time_str][symbol][4],  # Chg5
            rolling[time_str][symbol][5]   # Chg30
        ]
        for symbol in rolling[time_str]
    }
    info = pd.DataFrame(save_data, index=index_list).T

    # # ✅ 保存 info 为 CSV
    # info_csv_path = os.path.join(save_path, f'info_{time_str.replace(":", "")}.csv')
    # info.to_csv(info_csv_path, index=True)
    # print(f"💾 info 已保存为 CSV: {info_csv_path}")
    
    # 历史统计数据已在前面获取
    # 合并数据并计算Z分数
    z_score_data = rolling_result.join(certain_time_data, how='inner')
    z_score_data = get_z_score(z_score_data, CONFIG.WINDOW_LENGTHS, save_path)
    
    # 如果存在rolling_full（从开盘到现在的z-score），添加到z_score_data中
    if 'rolling_full' in rolling_result.columns:
        z_score_data['rolling_full_z_score'] = rolling_result['rolling_full']
    
     # ✅ 保存 z_score_data 为 CSV
    z_score_csv_path = os.path.join(save_path, f'z_score_{time_str.replace(":", "")}.csv')
    z_score_data.to_csv(z_score_csv_path, index=True)
    print(f"💾 z_score_data 已保存为 CSV: {z_score_csv_path}")


    # 创建最终数据
    useful_columns = ["Name", "Price", "Chg", "Vol"] + \
                    [f'rolling{length}_z_score' for length in CONFIG.WINDOW_LENGTHS] + \
                    ['rolling_full_z_score'] + \
                    ["Chg5", "Chg30"]
    final_data = info.join(z_score_data, how="inner")[useful_columns]
    final_data.sort_values(by="rolling5_z_score", ascending=False, inplace=True)

    # ✅ 保存 final_data 为 CSV
    final_csv_path = os.path.join(save_path, f'final_data_{time_str.replace(":", "")}.csv')
    final_data.to_csv(final_csv_path, index=True)
    print(f"💾 final_data 已保存为 CSV: {final_csv_path}")


    # 计算指数
    join_index_data = index_weight_data.join(final_data, how='left')
    process_col = final_data.columns[2:]  # 省略掉Name列
    useful_col = []
    
    for col in process_col:
        join_index_data[f"index_{col}"] = (join_index_data['weight'] * join_index_data[col])/100
        useful_col.append(f"index_{col}")
        
    df = join_index_data.groupby(['index_code','index_name']).sum()[useful_col].reset_index(level='index_name')
    df.index.name = None

    # 保存指数数据（CSV 格式），修复: 去除文件名中的冒号并在权限受限时回退路径
    safe_time_str = time_str.replace(':', '')
    index_dir = PATHS.index_data_path
    os.makedirs(index_dir, exist_ok=True)
    index_csv_path = os.path.join(index_dir, f'{safe_time_str}.csv')
    try:
        df.to_csv(index_csv_path, index=True)
        manage_index_files(index_dir, max_files=5)
        print(f"📊 指数数据已更新: {time_str} -> {index_csv_path}")
    except PermissionError:
        # 回退到保存目录下的 index_data 子目录
        fallback_dir = os.path.join(save_path, 'index_data')
        os.makedirs(fallback_dir, exist_ok=True)
        index_csv_path = os.path.join(fallback_dir, f'{safe_time_str}.csv')
        df.to_csv(index_csv_path, index=True)
        manage_index_files(fallback_dir, max_files=5)
        print(f"📊 指数数据已更新(回退): {time_str} -> {index_csv_path}")
    
    # ========== 新增：保存 JSON 格式（主要格式） ==========
    file_base_name = f"test_{time_str.replace(':', '')}_idx{current_trading_index}"
    
    # 准备 JSON 数据（重置索引，将股票代码作为字段）
    json_data = final_data.reset_index()
    json_data.rename(columns={'index': 'code'}, inplace=True)
    
    # 重命名列以匹配前端期望（简化字段名）
    json_data.rename(columns={
        'rolling1_z_score': 'r1_z',
        'rolling5_z_score': 'r5_z',
        'rolling10_z_score': 'r10_z',
        'rolling30_z_score': 'r30_z',
        'rolling_full_z_score': 'rolling_full'
    }, inplace=True)
    
    # 保存为 JSON（orient='records' 生成数组格式），权限回退到 /tmp
    try:
        os.makedirs(save_path, exist_ok=True)
        json_target_dir = save_path
    except PermissionError:
        json_target_dir = os.path.join('/tmp', 'live_monitor', 'test_result')
        os.makedirs(json_target_dir, exist_ok=True)
    
    json_file_path = os.path.join(json_target_dir, f"{file_base_name}.json")
    json_data.to_json(
        json_file_path,
        orient='records',
        force_ascii=False,
        double_precision=2  # 保留2位小数，减小文件大小
    )
    print(f"💾 JSON数据已保存: {json_file_path} ({len(json_data)} 条记录)")
    
    # 可选：保留 CSV 作为备份（调试用）
    # csv_file_path = os.path.join(save_path, f"{file_base_name}.csv")
    # final_data.to_csv(csv_file_path)
    # print(f"💾 CSV数据已保存: {file_base_name}.csv")
    # ======================================================
    
    # 管理文件数量（需要同时管理 JSON 和 CSV）
    manage_result_files(json_target_dir)

def wait_for_minute_start() -> None:
    """等待到下一分钟的开始"""
    now = datetime.now()
    if now.second != 0 or now.microsecond != 0:
        seconds_to_wait = CONFIG.MINUTE_SECONDS - now.second
        if now.microsecond > 0:
            seconds_to_wait -= 1
        time.sleep(seconds_to_wait + (1 - now.microsecond / 1_000_000 if now.microsecond > 0 else 0))

def print_startup_info(api_url: str, data_path: str, save_path: str) -> None:
    """打印程序启动信息"""
    print_trading_map_info()
    print(f"🚀 股票分析程序启动")
    print(f"📡 数据源: {api_url}")
    print(f"📂 统计数据: {data_path}")
    print(f"💾 保存路径: {save_path}")
    print(f"⏱️ 更新间隔: {CONFIG.UPDATE_INTERVAL} 秒")
    print(f"🔄 程序运行规则:")
    print(f"   - 交易时间内正常运行并处理数据")
    print(f"   - 非交易时间自动睡眠等待")
    print(f"   - 15:00收盘后自动退出程序")
    print(f"   - 收盘后启动将等待明日9:30开盘")
    print(f"❌ 按 Ctrl+C 可安全停止程序")
    print("=" * 60)

def _print_exit_message(save_path: str) -> None:
    """打印程序退出信息"""
    print(f"🔚 交易时间结束，程序正常退出")
    print(f"📊 程序运行结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💾 数据已保存至: {save_path}")
    print(f"👋 明日交易时间见！")

def _transform_market_data(fetched_data: Dict[str, Any]) -> Dict[str, List]:
    """转换市场数据格式"""
    return {
        item["Symbol"]: [
            item['StockName'],      # 0:股票名称
            item["Latest"],         # 1:最新价
            item["ChangePercent"],  # 2:涨跌幅
            item["TradingVolume"]   # 3:交易量
        ]
        for item in fetched_data["data"]
    }

# def _process_market_data(fetched_data: Dict[str, Any], time_str: str, 
#                         rolling: Dict[str, Dict], start_time: str,
#                         statistics_data: Dict, save_path: str, index_weight_data: pd.DataFrame) -> str:
#     """处理市场数据的主要逻辑"""
#     current_trading_index = time_to_trading_index(time_str)
    
#     # 设置起始时间
#     if not start_time:
#         start_time = time_str
#         print(f"🎯 设置起始交易时间: {start_time} (索引: {current_trading_index})")
    
#     # 转换数据格式
#     transformed_data = _transform_market_data(fetched_data)
    
#     # 创建数据结构并加入rolling字典
#     result_data = create_data_structure(transformed_data, rolling, time_str, start_time)
#     rolling[time_str] = result_data
    
#     print(f"✓ 当前处理时间: {time_str} (交易索引: {current_trading_index})")
#     print(f"📊 rolling 字典状态: {len(rolling)} 个时间点 {sorted(rolling.keys())}")
    

#     # 管理rolling字典长度
#     if len(rolling) > CONFIG.MAX_ROLLING_LENGTH:
#         oldest_time = min(rolling.keys())
#         del rolling[oldest_time]
#         start_time = min(rolling.keys())
#         print(f"🗑️ 删除过期数据: {oldest_time}")
    
#     # 处理数据并保存
#     process_data_and_save(rolling, time_str, statistics_data, save_path, index_weight_data)
    
#     return start_time

import os
import pandas as pd
import numpy as np
from typing import Dict, Any

def new_create_data_structure(transformed_df: pd.DataFrame, 
                              rolling: Dict[str, Dict[str, Dict[str, Any]]],
                              time_str: str,
                              start_time: str) -> Dict[str, Dict[str, Any]]:
    """
    将 DataFrame 转换为 rolling 字典需要的格式（保证每个 symbol 对应 dict，扁平化 list）。
    
    参数:
        transformed_df: 转换后的行情 DataFrame，至少包含 'symbol', 'name', 'price', 'change', 'volume'
        rolling: 当前 rolling 字典，可用于历史数据引用
        time_str: 当前时间点
        start_time: 起始时间
        
    返回:
        result_data: dict，结构 {symbol: {字段: 值, ...}}
    """
    
    def flatten_value(val):
        """递归扁平化 list，并转成 float/int/string"""
        if isinstance(val, list) and len(val) > 0:
            return flatten_value(val[0])
        elif hasattr(val, 'item'):  # np.float64 / np.int64
            return val.item()
        elif isinstance(val, (float, int)):
            return val
        elif val is None or isinstance(val, pd._libs.missing.NAType):
            return 0
        else:
            return val  # 字符串或其他类型
    
    result_data = {}
    
    for _, row in transformed_df.iterrows():
        symbol = row['symbol']
        attr = {}
        for col in transformed_df.columns:
            if col == 'symbol':
                continue
            val = row[col]
            attr[col] = flatten_value(val)
        result_data[symbol] = attr
    
    return result_data


def _process_market_data(fetched_data: Dict[str, Any], time_str: str,  
                        rolling: Dict[str, Dict[str, Dict[str, Any]]],
                        start_time: str,
                        statistics_data: Dict,
                        save_path: str,
                        index_weight_data: pd.DataFrame) -> str:
    """处理市场数据，并生成可视化/分析用 rolling_df"""
    
    current_trading_index = time_to_trading_index(time_str)

    if not start_time:
        start_time = time_str
        print(f"🎯 设置起始交易时间: {start_time} (索引: {current_trading_index})")

    # --- 转换数据格式 ---
    transformed_data = _transform_market_data(fetched_data)

    # --- 转换 transformed_data 为 DataFrame ---
    if isinstance(transformed_data, dict):
        # dict -> DataFrame，key 是 symbol
        transformed_df = pd.DataFrame.from_dict(transformed_data, orient='index').reset_index()
        transformed_df.rename(columns={'index': 'symbol'}, inplace=True)
    else:
        # 已经是 DataFrame
        transformed_df = transformed_data

    # --- 保存 CSV ---
    debug_dir = os.path.join(save_path, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    transformed_path = os.path.join(debug_dir, f"transformed_data_{time_str.replace(':', '-')}.csv")
    transformed_df.to_csv(transformed_path, index=False)
    print(f"🧾 transformed_data 已保存到: {transformed_path}")

    # --- 创建 rolling dict ---
    result_data = new_create_data_structure(transformed_data, rolling, time_str, start_time)
    rolling[time_str] = result_data

    # --- 管理 rolling dict 长度 ---
    if len(rolling) > CONFIG.MAX_ROLLING_LENGTH:
        oldest_time = min(rolling.keys())
        del rolling[oldest_time]
        start_time = min(rolling.keys())
        print(f"🗑️ 删除过期数据: {oldest_time}")

    # --- 生成 rolling_df 用于可视化和 CSV ---
    rolling_rows = []
    for t, data_dict in rolling.items():
        for symbol, attr in data_dict.items():
            row = {"time": t, "symbol": symbol}
            row.update(attr)
            rolling_rows.append(row)
    rolling_df = pd.DataFrame(rolling_rows)

    rolling_csv_path = os.path.join(debug_dir, "rolling_history.csv")
    rolling_df.to_csv(rolling_csv_path, index=False)
    print(f"📈 rolling 历史数据已保存: {rolling_csv_path}")

    # --- 示例 z-score 计算（可选） ---
    # 按 symbol 分组，计算过去 N 个时间点的 price z-score
    N = 20
    rolling_df["price_mean"] = rolling_df.groupby("symbol")["price"].transform(lambda x: x.rolling(N, min_periods=1).mean())
    rolling_df["price_std"] = rolling_df.groupby("symbol")["price"].transform(lambda x: x.rolling(N, min_periods=1).std())
    rolling_df["price_zscore"] = (rolling_df["price"] - rolling_df["price_mean"]) / rolling_df["price_std"]

    # --- 调用后续处理逻辑 ---
    process_data_and_save(rolling, time_str, statistics_data, save_path, index_weight_data)

    print(f"✓ 当前处理时间: {time_str} (交易索引: {current_trading_index})")
    print(f"📊 rolling 字典状态: {len(rolling)} 个时间点 {sorted(rolling.keys())}")

    return start_time





def test_amz_data():
    import AmazingData as ad 
    import dotenv
    import os
    dotenv.load_dotenv()
    username = os.getenv("AMZ_USERNAME")
    password = os.getenv("AMZ_PWD")
    host = os.getenv("AMZ_HOST")
    port = int(os.getenv("AMZ_PORT"))
    ad.login(username, password,host,port) 
    base_data_object = ad.BaseData() 
    code_list = base_data_object.get_code_list(security_type=' EXTRA_INDEX_A ') 

    # 实时订阅 
    sub_data = ad.SubscribeData() 
    @sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value) 
    def onSnapshot(index: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):     
        print(period, data)  
    
    sub_data.run()  
    

import os
from minio import Minio
from datetime import datetime
from minio.error import S3Error

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = "live-data"

def download_latest_time_data(prefix: str = "time_data_", local_dir: str = "/app/statistic_data"):
    """
    从 MinIO 下载最新的统计数据文件 (例如 time_data_20251020.parquet)，
    并重命名为带中划线日期的格式 (例如 time_data_2025-10-20.parquet)。

    参数:
        prefix (str): 文件名前缀（默认 'time_data_'）
        local_dir (str): 本地下载目录（默认 '/app/statistic_data'）

    返回:
        str: 下载到本地的完整文件路径
    """
    try:
        # 初始化客户端
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )

        if not client.bucket_exists(MINIO_BUCKET):
            raise ValueError(f"❌ 桶不存在: {MINIO_BUCKET}")

        # 获取桶中所有符合命名的对象
        objects = client.list_objects(MINIO_BUCKET, recursive=True)
        time_files = [
            obj.object_name for obj in objects
            if obj.object_name.startswith(prefix) and obj.object_name.endswith(".parquet")
        ]

        if not time_files:
            raise FileNotFoundError(f"⚠️ 未找到符合命名规则的文件: {prefix}*.parquet")

        # 提取日期并找到最新文件
        def extract_date(name):
            try:
                date_str = name.replace(prefix, "").replace(".parquet", "")
                return datetime.strptime(date_str, "%Y%m%d")
            except Exception:
                return datetime.min

        latest_file = max(time_files, key=extract_date)
        latest_date = extract_date(latest_file).strftime("%Y-%m-%d")  # 转成带中划线日期

        # 构造本地路径
        os.makedirs(local_dir, exist_ok=True)
        new_filename = f"{prefix}{latest_date}.parquet"
        local_path = os.path.join(local_dir, new_filename)

        # 下载并重命名
        temp_path = os.path.join(local_dir, os.path.basename(latest_file))
        client.fget_object(MINIO_BUCKET, latest_file, temp_path)

        # 重命名（覆盖旧文件）
        if os.path.exists(local_path):
            os.remove(local_path)
        os.rename(temp_path, local_path)

        print(f"✅ 最新数据文件已下载并重命名: {latest_file} → {new_filename}")
        return local_path

    except S3Error as e:
        print(f"❌ MinIO 错误: {e}")
        raise
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        raise



def main(url: str = None, interval_seconds: int = None, previous_path: str = None, test_mode: bool = False) -> None:
    
    
    download_latest_time_data()

    """主函数：股票分析程序入口"""
    # 使用配置中的默认值
    api_url = url or API_URL
    data_path = previous_path or PATHS.previous_data_path
    # 测试模式使用独立的保存路径
    save_path = PATHS.test_save_data_path if test_mode else PATHS.save_data_path

    #test_amz_data()
    # 测试模式提示
    if test_mode:
        print("🧪 =============== 测试模式启动 ===============")
        print("⚠️ 注意：测试模式将忽略交易时间限制")
        print(f"📁 测试数据将保存到: {save_path}")
        print("✅ 不会影响正式结果文件")
        print("🧪 =======================================")
        # 确保测试目录存在
        os.makedirs(save_path, exist_ok=True)
    
    # 初始化
    start_time = ''
    index_weight_data = read_index_weight_data(PATHS.index_weight_data_path)
    
    # 使用优化版本加载统计数据（DataFrame格式，性能提升10-16倍）
    print("📊 加载预处理统计数据...")
    statistics_data = read_previous_data_optimized(data_path)
    print(f"✅ 统计数据加载完成: {statistics_data.shape[0]} 行数据")
    
    rolling: Dict[str, Dict[str, List]] = {}
    
    # 打印启动信息
    print_startup_info(api_url, data_path, save_path)
    
    # 检查启动时的时间状态 - 传入测试模式参数
    status, wait_seconds, next_session, message = get_time_status_and_sleep(test_mode)
    if status == 'exit' and not test_mode:  # 测试模式下不退出
        hours, minutes = format_time_duration(wait_seconds)[:2]
        print(f"\n📢 当前为收盘后时间，程序将等待明日开盘")
        print(f"💤 预计等待时间: {hours}小时{minutes}分钟")
        print(f"⏰ 将在 {(datetime.now() + timedelta(seconds=wait_seconds)).strftime('%Y-%m-%d %H:%M:%S')} 开始运行")
        print(f"🔄 程序现在进入睡眠模式...")
        # 实际进入睡眠等待
        handle_sleep(wait_seconds, next_session)

    try:
        while True:
            # 检查当前时间状态 - 传入测试模式参数
            status, wait_seconds, next_session, message = get_time_status_and_sleep(test_mode)
            print(message)
            
            if status == 'exit' and not test_mode:  # 测试模式下不退出
                _print_exit_message(save_path)
                break
                
            elif status == 'wait' and not test_mode:  # 测试模式下不等待
                handle_sleep(wait_seconds, next_session)
                continue
            
            # 等待到分钟开始
            wait_for_minute_start()
            
            # 获取当前标准交易时间
            current_time_str = datetime.now().strftime('%H:%M:00')
            
            # 验证交易时间 (测试模式下跳过验证)
            if not test_mode and not is_trading_time(current_time_str):
                print(f"⚠️ 当前时间 {current_time_str} 不在交易时间映射范围内，等待30秒后重新检查...")
                time.sleep(30)
                continue
                
            print(f"\n--- 正在获取数据 (交易时间: {current_time_str}, 索引: {time_to_trading_index(current_time_str) if not test_mode else 'TEST'}) ---")
            
            # 获取数据（在线或测试模式）
            fetched_data = fetch_minute_data(api_url)
            if fetched_data:
                # 处理数据
                start_time = _process_market_data(
                    fetched_data, current_time_str, rolling, 
                    start_time, statistics_data, save_path, index_weight_data
                )
                
                print(f"⏰ 等待下一分钟...")
                
                # 测试模式下，只运行一次就退出
                if test_mode:
                    print("🧪 测试模式：已完成一次数据处理，程序退出")
                    break
        
    except KeyboardInterrupt:
        print(f"\n🛑 接收到停止信号，程序正在安全退出...")
        print(f"📊 最后处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"👋 程序已安全停止")
        
    except Exception as e:
        print(f"\n❌ 程序发生未预期的错误: {e}")
        print(f"📊 错误发生时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔧 请检查网络连接、数据源或配置文件")
        raise




if __name__ == "__main__":
    import sys
    # 检查命令行参数中是否有test_mode
    test_mode = "--test" in sys.argv or "--test-mode" in sys.argv
    main(test_mode=test_mode)



