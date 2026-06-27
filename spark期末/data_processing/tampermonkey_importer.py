"""
油猴插件数据导入工具
用于处理Tampermonkey爬虫导出的JSON数据，并导入到数据库
"""

import json
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import glob


class TampermonkeyDataImporter:
    """油猴插件数据导入器"""
    
    def __init__(self, db_manager=None):
        """
        初始化导入器
        
        Args:
            db_manager: 数据库管理器实例（可选）
        """
        self.db_manager = db_manager
    
    def load_json_file(self, file_path: str) -> pd.DataFrame:
        """
        从JSON文件加载数据
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            DataFrame格式的股票数据
        """
        try:
            print(f"正在读取文件: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                print("警告: 文件为空")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            
            # 数据清洗和转换
            df = self._clean_data(df)
            
            print(f"成功加载 {len(df)} 条数据")
            return df
            
        except Exception as e:
            print(f"读取文件失败: {e}")
            return pd.DataFrame()
    
    def load_multiple_files(self, directory: str, pattern: str = "*.json") -> pd.DataFrame:
        """
        从目录加载多个JSON文件
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式
            
        Returns:
            合并后的DataFrame
        """
        all_files = glob.glob(os.path.join(directory, pattern))
        
        if not all_files:
            print(f"在 {directory} 中未找到匹配的文件")
            return pd.DataFrame()
        
        print(f"找到 {len(all_files)} 个文件")
        
        all_data = []
        for file_path in all_files:
            df = self.load_json_file(file_path)
            if not df.empty:
                all_data.append(df)
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            print(f"合并后共 {len(combined_df)} 条数据")
            return combined_df
        else:
            return pd.DataFrame()
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗和转换数据
        
        Args:
            df: 原始DataFrame
            
        Returns:
            清洗后的DataFrame
        """
        # 转换日期字段
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
        
        # 转换数值字段
        numeric_columns = ['开盘价', '收盘价', '最高价', '最低价', 
                          '成交量', '成交额', '涨跌幅', '换手率']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 删除无效行
        df = df.dropna(subset=['日期', '股票代码'])
        
        # 删除重复数据
        df = df.drop_duplicates(subset=['日期', '股票代码'], keep='last')
        
        # 按日期和股票代码排序
        df = df.sort_values(['股票代码', '日期']).reset_index(drop=True)
        
        return df
    
    def save_to_csv(self, df: pd.DataFrame, output_path: str):
        """
        保存为CSV文件
        
        Args:
            df: DataFrame
            output_path: 输出文件路径
        """
        try:
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"数据已保存到: {output_path}")
        except Exception as e:
            print(f"保存CSV失败: {e}")
    
    def save_to_excel(self, df: pd.DataFrame, output_path: str):
        """
        保存为Excel文件
        
        Args:
            df: DataFrame
            output_path: 输出文件路径
        """
        try:
            df.to_excel(output_path, index=False, engine='openpyxl')
            print(f"数据已保存到: {output_path}")
        except Exception as e:
            print(f"保存Excel失败: {e}")
    
    def save_to_database(self, df: pd.DataFrame):
        """
        保存到数据库
        
        Args:
            df: DataFrame
        """
        if self.db_manager is None:
            print("错误: 未配置数据库管理器")
            return
        
        try:
            print(f"正在导入 {len(df)} 条数据到数据库...")
            self.db_manager.save_stock_data(df)
            print("数据导入成功")
        except Exception as e:
            print(f"数据库导入失败: {e}")
    
    def get_statistics(self, df: pd.DataFrame) -> Dict:
        """
        获取数据统计信息
        
        Args:
            df: DataFrame
            
        Returns:
            统计信息字典
        """
        if df.empty:
            return {}
        
        stats = {
            '总记录数': len(df),
            '股票数量': df['股票代码'].nunique(),
            '日期范围': {
                '最早': df['日期'].min().strftime('%Y-%m-%d'),
                '最晚': df['日期'].max().strftime('%Y-%m-%d')
            },
            '数据完整性': {
                '完整记录': int(df.notna().all(axis=1).sum()),
                '缺失值总数': int(df.isna().sum().sum())
            }
        }
        
        # 按股票统计
        stock_stats = df.groupby('股票代码').agg({
            '日期': 'count',
            '收盘价': ['mean', 'min', 'max']
        }).round(2)
        
        stats['股票详情'] = stock_stats.to_dict('index')
        
        return stats
    
    def merge_with_existing(self, new_df: pd.DataFrame, existing_df: pd.DataFrame) -> pd.DataFrame:
        """
        合并新数据和已有数据，去重
        
        Args:
            new_df: 新数据
            existing_df: 已有数据
            
        Returns:
            合并后的DataFrame
        """
        if existing_df.empty:
            return new_df
        
        if new_df.empty:
            return existing_df
        
        # 合并数据
        merged = pd.concat([existing_df, new_df], ignore_index=True)
        
        # 去重（保留最新的）
        merged = merged.drop_duplicates(
            subset=['日期', '股票代码'], 
            keep='last'
        )
        
        # 重新排序
        merged = merged.sort_values(['股票代码', '日期']).reset_index(drop=True)
        
        print(f"合并完成: {len(existing_df)} + {len(new_df)} -> {len(merged)} (去重后)")
        
        return merged


def quick_import(json_file_path: str, output_format: str = 'csv'):
    """
    快速导入函数 - 一键式操作
    
    Args:
        json_file_path: JSON文件路径
        output_format: 输出格式 ('csv', 'excel', 'database')
    """
    importer = TampermonkeyDataImporter()
    
    # 加载数据
    df = importer.load_json_file(json_file_path)
    
    if df.empty:
        print("没有数据可导入")
        return
    
    # 显示统计信息
    stats = importer.get_statistics(df)
    print("\n数据统计:")
    print(f"  总记录数: {stats.get('总记录数', 0)}")
    print(f"  股票数量: {stats.get('股票数量', 0)}")
    if '日期范围' in stats:
        print(f"  日期范围: {stats['日期范围']['最早']} ~ {stats['日期范围']['最晚']}")
    print()
    
    # 根据格式保存
    base_name = os.path.splitext(json_file_path)[0]
    
    if output_format == 'csv':
        output_path = f"{base_name}.csv"
        importer.save_to_csv(df, output_path)
    
    elif output_format == 'excel':
        output_path = f"{base_name}.xlsx"
        importer.save_to_excel(df, output_path)
    
    elif output_format == 'database':
        # 需要配置数据库管理器
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        importer.db_manager = db
        importer.save_to_database(df)
    
    else:
        print(f"不支持的输出格式: {output_format}")


if __name__ == '__main__':
    # 示例用法
    print("="*60)
    print("油猴插件数据导入工具")
    print("="*60)
    
    # 查找最近的JSON文件
    json_files = glob.glob("stock_data_*.json")
    
    if json_files:
        latest_file = max(json_files, key=os.path.getctime)
        print(f"\n找到最新文件: {latest_file}\n")
        
        # 快速导入为CSV
        quick_import(latest_file, output_format='csv')
        
        # 也可以导入为Excel
        # quick_import(latest_file, output_format='excel')
        
        # 或者导入到数据库
        # quick_import(latest_file, output_format='database')
    else:
        print("未找到JSON文件，请先使用油猴插件导出数据")
        print("\n使用方法:")
        print("  1. 在东方财富网页面使用油猴插件抓取数据")
        print("  2. 点击'导出JSON'按钮")
        print("  3. 将下载的JSON文件放到当前目录")
        print("  4. 运行此脚本自动导入")
