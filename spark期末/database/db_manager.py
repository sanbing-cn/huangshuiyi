"""
数据库管理模块
负责MySQL数据库的连接、表创建和数据存储
"""

import pymysql
from sqlalchemy import create_engine
import pandas as pd
from typing import List, Dict
from config import DB_CONFIG, DATABASE_URL, TABLE_NAME


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.config = DB_CONFIG
        self.engine = None
        self.connection = None
        self.TABLE_NAME = TABLE_NAME  # 添加表名属性
    
    def connect(self):
        """建立数据库连接"""
        try:
            # 使用pymysql建立连接
            self.connection = pymysql.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset=DB_CONFIG['charset']
            )
            
            # 创建SQLAlchemy引擎
            self.engine = create_engine(DATABASE_URL)
            
            print("MySQL数据库连接成功")
            return True
            
        except Exception as e:
            print(f"数据库连接失败: {str(e)}")
            print("\n请检查:")
            print("1. MySQL服务是否启动")
            print("2. 用户名密码是否正确 (用户: a, 密码: 321321)")
            print("3. 数据库 '股票' 是否存在")
            print("4. 端口3306是否开放")
            return False
    
    def disconnect(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            print("数据库连接已关闭")
    
    def create_database(self):
        """
        创建数据库（如果不存在）
        """
        try:
            # 先连接到MySQL服务器（不指定数据库）
            conn = pymysql.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                charset='utf8'
            )
            
            cursor = conn.cursor()
            
            # 检查数据库是否存在
            cursor.execute(f"SHOW DATABASES LIKE '{DB_CONFIG['database']}'")
            result = cursor.fetchone()
            
            if not result:
                # 创建数据库
                cursor.execute(f"CREATE DATABASE `{DB_CONFIG['database']}` CHARACTER SET utf8 COLLATE utf8_general_ci")
                print(f"数据库 '{DB_CONFIG['database']}' 创建成功")
            else:
                print(f"数据库 '{DB_CONFIG['database']}' 已存在")
            
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"创建数据库失败: {str(e)}")
            return False
    
    def create_table(self):
        """
        创建股票走势分析表
        
        表结构包含：
        - id: 主键，自增
        - 日期: 交易日期
        - 股票代码: 股票代码
        - 开盘价、收盘价、最高价、最低价: 价格数据
        - 成交量、成交额: 交易数据
        - 涨跌幅: 价格变化
        - 技术指标: MA5, MA10, MA20等
        - 其他分析指标
        """
        if not self.connection:
            print("请先连接数据库")
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # 删除已存在的表（可选，谨慎使用）
            # cursor.execute(f"DROP TABLE IF EXISTS `{TABLE_NAME}`")
            
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
                `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                `日期` DATE NOT NULL COMMENT '交易日期',
                `股票代码` VARCHAR(10) NOT NULL COMMENT '股票代码',
                `股票名称` VARCHAR(50) COMMENT '股票名称',
                `开盘价` DECIMAL(10, 2) COMMENT '开盘价格',
                `收盘价` DECIMAL(10, 2) COMMENT '收盘价格',
                `最高价` DECIMAL(10, 2) COMMENT '最高价格',
                `最低价` DECIMAL(10, 2) COMMENT '最低价格',
                `成交量` BIGINT COMMENT '成交量',
                `成交额` DECIMAL(15, 2) COMMENT '成交额',
                `涨跌幅` DECIMAL(10, 4) COMMENT '涨跌幅百分比',
                `MA5` DECIMAL(10, 2) COMMENT '5日移动平均线',
                `MA10` DECIMAL(10, 2) COMMENT '10日移动平均线',
                `MA20` DECIMAL(10, 2) COMMENT '20日移动平均线',
                `VOL_MA5` BIGINT COMMENT '5日成交量平均',
                `Momentum_5` DECIMAL(10, 4) COMMENT '5日价格动量',
                `价格波动` DECIMAL(10, 2) COMMENT '价格波动范围',
                `振幅` DECIMAL(10, 4) COMMENT '振幅百分比',
                `星期` TINYINT COMMENT '星期几(0-6)',
                `月份` TINYINT COMMENT '月份',
                `年份` SMALLINT COMMENT '年份',
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                INDEX `idx_date` (`日期`),
                INDEX `idx_stock_code` (`股票代码`),
                INDEX `idx_stock_name` (`股票名称`),
                UNIQUE KEY `uk_date_stock` (`日期`, `股票代码`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='股票走势分析表';
            """
            
            cursor.execute(create_table_sql)
            self.connection.commit()
            
            print(f"数据表 '{TABLE_NAME}' 创建成功")
            cursor.close()
            
            return True
            
        except Exception as e:
            print(f"创建数据表失败: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def save_data(self, df: pd.DataFrame, if_exists='replace') -> bool:
        """
        将DataFrame保存到数据库
        
        Args:
            df: Pandas DataFrame
            if_exists: 如果表已存在的处理方式 ('fail', 'replace', 'append')
            
        Returns:
            是否保存成功
        """
        if not self.engine:
            print("请先连接数据库")
            return False
        
        try:
            if df.empty:
                print("数据为空，无需保存")
                return False
            
            print(f"正在保存 {len(df)} 条数据到数据库...")
            
            # 使用pandas的to_sql方法
            df.to_sql(
                name=TABLE_NAME,
                con=self.engine,
                if_exists=if_exists,
                index=False,
                chunksize=1000,  # 分批插入，每批1000条
                method='multi'   # 使用多行插入提高效率
            )
            
            print(f"数据保存成功！共 {len(df)} 条记录")
            return True
            
        except Exception as e:
            print(f"保存数据失败: {str(e)}")
            print("\n可能的原因:")
            print("1. 数据库连接已断开")
            print("2. 表结构不匹配（列名或数据类型）")
            print("3. DataFrame中包含NULL值但数据库字段不允许")
            print("4. MySQL服务未启动")
            print("\n详细错误信息:", str(e))
            return False
    
    def query_data(self, sql: str) -> pd.DataFrame:
        """
        查询数据
        
        Args:
            sql: SQL查询语句
            
        Returns:
            查询结果的DataFrame
        """
        if not self.engine:
            print("请先连接数据库")
            return pd.DataFrame()
        
        try:
            df = pd.read_sql(sql, self.engine)
            print(f"查询成功，返回 {len(df)} 条记录")
            return df
            
        except Exception as e:
            print(f"查询失败: {str(e)}")
            return pd.DataFrame()
    
    def get_table_info(self) -> Dict:
        """
        获取表的基本信息
        
        Returns:
            表信息字典
        """
        if not self.connection:
            print("请先连接数据库")
            return {}
        
        try:
            cursor = self.connection.cursor()
            
            # 获取记录数
            cursor.execute(f"SELECT COUNT(*) FROM `{TABLE_NAME}`")
            record_count = cursor.fetchone()[0]
            
            # 获取表结构
            cursor.execute(f"DESCRIBE `{TABLE_NAME}`")
            columns = cursor.fetchall()
            
            info = {
                '表名': TABLE_NAME,
                '记录数': record_count,
                '字段数': len(columns),
                '字段列表': [col[0] for col in columns]
            }
            
            cursor.close()
            
            print(f"表信息:")
            print(f"  表名: {info['表名']}")
            print(f"  记录数: {info['记录数']}")
            print(f"  字段数: {info['字段数']}")
            
            return info
            
        except Exception as e:
            print(f"获取表信息失败: {str(e)}")
            return {}
    
    def clear_table(self):
        """
        清空表数据（谨慎使用）
        """
        if not self.connection:
            print("请先连接数据库")
            return False
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"TRUNCATE TABLE `{TABLE_NAME}`")
            self.connection.commit()
            cursor.close()
            
            print(f"表 '{TABLE_NAME}' 已清空")
            return True
            
        except Exception as e:
            print(f"清空表失败: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()


if __name__ == '__main__':
    # 测试数据库管理
    db_manager = DatabaseManager()
    
    # 1. 创建数据库
    db_manager.create_database()
    
    # 2. 连接数据库
    if db_manager.connect():
        # 3. 创建表
        db_manager.create_table()
        
        # 4. 获取表信息
        db_manager.get_table_info()
        
        # 5. 测试保存数据
        test_data = {
            '日期': pd.date_range('2024-01-01', periods=5),
            '股票代码': ['000001'] * 5,
            '股票名称': ['平安银行'] * 5,
            '开盘价': [10.5, 10.6, 10.7, 10.8, 10.9],
            '收盘价': [10.6, 10.7, 10.8, 10.9, 11.0],
            '最高价': [10.8, 10.9, 11.0, 11.1, 11.2],
            '最低价': [10.4, 10.5, 10.6, 10.7, 10.8],
            '成交量': [1000000, 1100000, 1200000, 1300000, 1400000],
            '成交额': [10600000, 11770000, 12960000, 14170000, 15400000],
            '涨跌幅': [1.0, 0.94, 0.93, 0.92, 0.91],
            '换手率': [0.5, 0.52, 0.54, 0.56, 0.58],
            'MA5': [None, None, None, None, 10.8],
            'MA10': [None] * 5,
            'MA20': [None] * 5,
            'VOL_MA5': [None] * 5,
            'Momentum_5': [None] * 5,
            '价格波动': [0.4, 0.4, 0.4, 0.4, 0.4],
            '振幅': [3.77, 3.70, 3.64, 3.57, 3.51],
            '星期': [0, 1, 2, 3, 4],
            '月份': [1, 1, 1, 1, 1],
            '年份': [2024, 2024, 2024, 2024, 2024]
        }
        
        test_df = pd.DataFrame(test_data)
        db_manager.save_data(test_df)
        
        # 6. 查询数据
        result_df = db_manager.query_data(f"SELECT * FROM `{TABLE_NAME}` LIMIT 10")
        print("\n查询结果:")
        print(result_df)
        
        # 7. 断开连接
        db_manager.disconnect()
