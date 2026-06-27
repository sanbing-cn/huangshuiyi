"""
主程序入口
整合爬虫、数据处理、分析和存储的完整流程
"""

import sys
import os
import pandas as pd
import glob
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_processing.preprocessor import DataPreprocessor
from analysis.stock_analyzer import StockAnalyzer
from database.db_manager import DatabaseManager


class StockAnalysisPipeline:
    """股票数据分析流水线"""
    
    def __init__(self, use_oilmonkey=True):
        """
        初始化流水线
        
        Args:
            use_oilmonkey: True=使用油猴导出的JSON数据, False=使用Python爬虫
        """
        self.use_oilmonkey = use_oilmonkey
        
        if not use_oilmonkey:
            # 仅在不使用油猴时导入爬虫（需要恢复归档文件）
            try:
                from spider.stock_spider import StockSpider
                self.spider = StockSpider(request_delay=(8, 15), max_retries=3)
            except ImportError:
                print("警告：爬虫模块已归档，将自动使用油猴数据模式")
                self.use_oilmonkey = True
        
        self.preprocessor = DataPreprocessor()
        self.analyzer = None  # Spark分析器延迟初始化
        self.db_manager = DatabaseManager()
        
    def run(self, stock_codes=None, days=30):
        """
        运行完整的分析流程
        
        Args:
            stock_codes: 股票代码列表，None则自动获取
            days: 获取的历史数据天数
        """
        print("\n" + "#"*80)
        print("# 股票大数据分析系统")
        print("# 开始时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("#"*80 + "\n")
        
        try:
            # 第1步：初始化数据库
            print("\n【第1步】初始化数据库...")
            self._init_database()

            
            # 第2步：数据采集
            print("\n【第2步】采集股票数据...")
            raw_data = self._collect_data(stock_codes, days)
            
            if raw_data.empty:
                print("警告：未采集到数据，程序退出")
                return
            
            # 第3步：数据预处理
            print("\n【第3步】数据预处理...")
            processed_data, quality_report = self._preprocess_data(raw_data)
            
            if processed_data.empty:
                print("警告：预处理后数据为空，程序退出")
                return
            
            # 第4步：Spark数据分析
            print("\n【第4步】Spark数据分析...")
            analyzed_data = self._analyze_data(processed_data)
            
            if analyzed_data is None or analyzed_data.empty:
                print("警告：分析结果为空，程序退出")
                return
            
            # 第5步：保存结果到数据库
            print("\n【第5步】保存分析结果到数据库...")
            try:
                self._save_to_database(analyzed_data)
            except Exception as e:
                print(f"\n警告：数据保存失败，但不影响分析结果展示")
                print(f"错误详情: {str(e)}")
                print("您可以稍后修复数据库问题，分析结果已在内存中")
            
            # 第6步：生成报告
            print("\n【第6步】生成分析报告...")
            self._generate_report(quality_report, analyzed_data)
            
            print("\n" + "#"*80)
            print("# 分析流程完成!")
            print("# 结束时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print("#"*80 + "\n")
            
        except Exception as e:
            print(f"\n程序执行出错: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            # 清理资源
            self._cleanup()
    
    def _init_database(self):
        """初始化数据库"""
        # 创建数据库（如果不存在）
        self.db_manager.create_database()
        
        # 连接数据库
        if not self.db_manager.connect():
            raise Exception("数据库连接失败")
        
        # 创建数据表
        if not self.db_manager.create_table():
            raise Exception("数据表创建失败")
        
        print("数据库初始化完成")
    
    def _collect_data(self, stock_codes, days):
        """
        采集数据
        
        Args:
            stock_codes: 股票代码列表（油猴模式下忽略）
            days: 天数（油猴模式下忽略）
            
        Returns:
            原始数据DataFrame
        """
        if self.use_oilmonkey:
            print("使用油猴导出的JSON数据...")
            return self._load_oilmonkey_data()
        else:
            print("开始从东方财富网爬取数据...")
            raw_data = self.spider.fetch_all_stocks(stock_codes, days)
            
            if raw_data.empty:
                print("警告：未获取到数据")
                return pd.DataFrame()
            
            print(f"数据采集完成，共获取 {len(raw_data)} 条记录")
            return raw_data
    
    def _load_oilmonkey_data(self):
        """
        加载油猴导出的JSON数据
        
        Returns:
            DataFrame包含所有股票数据
        """
        # 查找最新的stock_data_*.json文件
        json_files = glob.glob("stock_data_*.json")
        
        if not json_files:
            print("❌ 未找到 stock_data_*.json 文件")
            print("\n请先使用油猴插件导出数据：")
            print("1. 访问 https://www.eastmoney.com/")
            print("2. 使用油猴插件抓取数据")
            print("3. 点击'💾 导出JSON'按钮")
            print("4. 将JSON文件移动到项目根目录")
            return pd.DataFrame()
        
        # 按修改时间排序，获取最新文件
        latest_file = max(json_files, key=os.path.getmtime)
        print(f"[✓] 找到文件: {latest_file}")
        
        try:
            # 加载JSON数据
            df = pd.read_json(latest_file, encoding='utf-8')
            print(f"[✓] 加载了 {len(df)} 条记录")
            
            # 数据清洗和转换
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
            
            # 转换数值字段
            numeric_columns = ['开盘', '收盘', '最高', '最低', '成交量', '成交额', '涨跌幅']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 去重
            df.drop_duplicates(inplace=True)
            
            # 排序
            if '日期' in df.columns and '股票代码' in df.columns:
                df.sort_values(by=['股票代码', '日期'], inplace=True)
            
            print(f"[✓] 数据清洗完成，有效记录: {len(df)} 条")
            
            return df
            
        except Exception as e:
            print(f"❌ 加载JSON文件失败: {e}")
            return pd.DataFrame()
    
    def _preprocess_data(self, raw_data):
        """
        预处理数据
        
        Args:
            raw_data: 原始数据
            
        Returns:
            (处理后的数据, 质量报告)
        """
        processed_data, quality_report = self.preprocessor.preprocess(raw_data)
        
        print(f"数据预处理完成，处理后数据量: {len(processed_data)}")
        return processed_data, quality_report
    
    def _analyze_data(self, processed_data):
        """
        使用Spark分析数据
        
        Args:
            processed_data: 处理后的Pandas DataFrame
            
        Returns:
            分析后的Pandas DataFrame
        """
        # 初始化Spark分析器
        self.analyzer = StockAnalyzer(app_name="StockTrendAnalysis")
        
        # 转换为Spark DataFrame
        spark_df = self.analyzer.create_dataframe(processed_data)
        
        # 执行综合分析
        analyzed_spark_df = self.analyzer.comprehensive_analysis(spark_df)
        
        # 转换回Pandas DataFrame以便保存到MySQL
        analyzed_pdf = analyzed_spark_df.toPandas()
        
        print(f"Spark分析完成，分析结果包含 {len(analyzed_pdf)} 条记录")
        
        return analyzed_pdf
    
    def _save_to_database(self, analyzed_data):
        """
        保存分析结果到数据库
        
        Args:
            analyzed_data: 分析后的数据
        """
        # 检查数据库连接状态
        if not self.db_manager.engine:
            print("警告：数据库连接已断开，尝试重新连接...")
            if not self.db_manager.connect():
                raise Exception("数据库重新连接失败")
        
        # 显示即将保存的数据信息
        print(f"\n准备保存数据:")
        print(f"  - 记录数: {len(analyzed_data)}")
        print(f"  - 列名: {list(analyzed_data.columns)}")
        print(f"  - 数据类型:\n{analyzed_data.dtypes}")
        print(f"  - 前3行数据:\n{analyzed_data.head(3)}")
        
        success = self.db_manager.save_data(analyzed_data, if_exists='replace')
        
        if success:
            # 显示表信息
            self.db_manager.get_table_info()
            
            # 查询示例数据
            sample_sql = f"SELECT * FROM `{self.db_manager.config['database']}`.`{self.db_manager.TABLE_NAME}` ORDER BY 日期 DESC LIMIT 5"
            sample_data = self.db_manager.query_data(sample_sql)
            
            if not sample_data.empty:
                print("\n最新5条数据示例:")
                print(sample_data)
        else:
            raise Exception("数据保存失败 - 请查看上方的详细错误信息")
    
    def _generate_report(self, quality_report, analyzed_data):
        """
        生成分析报告
        
        Args:
            quality_report: 数据质量报告
            analyzed_data: 分析后的数据
        """
        print("\n" + "="*80)
        print("数据分析报告")
        print("="*80)
        
        print(f"\n1. 数据概况:")
        print(f"   - 总记录数: {len(analyzed_data)}")
        print(f"   - 股票数量: {analyzed_data['股票代码'].nunique()}")
        print(f"   - 日期范围: {analyzed_data['日期'].min()} 至 {analyzed_data['日期'].max()}")
        
        print(f"\n2. 数据质量:")
        print(f"   - 缺失值统计: {quality_report.get('缺失值统计', {})}")
        print(f"   - 重复记录: {quality_report.get('重复记录数', 0)}")
        
        print(f"\n3. 价格统计:")
        if '收盘价' in analyzed_data.columns:
            print(f"   - 平均收盘价: {analyzed_data['收盘价'].mean():.2f}")
            print(f"   - 最高收盘价: {analyzed_data['收盘价'].max():.2f}")
            print(f"   - 最低收盘价: {analyzed_data['收盘价'].min():.2f}")
        
        if '涨跌幅' in analyzed_data.columns:
            print(f"\n4. 涨跌情况:")
            print(f"   - 平均涨跌幅: {analyzed_data['涨跌幅'].mean():.2f}%")
            print(f"   - 最大单日涨幅: {analyzed_data['涨跌幅'].max():.2f}%")
            print(f"   - 最大单日跌幅: {analyzed_data['涨跌幅'].min():.2f}%")
        
        print("\n" + "="*80)
    
    def _cleanup(self):
        """清理资源"""
        # 停止Spark会话
        if self.analyzer:
            self.analyzer.stop()
        
        # 关闭数据库连接
        self.db_manager.disconnect()
        
        print("资源清理完成")


def main():
    """主函数"""
    # 创建分析流水线
    pipeline = StockAnalysisPipeline()
    
    # 方式1：指定股票代码
    # stock_codes = ['000001', '000002', '600000', '600036', '000858']
    # pipeline.run(stock_codes=stock_codes, days=60)
    
    # 方式2：自动获取股票列表（需要手动实现爬虫）
    pipeline.run(stock_codes=None, days=30)


if __name__ == '__main__':
    main()
