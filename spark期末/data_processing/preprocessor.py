"""
数据预处理模块
负责数据清洗、转换和质量校验
"""

import pandas as pd
import numpy as np
from typing import Tuple


class DataPreprocessor:
    """数据预处理器"""
    
    def __init__(self):
        pass
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗原始数据
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            清洗后的DataFrame
        """
        print(f"清洗前数据量: {len(df)}")
        
        # 1. 删除完全重复的行
        df = df.drop_duplicates()
        print(f"删除重复行后: {len(df)}")
        
        # 2. 处理缺失值
        df = self.handle_missing_values(df)
        
        # 3. 处理异常值
        df = self.handle_outliers(df)
        
        # 4. 数据类型转换
        df = self.convert_data_types(df)
        
        # 5. 删除无效数据
        df = self.remove_invalid_data(df)
        
        print(f"清洗后数据量: {len(df)}")
        
        return df.reset_index(drop=True)
    
    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理缺失值
        
        Args:
            df: 数据DataFrame
            
        Returns:
            处理缺失值后的DataFrame
        """
        # 检查缺失值
        missing_count = df.isnull().sum()
        if missing_count.sum() > 0:
            print("发现缺失值:")
            print(missing_count[missing_count > 0])
            
            # 对于数值列，用中位数填充
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if df[col].isnull().sum() > 0:
                    median_val = df[col].median()
                    df[col].fillna(median_val, inplace=True)
            
            # 对于日期列，删除含有缺失值的行
            if '日期' in df.columns:
                df = df.dropna(subset=['日期'])
        
        return df
    
    def handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理异常值（使用IQR方法）
        
        Args:
            df: 数据DataFrame
            
        Returns:
            处理异常值后的DataFrame
        """
        numeric_cols = ['开盘价', '收盘价', '最高价', '最低价', '成交量', '成交额']
        
        for col in numeric_cols:
            if col in df.columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - 3 * IQR
                upper_bound = Q3 + 3 * IQR
                
                # 标记异常值但不删除，而是修正为边界值
                df[col] = df[col].clip(lower=lower_bound, upper=upper_bound)
        
        return df
    
    def convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换数据类型
        
        Args:
            df: 数据DataFrame
            
        Returns:
            转换类型后的DataFrame
        """
        # 确保日期列为datetime类型
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'])
        
        # 确保数值列为float或int类型
        numeric_cols = ['开盘价', '收盘价', '最高价', '最低价', '成交量', '成交额']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def remove_invalid_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        删除无效数据
        
        Args:
            df: 数据DataFrame
            
        Returns:
            删除无效数据后的DataFrame
        """
        # 删除价格为负数或零的记录
        price_cols = ['开盘价', '收盘价', '最高价', '最低价']
        for col in price_cols:
            if col in df.columns:
                df = df[df[col] > 0]
        
        # 删除成交量为负数的记录
        if '成交量' in df.columns:
            df = df[df['成交量'] >= 0]
        
        # 确保最高价 >= 最低价
        if '最高价' in df.columns and '最低价' in df.columns:
            df = df[df['最高价'] >= df['最低价']]
        
        return df
    
    def add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        添加特征列
        
        Args:
            df: 数据DataFrame
            
        Returns:
            添加特征后的DataFrame
        """
        df = df.copy()
        
        # 1. 基础特征
        # 计算涨跌幅
        if '收盘价' in df.columns:
            df['涨跌幅'] = df.groupby('股票代码')['收盘价'].pct_change() * 100
        
        # 计算价格波动范围
        if '最高价' in df.columns and '最低价' in df.columns:
            df['价格波动'] = df['最高价'] - df['最低价']
        
        # 计算振幅
        if '收盘价' in df.columns and '价格波动' in df.columns:
            df['振幅'] = (df['价格波动'] / df['收盘价']) * 100
        
        # 添加时间特征
        if '日期' in df.columns:
            df['星期'] = df['日期'].dt.dayofweek
            df['月份'] = df['日期'].dt.month
            df['年份'] = df['日期'].dt.year
        
        # 2. 技术指标
        # 计算移动平均线
        if '收盘价' in df.columns:
            df['MA5'] = df.groupby('股票代码')['收盘价'].transform(
                lambda x: x.rolling(window=5, min_periods=1).mean()
            )
            df['MA10'] = df.groupby('股票代码')['收盘价'].transform(
                lambda x: x.rolling(window=10, min_periods=1).mean()
            )
            df['MA20'] = df.groupby('股票代码')['收盘价'].transform(
                lambda x: x.rolling(window=20, min_periods=1).mean()
            )
        
        # 计算成交量均线
        if '成交量' in df.columns:
            df['VOL_MA5'] = df.groupby('股票代码')['成交量'].transform(
                lambda x: x.rolling(window=5, min_periods=1).mean()
            )
            # 强制转换为浮点数，处理所有异常情况
            df['VOL_MA5'] = pd.to_numeric(df['VOL_MA5'], errors='coerce')
            # 填充NaN为0（滚动计算的初期会有NaN）
            df['VOL_MA5'] = df['VOL_MA5'].fillna(0)
            # 转换为整数类型（使用float避免Int64的严格检查）
            df['VOL_MA5'] = df['VOL_MA5'].astype(float).round(0).astype('Int64')
        
        # 计算动量指标（5日价格变化率）
        if '收盘价' in df.columns:
            df['Momentum_5'] = df.groupby('股票代码')['收盘价'].transform(
                lambda x: x.pct_change(periods=5, fill_method=None) * 100
            )
        
        return df
    
    def validate_data_quality(self, df: pd.DataFrame) -> dict:
        """
        验证数据质量
        
        Args:
            df: 数据DataFrame
            
        Returns:
            数据质量报告字典
        """
        report = {
            '总记录数': len(df),
            '缺失值统计': df.isnull().sum().to_dict(),
            '重复记录数': df.duplicated().sum(),
            '数据类型': df.dtypes.to_dict(),
            '数值统计': {}
        }
        
        # 添加数值列的统计信息
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            report['数值统计'][col] = {
                '均值': df[col].mean(),
                '标准差': df[col].std(),
                '最小值': df[col].min(),
                '最大值': df[col].max()
            }
        
        return report
    
    def preprocess(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
        """
        完整的预处理流程
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            (预处理后的DataFrame, 数据质量报告)
        """
        print("="*50)
        print("开始数据预处理...")
        print("="*50)
        
        # 1. 数据清洗
        df_cleaned = self.clean_data(df)
        
        # 2. 特征工程
        df_featured = self.add_features(df_cleaned)
        
        # 3. 数据质量验证
        quality_report = self.validate_data_quality(df_featured)
        
        print("="*50)
        print("数据预处理完成!")
        print("="*50)
        
        return df_featured, quality_report


if __name__ == '__main__':
    # 测试数据预处理
    import random
    
    # 创建示例数据
    data = {
        '日期': pd.date_range('2024-01-01', periods=100),
        '开盘价': [random.uniform(10, 100) for _ in range(100)],
        '收盘价': [random.uniform(10, 100) for _ in range(100)],
        '最高价': [random.uniform(10, 100) for _ in range(100)],
        '最低价': [random.uniform(10, 100) for _ in range(100)],
        '成交量': [random.randint(100000, 10000000) for _ in range(100)],
        '成交额': [random.uniform(1000000, 100000000) for _ in range(100)],
        '股票代码': '000001'
    }
    
    df = pd.DataFrame(data)
    
    # 添加一些缺失值和异常值用于测试
    df.loc[5, '收盘价'] = None
    df.loc[10, '开盘价'] = -100  # 异常值
    
    preprocessor = DataPreprocessor()
    df_processed, report = preprocessor.preprocess(df)
    
    print("\n数据质量报告:")
    for key, value in report.items():
        print(f"{key}: {value}")
