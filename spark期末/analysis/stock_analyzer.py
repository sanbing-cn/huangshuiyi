"""
Spark数据分析模块
使用PySpark进行股票数据分析和趋势预测
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.window import Window
import pandas as pd
import numpy as np
from typing import Dict, List


class StockAnalyzer:
    """股票数据分析器"""
    
    def __init__(self, app_name="StockAnalysis"):
        """
        初始化Spark会话
        
        Args:
            app_name: Spark应用名称
        """
        import os
        import sys
        
        # 设置Python路径（使用当前运行的Python解释器）
        python_path = sys.executable
        print(f"检测到Python路径: {python_path}")
        
        # 验证Python路径是否存在且可执行
        if not os.path.exists(python_path):
            print(f"警告: Python路径不存在: {python_path}")
            print("尝试使用系统默认Python...")
            python_path = 'python'
        elif 'Start Menu' in python_path or ' ' in python_path:
            # 如果路径包含空格，尝试使用系统PATH中的python
            print(f"警告: Python路径包含空格，可能导致问题: {python_path}")
            print("尝试使用系统默认Python...")
            python_path = 'python'
        
        print(f"最终使用Python: {python_path}")
        os.environ['PYSPARK_PYTHON'] = python_path
        os.environ['PYSPARK_DRIVER_PYTHON'] = python_path
        
        self.spark = SparkSession.builder \
            .appName(app_name) \
            .master("local[*]") \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
            .config("spark.python.worker.timeout", "600") \
            .getOrCreate()
        
        self.spark.sparkContext.setLogLevel("ERROR")  # 只显示错误，隐藏警告
        print("Spark会话已创建")
    
    def create_dataframe(self, pdf: pd.DataFrame):
        """
        将Pandas DataFrame转换为Spark DataFrame
        
        Args:
            pdf: Pandas DataFrame
            
        Returns:
            Spark DataFrame
        """
        return self.spark.createDataFrame(pdf)
    
    def basic_statistics(self, df):
        """
        基础统计分析
        
        Args:
            df: Spark DataFrame
            
        Returns:
            统计结果字典
        """
        print("\n" + "="*50)
        print("基础统计分析")
        print("="*50)
        
        # 总体统计
        total_records = df.count()
        stock_count = df.select("股票代码").distinct().count()
        date_range = df.agg(min("日期"), max("日期")).collect()[0]
        
        stats = {
            '总记录数': total_records,
            '股票数量': stock_count,
            '起始日期': str(date_range[0]),
            '结束日期': str(date_range[1])
        }
        
        print(f"总记录数: {total_records}")
        print(f"股票数量: {stock_count}")
        print(f"日期范围: {date_range[0]} 至 {date_range[1]}")
        
        # 价格统计
        price_stats = df.select(
            avg("收盘价").alias("平均收盘价"),
            max("收盘价").alias("最高收盘价"),
            min("收盘价").alias("最低收盘价"),
            stddev("收盘价").alias("收盘价标准差")
        ).collect()[0]
        
        stats['价格统计'] = {
            '平均收盘价': float(price_stats['平均收盘价']),
            '最高收盘价': float(price_stats['最高收盘价']),
            '最低收盘价': float(price_stats['最低收盘价']),
            '收盘价标准差': float(price_stats['收盘价标准差'])
        }
        
        print(f"\n价格统计:")
        for key, value in stats['价格统计'].items():
            print(f"  {key}: {value:.2f}")
        
        return stats
    
    def trend_analysis(self, df):
        """
        趋势分析 - 计算移动平均线和技术指标
        
        Args:
            df: Spark DataFrame
            
        Returns:
            包含趋势分析的DataFrame
        """
        print("\n" + "="*50)
        print("趋势分析")
        print("="*50)
        
        # 定义窗口：按股票代码分区，按日期排序
        window_spec = Window.partitionBy("股票代码").orderBy("日期")
        
        # 计算移动平均线
        df_trend = df.withColumn("MA5", avg("收盘价").over(window_spec.rowsBetween(-4, 0))) \
                     .withColumn("MA10", avg("收盘价").over(window_spec.rowsBetween(-9, 0))) \
                     .withColumn("MA20", avg("收盘价").over(window_spec.rowsBetween(-19, 0)))
        
        # 计算成交量移动平均
        df_trend = df_trend.withColumn("VOL_MA5", avg("成交量").over(window_spec.rowsBetween(-4, 0)))
        
        # 计算价格动量（当前价格与N日前价格的比率）
        df_trend = df_trend.withColumn("Momentum_5", 
                                       col("收盘价") / lag("收盘价", 5).over(window_spec))
        
        print("移动平均线计算完成: MA5, MA10, MA20")
        print("成交量移动平均计算完成: VOL_MA5")
        print("价格动量计算完成: Momentum_5")
        
        return df_trend
    
    def volatility_analysis(self, df):
        """
        波动性分析
        
        Args:
            df: Spark DataFrame
            
        Returns:
            波动性分析结果
        """
        print("\n" + "="*50)
        print("波动性分析")
        print("="*50)
        
        # 计算每日收益率
        window_spec = Window.partitionBy("股票代码").orderBy("日期")
        df_return = df.withColumn("Daily_Return", 
                                  (col("收盘价") - lag("收盘价", 1).over(window_spec)) / 
                                  lag("收盘价", 1).over(window_spec))
        
        # 按股票分组计算波动性指标
        volatility_stats = df_return.groupBy("股票代码").agg(
            avg("Daily_Return").alias("平均日收益率"),
            stddev("Daily_Return").alias("收益率标准差"),
            min("Daily_Return").alias("最大单日跌幅"),
            max("Daily_Return").alias("最大单日涨幅"),
            count("Daily_Return").alias("交易天数")
        )
        
        # 计算年化波动率
        volatility_stats = volatility_stats.withColumn(
            "年化波动率", 
            col("收益率标准差") * sqrt(lit(252))
        )
        
        result = volatility_stats.collect()
        
        print(f"分析了 {len(result)} 只股票的波动性")
        for row in result[:5]:  # 显示前5只股票
            print(f"\n股票 {row['股票代码']}:")
            print(f"  平均日收益率: {float(row['平均日收益率'])*100:.2f}%")
            print(f"  年化波动率: {float(row['年化波动率'])*100:.2f}%")
        
        return volatility_stats
    
    def volume_price_analysis(self, df):
        """
        量价关系分析
        
        Args:
            df: Spark DataFrame
            
        Returns:
            量价分析结果
        """
        print("\n" + "="*50)
        print("量价关系分析")
        print("="*50)
        
        # 计算量价相关系数
        correlation = df.select(corr("收盘价", "成交量")).collect()[0][0]
        
        print(f"收盘价与成交量的相关系数: {correlation:.4f}")
        
        if correlation > 0.5:
            print("解读: 强正相关 - 价格上涨伴随成交量放大")
        elif correlation > 0:
            print("解读: 弱正相关 - 价格与成交量呈正向关系")
        elif correlation > -0.5:
            print("解读: 弱负相关 - 价格与成交量呈反向关系")
        else:
            print("解读: 强负相关 - 价格上涨伴随成交量萎缩")
        
        # 按成交量分组分析价格走势
        # 注意：ntile需要全局排序，这里使用空分区（所有数据在一个分区）
        df_quantile = df.withColumn("Vol_Quantile", 
                                    ntile(4).over(Window.orderBy("成交量")))
        
        vol_price_analysis = df_quantile.groupBy("Vol_Quantile").agg(
            avg("收盘价").alias("平均价格"),
            avg("涨跌幅").alias("平均涨跌幅")
        ).orderBy("Vol_Quantile")
        
        print("\n不同成交量区间的平均表现:")
        for row in vol_price_analysis.collect():
            quantile_labels = ['低成交量', '中低成交量', '中高成交量', '高成交量']
            label = quantile_labels[int(row['Vol_Quantile'])-1]
            print(f"  {label}: 平均价格={float(row['平均价格']):.2f}, "
                  f"平均涨跌幅={float(row['平均涨跌幅']):.2f}%")
        
        return {'相关系数': correlation, '量价分析': vol_price_analysis}
    
    def stock_ranking(self, df):
        """
        股票排名分析
        
        Args:
            df: Spark DataFrame
            
        Returns:
            排名结果
        """
        print("\n" + "="*50)
        print("股票排名分析")
        print("="*50)
        
        # 计算每只股票的综合表现
        performance = df.groupBy("股票代码").agg(
            avg("涨跌幅").alias("平均涨跌幅"),
            sum("成交量").alias("总成交量"),
            avg("成交额").alias("平均成交额"),
            stddev("收盘价").alias("价格波动率"),
            count("*").alias("交易天数")
        )
        
        # 按不同指标排名
        # 注意：排名是全局操作，不需要分区
        window_rank = Window.orderBy(col("平均涨跌幅").desc())
        
        ranked_df = performance.withColumn("涨跌幅排名", rank().over(window_rank))
        
        # 显示前10名
        top_performers = ranked_df.orderBy("涨跌幅排名").limit(10).collect()
        
        print("\n涨跌幅排名前10的股票:")
        for i, row in enumerate(top_performers, 1):
            print(f"{i}. 股票 {row['股票代码']}: 平均涨跌幅={float(row['平均涨跌幅']):.2f}%")
        
        return ranked_df
    
    def comprehensive_analysis(self, df):
        """
        综合分析 - 执行所有分析并整合结果
        
        Args:
            df: Spark DataFrame
            
        Returns:
            综合分析结果DataFrame
        """
        print("\n" + "#"*50)
        print("# 开始综合数据分析")
        print("#"*50)
        
        # 1. 基础统计
        basic_stats = self.basic_statistics(df)
        
        # 2. 趋势分析
        df_trend = self.trend_analysis(df)
        
        # 3. 波动性分析
        volatility_stats = self.volatility_analysis(df)
        
        # 4. 量价关系分析
        vol_price_result = self.volume_price_analysis(df)
        
        # 5. 股票排名
        ranking_result = self.stock_ranking(df)
        
        print("\n" + "#"*50)
        print("# 综合分析完成")
        print("#"*50)
        
        # 返回趋势分析后的DataFrame（包含所有技术指标）
        return df_trend
    
    def stop(self):
        """停止Spark会话"""
        if self.spark:
            self.spark.stop()
            print("Spark会话已停止")


if __name__ == '__main__':
    # 测试Spark分析
    import pandas as pd
    import random
    
    # 创建示例数据
    data = []
    for stock_code in ['000001', '000002', '600000']:
        for i in range(100):
            data.append({
                '日期': pd.Timestamp('2024-01-01') + pd.Timedelta(days=i),
                '开盘价': random.uniform(10, 100),
                '收盘价': random.uniform(10, 100),
                '最高价': random.uniform(10, 100),
                '最低价': random.uniform(10, 100),
                '成交量': random.randint(100000, 10000000),
                '成交额': random.uniform(1000000, 100000000),
                '股票代码': stock_code,
                '涨跌幅': random.uniform(-5, 5)
            })
    
    pdf = pd.DataFrame(data)
    
    analyzer = StockAnalyzer()
    
    try:
        sdf = analyzer.create_dataframe(pdf)
        result_df = analyzer.comprehensive_analysis(sdf)
        result_df.show(10)
    finally:
        analyzer.stop()
