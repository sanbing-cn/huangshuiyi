"""
数据库配置模块
MySQL数据库连接配置
"""

# ==================== MySQL数据库配置 ====================
DB_CONFIG = {
    'host': 'localhost',      # MySQL服务器地址
    'port': 3306,             # MySQL端口号
    'user': 'root',           # 数据库用户名
    'password': '321321',     # 数据库密码
    'database': '股票',        # 数据库名称
    'charset': 'utf8'         # 字符集编码
}

# MySQL连接字符串（用于SQLAlchemy ORM）
DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"

# ==================== 数据表配置 ====================
TABLE_NAME = '股票走势分析'  # 股票走势分析表名
