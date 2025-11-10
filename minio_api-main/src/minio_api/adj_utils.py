import pandas as pd

def apply_adjustment_factor(df: pd.DataFrame, df_adj: pd.DataFrame, fq_type: str) -> pd.DataFrame:
    """
    应用复权调整因子到日线数据
    
    Args:
        df: 原始日线数据
        df_adj: 调整因子数据
        fq_type: 复权类型 'qfq' 或 'hfq'
    
    Returns:
        调整后的数据
    """
    if 'trade_date' not in df.columns or 'trade_date' not in df_adj.columns:
        raise ValueError("数据中缺少trade_date列")

    df = df.copy()
    df_adj = df_adj.copy()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df_adj['trade_date'] = pd.to_datetime(df_adj['trade_date'])
    df_sorted = df.sort_values('trade_date')
    df_adj_sorted = df_adj.sort_values('trade_date')
    
    # 使用 merge_asof 匹配调整因子
    merged = pd.merge_asof(
        df_sorted,
        df_adj_sorted[['ts_code', 'trade_date', 'adj_factor']],
        on='trade_date',
        by='ts_code',
        direction='backward'
    )
    
    # 根据复权类型选择基准值
    if fq_type == 'qfq':  # 前复权：使用最后一个调整因子作为基准
        base_values = (
            df_adj_sorted.groupby('ts_code', as_index=False)['adj_factor']
            .last()
            .rename(columns={'adj_factor': 'base_value'})
        )
    else:  # hfq 后复权：使用第一个调整因子作为基准
        base_values = (
            df_adj_sorted.groupby('ts_code', as_index=False)['adj_factor']
            .first()
            .rename(columns={'adj_factor': 'base_value'})
        )
    
    # 计算调整比例并应用
    merged = pd.merge(merged, base_values, on='ts_code', how='left')
    merged['factor'] = merged['adj_factor'] / merged['base_value']
    
    # 应用调整因子到价格列
    for col in ['open', 'high', 'low', 'close', 'pre_close']:
        if col in merged.columns:
            merged[col] = merged[col] * merged['factor']
    
    # 成交量需要反向调整
    if 'vol' in merged.columns:
        merged['vol'] = merged['vol'] / merged['factor']
    
    # 清理临时列
    merged = merged.drop(['adj_factor', 'base_value', 'factor'], axis=1, errors='ignore')
    
    return merged