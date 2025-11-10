"""
便捷函数 - 多数据类型支持
"""
import pandas as pd
from typing import Union, List, Optional
from .client import MinIOStockDataClient, get_data_from_minio
from .config import MinIOConfig
from .schemas import get_supported_data_types, is_data_type_supported, schema_manager

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

def get_cnstock_data(start_date: str = "20200101",
                    end_date: str = "20250101", 
                    symbols: Union[str, List[str]] = "all",
                    fq_type: str = "qfq",
                    config: Optional[MinIOConfig] = None) -> pd.DataFrame:
    """获取中国股票基础数据"""
    return get_data_from_minio("CNSTOCK", start_date, end_date, symbols, fq_type, config)

def get_cnstock_adj_factor_data(start_date: str = "20200101",
                        end_date: str = "20250101", 
                        symbols: Union[str, List[str]] = "all",
                        fq_type: str = "qfq",
                        config: Optional[MinIOConfig] = None) -> pd.DataFrame:
    """获取中国股票adj_factor数据"""
    return get_data_from_minio("CNSTOCK_ADJ", start_date, end_date, symbols, fq_type, config)

def get_cnstock_basic_data(start_date: str = "20200101",
                          end_date: str = "20250101", 
                          symbols: Union[str, List[str]] = "all",
                          config: Optional[MinIOConfig] = None) -> pd.DataFrame:
    """获取中国股票基础信息数据"""
    return get_data_from_minio("CNSTOCK_BASIC", start_date, end_date, symbols, config=config)

def get_cnindex_data(start_date: str = "20200101",
                    end_date: str = "20250101", 
                    symbols: Union[str, List[str]] = "all",
                    config: Optional[MinIOConfig] = None) -> pd.DataFrame:
    """获取中国指数数据"""
    return get_data_from_minio("CNINDEX", start_date, end_date, symbols, config=config)

def get_cnstock_moneyflow_data(start_date: str = "20200101",
                              end_date: str = "20250101", 
                              symbols: Union[str, List[str]] = "all",
                              config: Optional[MinIOConfig] = None) -> pd.DataFrame:
    """获取中国股票资金流向数据"""
    return get_data_from_minio("CNSTOCK_MONEYFLOW", start_date, end_date, symbols, config=config)

def list_supported_data_types() -> List[str]:
    """列出所有支持的数据类型"""
    return get_supported_data_types()

def get_data_type_info(data_type: str) -> dict:
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

def test_minio_connection(config: Optional[MinIOConfig] = None) -> bool:
    """
    测试MinIO连接
    
    Args:
        config: MinIO配置，None则从环境变量读取
        
    Returns:
        bool: 连接是否成功
    """
    try:
        client = MinIOStockDataClient(config=config)
        return client.test_connection()
    except Exception:
        return False

def get_available_data_summary(config: Optional[MinIOConfig] = None) -> dict:
    """
    获取可用数据的概览信息
    
    Args:
        config: MinIO配置
        
    Returns:
        dict: 数据概览信息
    """
    try:
        client = MinIOStockDataClient(config=config)
        return client.list_available_data()
    except Exception as e:
        return {"error": str(e)}