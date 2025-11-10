"""
MinIO股票数据客户端 - 多Schema支持版本
"""
import os
import pandas as pd
import io
from datetime import datetime
from typing import List, Optional, Union
import logging
from minio import Minio
from minio.error import S3Error

from .config import get_config, MinIOConfig
from .schemas import schema_manager, get_supported_data_types, is_data_type_supported
from .adj_utils import apply_adjustment_factor

logger = logging.getLogger(__name__)

class MinIOStockDataClient:
    """
    MinIO股票数据客户端 - 多数据类型支持
    自动从环境变量读取配置，支持完整的数据管理功能
    """
    
    def __init__(self, config: Optional[MinIOConfig] = None, bucket_type: str = 'data', **kwargs):
        """
        初始化MinIO客户端
        
        Args:
            config: MinIO配置对象，None则从环境变量读取
            bucket_type: bucket类型 ('data', 'result', 'backup', 'temp')
            **kwargs: 可选的配置覆盖参数
        """
        try:
            # 获取配置（这里会进行验证）
            self.config = config or get_config()
        except ValueError as e:
            logger.error(f"配置验证失败: {e}")
            raise  # 重新抛出配置错误，不要尝试连接MinIO
        
        # 应用kwargs覆盖
        endpoint = kwargs.get('endpoint', self.config.endpoint)
        access_key = kwargs.get('access_key', self.config.access_key)
        secret_key = kwargs.get('secret_key', self.config.secret_key)
        secure = kwargs.get('secure', self.config.secure)
        
        # 再次验证关键参数
        if not access_key or not secret_key:
            raise ValueError("MinIO访问密钥和秘密密钥不能为空")
        
        # 初始化MinIO客户端
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        # 设置bucket名称 - 支持多种方式
        if 'bucket_name' in kwargs:
            # 直接指定bucket名称
            self.bucket_name = kwargs['bucket_name']
        else:
            # 根据bucket类型选择
            self.bucket_name = self.config.get_bucket(bucket_type)
        
        logger.info(f"初始化MinIO客户端: {endpoint} (secure={secure}), bucket: {self.bucket_name}")
        
        # 确保bucket存在
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """确保数据桶存在"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"创建数据桶: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"桶操作失败: {e}")
            raise
    
    def get_data(self, 
                 data_type: str = "CNSTOCK",
                 start_date: str = "20200101",
                 end_date: str = "20250101", 
                 symbols: Union[str, List[str]] = "all",
                 fq_type: str = "qfq") -> pd.DataFrame:
        """
        从MinIO获取指定类型的数据
        
        Args:
            data_type: 数据类型，支持CNSTOCK, CNSTOCK_ADJ, CNSTOCK_BASIC, CNINDEX, CNSTOCK_MONEYFLOW等
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            symbols: 股票代码，"all"表示所有标的
            fq_type: 复权类型，仅对股票数据有效，默认 'qfq'。 'qfq'(前复权)/'hfq'(后复权)/'bfq'(不复权)。
            
        Returns:
            pd.DataFrame: 数据
        """
        start_time = datetime.now()
        
        # 验证数据类型
        if not is_data_type_supported(data_type):
            raise ValueError(f"不支持的数据类型: {data_type}，支持的类型: {get_supported_data_types()}")
        
        try:
            # 处理复权逻辑 - 模仿 CNStockDailyProvider
            if data_type == "CNSTOCK" and fq_type in ['qfq', 'hfq']:
                return self._get_adjusted_stock_data(start_date, end_date, symbols, fq_type)
            elif data_type == "CNSTOCK" and fq_type == 'bfq':
                # 不复权，直接获取原始数据
                return self._fetch_raw_data("CNSTOCK", start_date, end_date, symbols)
            elif data_type == "CNSTOCK_ADJ":
                # 如果直接请求ADJ数据，返回调整因子数据
                return self._fetch_raw_data("CNSTOCK_ADJ", start_date, end_date, symbols)
            else:
                # 其他数据类型直接获取
                return self._fetch_raw_data(data_type, start_date, end_date, symbols)
            
        except Exception as e:
            logger.error(f"{data_type}数据获取失败: {str(e)}")
            raise
    
    def _get_adjusted_stock_data(self, start_date: str, end_date: str, 
                                symbols: Union[str, List[str]], fq_type: str) -> pd.DataFrame:
        """
        获取复权股票数据 - 模仿 CNStockDailyProvider 的逻辑
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 股票代码
            fq_type: 复权类型 'qfq' 或 'hfq'
        
        Returns:
            复权后的股票数据
        """
        logger.info(f"获取{fq_type}复权数据，时间范围: {start_date} 到 {end_date}")
        
        # 1. 获取原始不复权数据
        df_bfq = self._fetch_raw_data("CNSTOCK", start_date, end_date, symbols)
        if df_bfq is None or df_bfq.empty:
            logger.warning("未找到原始股票数据")
            return df_bfq
        
        # 2. 获取调整因子数据
        df_adj = self._fetch_raw_data("CNSTOCK_ADJ", start_date, end_date, symbols)
        if df_adj is None or df_adj.empty:
            logger.error(f'调整因子数据缺失，标的: {symbols}')
            return df_bfq  # 返回原始数据
        
        # 3. 应用调整因子
        try:
            adjusted_df = apply_adjustment_factor(df_bfq, df_adj, fq_type)
            logger.info(f"成功应用{fq_type}调整因子，数据量: {len(adjusted_df):,}行")
            return adjusted_df
        except Exception as e:
            logger.error(f"应用调整因子失败: {e}")
            return df_bfq  # 返回原始数据
    
    def _fetch_raw_data(self, data_type: str, start_date: str, end_date: str, 
                       symbols: Union[str, List[str]]) -> pd.DataFrame:
        """
        获取原始数据（不进行复权处理）
        
        Args:
            data_type: 数据类型
            start_date: 开始日期
            end_date: 结束日期
            symbols: 标的代码
        
        Returns:
            原始数据
        """
        # 1. 查找匹配的数据文件
        data_files = self._find_data_files(data_type, start_date, end_date, symbols)
        
        if not data_files:
            logger.warning(f"未找到匹配的{data_type}数据文件")
            return pd.DataFrame()
        
        # 2. 下载并合并数据
        df_list = []
        for file_path in data_files:
            df_chunk = self._download_and_read_file(file_path)
            if df_chunk is not None and not df_chunk.empty:
                df_list.append(df_chunk)
        
        if not df_list:
            return pd.DataFrame()
        
        # 3. 合并数据
        df = pd.concat(df_list, ignore_index=True)
        
        # 4. 过滤数据
        df = self._filter_data(df, data_type, start_date, end_date, symbols)
        
        return df
    
    def _find_data_files(self, data_type: str, start_date: str, end_date: str, symbols) -> List[str]:
        """
        查找匹配的数据文件
        
        Args:
            data_type: 数据类型
            start_date: 开始日期
            end_date: 结束日期  
            symbols: 标的代码
        
        Returns:
            匹配的文件路径列表
        """
        try:
            start_dt = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
        except:
            raise ValueError("日期格式错误，请使用YYYYMMDD")
        
        data_files = []
        
        # 获取数据类型对应的路径前缀
        prefix = schema_manager.get_path_prefix(data_type) + "/"
        
        try:
            # 获取所有可用文件
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            
            available_files = []
            for obj in objects:
                if obj.object_name.endswith('.parquet'):
                    available_files.append(obj.object_name)
            
            # 按月查找文件
            current_date = start_dt.replace(day=1)  # 月初
            while current_date <= end_dt:
                year = current_date.year
                month = current_date.month
                
                # 查找匹配的月份文件
                monthly_file = f"{prefix}year={year}/month={month}/consolidated.parquet"
                if monthly_file in available_files:
                    data_files.append(monthly_file)
                    logger.debug(f"找到{data_type}文件: {monthly_file}")
                
                # 移动到下个月
                if month == 12:
                    current_date = current_date.replace(year=year+1, month=1)
                else:
                    current_date = current_date.replace(month=month+1)
            
            logger.info(f"找到{len(data_files)}个{data_type}数据文件")
            return data_files
            
        except S3Error as e:
            logger.error(f"查找{data_type}数据文件失败: {e}")
            return []
    
    def _download_and_read_file(self, object_name: str) -> pd.DataFrame:
        """下载并读取parquet文件"""
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            
            df = pd.read_parquet(io.BytesIO(data))
            logger.debug(f"下载文件: {object_name}, 数据量: {len(df):,}行")
            
            return df
            
        except Exception as e:
            logger.error(f"下载文件失败 {object_name}: {e}")
            return pd.DataFrame()
    
    def _filter_data(self, df: pd.DataFrame, data_type: str, start_date: str, end_date: str, symbols) -> pd.DataFrame:
        """过滤数据"""
        if df.empty:
            return df
        
        # 获取数据类型对应的列名
        date_column = schema_manager.get_date_column(data_type)
        symbol_column = schema_manager.get_symbol_column(data_type)
        
        # 日期过滤
        start_dt = pd.to_datetime(start_date, format='%Y%m%d')
        end_dt = pd.to_datetime(end_date, format='%Y%m%d')
        
        if date_column in df.columns:
            df = df.copy()  # 避免 SettingWithCopyWarning
            df[date_column] = pd.to_datetime(df[date_column])
            df = df[(df[date_column] >= start_dt) & (df[date_column] <= end_dt)]
        
        # 标的代码过滤
        if symbols != "all" and isinstance(symbols, (str, list)) and symbol_column in df.columns:
            if isinstance(symbols, str):
                symbols = [symbols]
            df = df[df[symbol_column].isin(symbols)]
        
        # 排序
        if not df.empty:
            sort_columns = [symbol_column, date_column] if symbol_column in df.columns and date_column in df.columns else []
            if sort_columns:
                df = df.sort_values(sort_columns)
        
        return df
    
    def list_available_data(self, data_type: Optional[str] = None) -> dict:
        """
        列出可用的数据文件
        
        Args:
            data_type: 指定数据类型，None则列出所有类型
        """
        try:
            result = {
                'data_types': [],
                'date_ranges': {},
                'file_count': 0,
                'supported_types': get_supported_data_types()
            }
            
            # 如果指定了数据类型，只查找该类型
            if data_type:
                if not is_data_type_supported(data_type):
                    raise ValueError(f"不支持的数据类型: {data_type}")
                search_types = [data_type]
            else:
                search_types = get_supported_data_types()
            
            for dtype in search_types:
                prefix = schema_manager.get_path_prefix(dtype) + "/"
                objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
                
                type_file_count = 0
                for obj in objects:
                    if obj.object_name.endswith('.parquet'):
                        result['file_count'] += 1
                        type_file_count += 1
                        
                        if dtype not in result['data_types']:
                            result['data_types'].append(dtype)
                        
                        # 解析年月信息
                        if 'year=' in obj.object_name and 'month=' in obj.object_name:
                            if dtype not in result['date_ranges']:
                                result['date_ranges'][dtype] = {'years': [], 'months': []}
                            
                            parts = obj.object_name.split('/')
                            for part in parts:
                                if part.startswith('year='):
                                    year = int(part.split('=')[1])
                                    if year not in result['date_ranges'][dtype]['years']:
                                        result['date_ranges'][dtype]['years'].append(year)
                                elif part.startswith('month='):
                                    month = int(part.split('=')[1])
                                    if month not in result['date_ranges'][dtype]['months']:
                                        result['date_ranges'][dtype]['months'].append(month)
                
                if type_file_count > 0:
                    logger.info(f"{dtype}: 找到{type_file_count}个文件")
            
            # 排序
            result['data_types'].sort()
            for data_type in result['date_ranges']:
                result['date_ranges'][data_type]['years'].sort()
                result['date_ranges'][data_type]['months'].sort()
            
            return result
            
        except S3Error as e:
            logger.error(f"列出数据失败: {e}")
            return {}
    
    def get_supported_data_types(self) -> List[str]:
        """获取支持的数据类型列表"""
        return get_supported_data_types()
    
    def get_data_type_info(self, data_type: str) -> dict:
        """获取数据类型的详细信息"""
        if not is_data_type_supported(data_type):
            raise ValueError(f"不支持的数据类型: {data_type}")
        
        config = schema_manager.get_config(data_type)
        return {
            'data_type': data_type,
            'description': config.get('description', ''),
            'date_column': config.get('date_column', 'trade_date'),
            'symbol_column': config.get('symbol_column', 'ts_code'),
            'path': schema_manager.get_path_prefix(data_type),
            'schema_fields': list(config.get('schema', {}).keys())
        }
    
    # 兼容性方法 - 保持向后兼容
    def get_stock_data_fast(self, 
                           start_date: str = "20200101",
                           end_date: str = "20250101", 
                           symbols: Union[str, List[str]] = "all",
                           fq_type: str = "qfq") -> pd.DataFrame:
        """
        从MinIO快速获取股票数据 (兼容性方法)
        
        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            symbols: 股票代码，"all"表示所有股票
            fq_type: 复权类型 qfq/hfq/bfq
            
        Returns:
            pd.DataFrame: 股票数据
        """
        return self.get_data(
            data_type="CNSTOCK",
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            fq_type=fq_type
        )
    
    def test_connection(self) -> bool:
        """测试MinIO连接"""
        try:
            # 尝试列出桶
            self.client.bucket_exists(self.bucket_name)
            logger.info("MinIO连接测试成功")
            return True
        except Exception as e:
            logger.error(f"MinIO连接测试失败: {e}")
            return False
    
    def get_bucket_info(self) -> dict:
        """获取桶信息"""
        try:
            objects = list(self.client.list_objects(self.bucket_name, recursive=True))
            total_size = sum(obj.size for obj in objects)
            
            return {
                'bucket_name': self.bucket_name,
                'object_count': len(objects),
                'total_size_mb': total_size / (1024 * 1024),
                'endpoint': self.config.endpoint,
                'supported_data_types': get_supported_data_types()
            }
        except Exception as e:
            logger.error(f"获取桶信息失败: {e}")
            return {}

# 便捷函数
def get_stock_data_from_minio(start_date: str = "20200101", 
                             end_date: str = "20250101",
                             symbols: Union[str, List[str]] = "all",
                             fq_type: str = "qfq",
                             config: Optional[MinIOConfig] = None) -> pd.DataFrame:
    """
    从MinIO获取股票数据的便捷函数 (兼容性函数)
    
    Args:
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        symbols: 股票代码
        fq_type: 复权类型
        config: MinIO配置，None则从环境变量读取
        
    Returns:
        pd.DataFrame: 股票数据
    """
    client = MinIOStockDataClient(config=config)
    return client.get_stock_data_fast(
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        fq_type=fq_type
    )

def get_data_from_minio(data_type: str,
                       start_date: str = "20200101",
                       end_date: str = "20250101", 
                       symbols: Union[str, List[str]] = "all",
                       fq_type: str = "bfq",
                       config: Optional[MinIOConfig] = None) -> pd.DataFrame:
    """
    从MinIO获取指定类型数据的便捷函数
    
    Args:
        data_type: 数据类型
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        symbols: 标的代码
        fq_type: 复权类型（仅对股票数据有效）
        config: MinIO配置，None则从环境变量读取
        
    Returns:
        pd.DataFrame: 数据
    """
    client = MinIOStockDataClient(config=config)
    return client.get_data(
        data_type=data_type,
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        fq_type=fq_type
    )