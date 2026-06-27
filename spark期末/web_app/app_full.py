"""
完整的Web应用 - 包含管理者端和用户端
"""

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import pandas as pd
import sys
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from config import DB_CONFIG, TABLE_NAME
import pymysql

app = Flask(__name__)
app.secret_key = 'stock_analysis_secret_key_2024'  # 会话密钥
db_manager = DatabaseManager()


def get_db_connection():
    """获取数据库连接"""
    if not db_manager.engine:
        db_manager.connect()
    return db_manager


def init_user_table():
    """初始化用户数据表"""
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset']
        )
        cursor = conn.cursor()
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS `用户数据` (
            `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
            `用户名` VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名（唯一）',
            `密码` VARCHAR(255) NOT NULL COMMENT '加密密码',
            `邮箱` VARCHAR(100) COMMENT '邮箱',
            `注册时间` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
            `最后登录` TIMESTAMP NULL COMMENT '最后登录时间',
            INDEX `idx_username` (`用户名`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='用户数据表';
        """
        
        cursor.execute(create_table_sql)
        conn.commit()
        cursor.close()
        conn.close()
        
        print("用户数据表初始化成功")
        return True
        
    except Exception as e:
        print(f"用户数据表初始化失败: {str(e)}")
        return False


def init_admin_login_log_table():
    """初始化管理端登录日志表"""
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset']
        )
        cursor = conn.cursor()
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS `管理端登录日志` (
            `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
            `用户名` VARCHAR(50) NOT NULL COMMENT '登录用户名',
            `登录时间` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
            `登录IP` VARCHAR(50) COMMENT '登录IP地址',
            `登录状态` VARCHAR(20) NOT NULL COMMENT '登录状态（成功/失败）',
            `失败原因` VARCHAR(100) COMMENT '失败原因',
            INDEX `idx_login_time` (`登录时间`),
            INDEX `idx_username` (`用户名`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='管理端登录日志表';
        """
        
        cursor.execute(create_table_sql)
        conn.commit()
        cursor.close()
        conn.close()
        
        print("管理端登录日志表初始化成功")
        return True
        
    except Exception as e:
        print(f"管理端登录日志表初始化失败: {str(e)}")
        return False


# ==================== 公共路由 ====================

@app.route('/')
def index():
    """首页 - 选择登录类型"""
    return render_template('home.html')


# ==================== 用户端路由 ====================

@app.route('/user/login')
def user_login_page():
    """用户登录页面"""
    return render_template('user_login.html')


@app.route('/user/register')
def user_register_page():
    """用户注册页面"""
    return render_template('user_register.html')


@app.route('/user/dashboard')
def user_dashboard():
    """用户仪表板"""
    if 'user_id' not in session:
        return redirect(url_for('user_login_page'))
    return render_template('user_dashboard.html', username=session.get('username'))


@app.route('/user/profile')
def user_profile():
    """用户个人资料页面"""
    if 'user_id' not in session:
        return redirect(url_for('user_login_page'))
    return render_template('user_profile.html', username=session.get('username'))


@app.route('/api/user/login', methods=['POST'])
def user_login():
    """用户登录API"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': '请输入用户名和密码'})
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        sql = "SELECT * FROM `用户数据` WHERE `用户名` = %s"
        cursor.execute(sql, (username,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['密码'], password):
            # 更新最后登录时间
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()
            update_sql = "UPDATE `用户数据` SET `最后登录` = NOW() WHERE `用户名` = %s"
            cursor.execute(update_sql, (username,))
            conn.commit()
            cursor.close()
            conn.close()
            
            session['user_id'] = user['id']
            session['username'] = user['用户名']
            session['user_type'] = 'user'
            
            return jsonify({'success': True, 'message': '登录成功'})
        else:
            return jsonify({'success': False, 'error': '用户名或密码错误'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/register', methods=['POST'])
def user_register():
    """用户注册API"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        email = data.get('email', '')
        
        if not username or not password:
            return jsonify({'success': False, 'error': '用户名和密码不能为空'})
        
        # 检查用户名是否已存在
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        check_sql = "SELECT COUNT(*) FROM `用户数据` WHERE `用户名` = %s"
        cursor.execute(check_sql, (username,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': '用户名已存在'})
        
        # 插入新用户
        hashed_password = generate_password_hash(password)
        insert_sql = "INSERT INTO `用户数据` (`用户名`, `密码`, `邮箱`) VALUES (%s, %s, %s)"
        cursor.execute(insert_sql, (username, hashed_password, email))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '注册成功'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/profile')
def get_user_profile():
    """获取用户个人资料"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': '未登录'})
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        sql = "SELECT `id`, `用户名`, `邮箱`, `注册时间`, `最后登录` FROM `用户数据` WHERE `id` = %s"
        cursor.execute(sql, (session['user_id'],))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user:
            # 处理datetime对象
            for key in ['注册时间', '最后登录']:
                if user[key] and hasattr(user[key], 'strftime'):
                    user[key] = user[key].strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({
                'success': True,
                'data': {
                    'id': user['id'],
                    'username': user['用户名'],
                    'email': user['邮箱'],
                    'register_time': user['注册时间'],
                    'last_login': user['最后登录']
                }
            })
        else:
            return jsonify({'success': False, 'error': '用户不存在'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/profile', methods=['PUT'])
def update_user_profile():
    """更新用户个人资料"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': '未登录'})
        
        data = request.json
        email = data.get('email', '')
        phone = data.get('phone', '')
        
        if not email:
            return jsonify({'success': False, 'error': '邮箱不能为空'})
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 检查手机字段是否存在，不存在则添加
        try:
            cursor.execute("ALTER TABLE `用户数据` ADD COLUMN `手机` VARCHAR(20) COMMENT '手机号码'")
            conn.commit()
        except:
            pass  # 字段已存在
        
        update_sql = "UPDATE `用户数据` SET `邮箱` = %s, `手机` = %s WHERE `id` = %s"
        cursor.execute(update_sql, (email, phone, session['user_id']))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '资料更新成功'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/password', methods=['PUT'])
def change_user_password():
    """修改用户密码"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': '未登录'})
        
        data = request.json
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        if not old_password or not new_password:
            return jsonify({'success': False, 'error': '请填写完整'})
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取当前用户信息
        sql = "SELECT `密码` FROM `用户数据` WHERE `id` = %s"
        cursor.execute(sql, (session['user_id'],))
        user = cursor.fetchone()
        
        if not user or not check_password_hash(user['密码'], old_password):
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': '当前密码错误'})
        
        # 更新密码
        hashed_password = generate_password_hash(new_password)
        update_sql = "UPDATE `用户数据` SET `密码` = %s WHERE `id` = %s"
        cursor.execute(update_sql, (hashed_password, session['user_id']))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '密码修改成功'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/stats')
def get_user_stats():
    """获取用户统计数据"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': '未登录'})
        
        safe_username = session['username'].replace('-', '_').replace(' ', '_')
        table_name = f"用户_{safe_username}_搜索记录"
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 检查搜索记录表是否存在
        check_table_sql = """
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
        """
        cursor.execute(check_table_sql, (DB_CONFIG['database'], table_name))
        table_exists = cursor.fetchone()['count'] > 0
        
        search_count = 0
        favorite_count = 0
        
        if table_exists:
            # 获取搜索次数
            cursor.execute(f"SELECT COUNT(*) as count FROM `{table_name}`")
            search_count = cursor.fetchone()['count']
            
            # 获取关注的股票数（搜索超过3次的）
            cursor.execute(f"""
            SELECT COUNT(DISTINCT `股票代码`) as count 
            FROM `{table_name}` 
            GROUP BY `股票代码` 
            HAVING COUNT(*) >= 3
            """)
            favorite_count = len(cursor.fetchall())
        
        # 计算会员天数
        cursor.execute("SELECT `注册时间` FROM `用户数据` WHERE `id` = %s", (session['user_id'],))
        user = cursor.fetchone()
        member_days = 0
        if user and user['注册时间']:
            delta = datetime.now() - user['注册时间']
            member_days = delta.days
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'search_count': search_count,
                'favorite_count': favorite_count,
                'member_days': member_days
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/search_history', methods=['POST'])
def save_search_history():
    """保存用户搜索历史到独立数据表"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': '未登录'})
        
        data = request.json
        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name', '')
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 为当前用户创建独立的搜索数据表（如果不存在）
        safe_username = session['username'].replace('-', '_').replace(' ', '_')
        table_name = f"用户_{safe_username}_搜索记录"
        
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
            `股票代码` VARCHAR(10) NOT NULL COMMENT '股票代码',
            `股票名称` VARCHAR(50) COMMENT '股票名称',
            `搜索时间` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '搜索时间',
            INDEX `idx_time` (`搜索时间`),
            INDEX `idx_code` (`股票代码`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='用户{session["username"]}的搜索记录表';
        """
        cursor.execute(create_table_sql)
        
        # 插入搜索记录
        insert_sql = f"INSERT INTO `{table_name}` (`股票代码`, `股票名称`) VALUES (%s, %s)"
        cursor.execute(insert_sql, (stock_code, stock_name))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/history')
def get_search_history():
    """获取用户搜索历史（从用户独立数据表）"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': '未登录'})
        
        # 构建用户专属表名
        safe_username = session['username'].replace('-', '_').replace(' ', '_')
        table_name = f"用户_{safe_username}_搜索记录"
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 检查表是否存在
        check_table_sql = """
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
        """
        cursor.execute(check_table_sql, (DB_CONFIG['database'], table_name))
        table_exists = cursor.fetchone()['count'] > 0
        
        if not table_exists:
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'data': []})
        
        # 从用户专属表中查询搜索历史
        sql = f"""
        SELECT `股票代码`, `股票名称`, MAX(`搜索时间`) as `最后搜索时间`, COUNT(*) as `搜索次数`
        FROM `{table_name}`
        GROUP BY `股票代码`, `股票名称`
        ORDER BY `最后搜索时间` DESC
        LIMIT 20
        """
        cursor.execute(sql)
        history = cursor.fetchall()
        
        # 处理datetime对象
        for record in history:
            if record['最后搜索时间'] and hasattr(record['最后搜索时间'], 'strftime'):
                record['最后搜索时间'] = record['最后搜索时间'].strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'data': history})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/history', methods=['DELETE'])
def delete_search_history():
    """删除用户搜索历史记录"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': '未登录'})
        
        data = request.json
        stock_code = data.get('stock_code')
        
        if not stock_code:
            return jsonify({'success': False, 'error': '请提供股票代码'})
        
        # 构建用户专属表名
        safe_username = session['username'].replace('-', '_').replace(' ', '_')
        table_name = f"用户_{safe_username}_搜索记录"
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 检查表是否存在
        check_table_sql = """
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
        """
        cursor.execute(check_table_sql, (DB_CONFIG['database'], table_name))
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': '搜索记录不存在'})
        
        # 删除指定股票的搜索记录
        delete_sql = f"DELETE FROM `{table_name}` WHERE `股票代码` = %s"
        cursor.execute(delete_sql, (stock_code,))
        affected_rows = cursor.rowcount
        conn.commit()
        
        cursor.close()
        conn.close()
        
        if affected_rows > 0:
            return jsonify({'success': True, 'message': f'成功删除 {affected_rows} 条记录'})
        else:
            return jsonify({'success': False, 'error': '未找到相关记录'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== 管理者端路由 ====================

@app.route('/admin/login')
def admin_login_page():
    """管理者登录页面"""
    return render_template('admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    """管理者仪表板"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login_page'))
    return render_template('admin_dashboard.html')


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """管理者登录API"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        # 获取登录IP
        login_ip = request.remote_addr
        
        ADMIN_USERNAME = 'admin'
        ADMIN_PASSWORD = 'admin123'
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # 登录成功，记录日志
            session['user_id'] = 0
            session['username'] = username
            session['user_type'] = 'admin'
            
            # 插入登录日志
            log_sql = """
            INSERT INTO `管理端登录日志` (`用户名`, `登录IP`, `登录状态`)
            VALUES (%s, %s, '成功')
            """
            cursor.execute(log_sql, (username, login_ip))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'message': '登录成功'})
        else:
            # 登录失败，记录日志
            fail_reason = '账号或密码错误'
            log_sql = """
            INSERT INTO `管理端登录日志` (`用户名`, `登录IP`, `登录状态`, `失败原因`)
            VALUES (%s, %s, '失败', %s)
            """
            cursor.execute(log_sql, (username, login_ip, fail_reason))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': False, 'error': fail_reason})
    
    except Exception as e:
        # 异常情况下也记录日志
        try:
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()
            log_sql = """
            INSERT INTO `管理端登录日志` (`用户名`, `登录IP`, `登录状态`, `失败原因`)
            VALUES (%s, %s, '失败', %s)
            """
            cursor.execute(log_sql, (username, request.remote_addr, str(e)))
            conn.commit()
            cursor.close()
            conn.close()
        except:
            pass
        
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/login_log')
def get_admin_login_log():
    """获取管理端登录日志"""
    try:
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'error': '无权限'})
        
        # 获取查询参数
        limit = request.args.get('limit', 100, type=int)  # 默认返回100条
        username_filter = request.args.get('username', '')  # 按用户名过滤
        status_filter = request.args.get('status', '')  # 按状态过滤
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 构建SQL
        sql = "SELECT * FROM `管理端登录日志` WHERE 1=1"
        params = []
        
        if username_filter:
            sql += " AND `用户名` LIKE %s"
            params.append(f"%{username_filter}%")
        
        if status_filter:
            sql += " AND `登录状态` = %s"
            params.append(status_filter)
        
        sql += " ORDER BY `登录时间` DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(sql, params)
        logs = cursor.fetchall()
        
        # 处理datetime对象
        for log in logs:
            if log['登录时间'] and hasattr(log['登录时间'], 'strftime'):
                log['登录时间'] = log['登录时间'].strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'data': logs})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/users')
def get_all_users():
    """获取所有用户列表及其搜索记录表"""
    try:
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'error': '无权限'})
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        sql = "SELECT `id`, `用户名`, `邮箱`, `注册时间`, `最后登录` FROM `用户数据` ORDER BY `注册时间` DESC"
        cursor.execute(sql)
        users = cursor.fetchall()
        
        for user in users:
            for key in ['注册时间', '最后登录']:
                if user[key] and hasattr(user[key], 'strftime'):
                    user[key] = user[key].strftime('%Y-%m-%d %H:%M:%S')
            
            safe_username = user['用户名'].replace('-', '_').replace(' ', '_')
            table_name = f"用户_{safe_username}_搜索记录"
            
            check_sql = """
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = %s
            """
            cursor.execute(check_sql, (DB_CONFIG['database'], table_name))
            result = cursor.fetchone()
            user['有搜索记录'] = result['count'] > 0
            user['搜索记录表名'] = table_name if result['count'] > 0 else None
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'data': users})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/search_users')
def search_users():
    """管理者搜索用户"""
    try:
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'error': '无权限'})
        
        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return jsonify({'success': True, 'data': []})
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        sql = """
        SELECT `id`, `用户名`, `邮箱`, `注册时间`, `最后登录` 
        FROM `用户数据` 
        WHERE `用户名` LIKE %s OR `邮箱` LIKE %s
        ORDER BY `注册时间` DESC
        LIMIT 50
        """
        search_pattern = f"%{keyword}%"
        cursor.execute(sql, (search_pattern, search_pattern))
        users = cursor.fetchall()
        
        for user in users:
            for key in ['注册时间', '最后登录']:
                if user[key] and hasattr(user[key], 'strftime'):
                    user[key] = user[key].strftime('%Y-%m-%d %H:%M:%S')
            
            safe_username = user['用户名'].replace('-', '_').replace(' ', '_')
            table_name = f"用户_{safe_username}_搜索记录"
            
            check_sql = """
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = %s
            """
            cursor.execute(check_sql, (DB_CONFIG['database'], table_name))
            result = cursor.fetchone()
            user['有搜索记录'] = result['count'] > 0
            user['搜索记录表名'] = table_name if result['count'] > 0 else None
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'data': users})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/delete_user', methods=['POST'])
def delete_user():
    """管理者删除用户及其所有数据"""
    try:
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'error': '无权限'})
        
        data = request.json
        username = data.get('username')
        
        if not username:
            return jsonify({'success': False, 'error': '请提供用户名'})
        
        if username == 'admin':
            return jsonify({'success': False, 'error': '不能删除管理员账号'})
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 删除用户的搜索记录表
        safe_username = username.replace('-', '_').replace(' ', '_')
        table_name = f"用户_{safe_username}_搜索记录"
        
        drop_table_sql = f"DROP TABLE IF EXISTS `{table_name}`"
        cursor.execute(drop_table_sql)
        
        # 删除用户账号数据
        delete_user_sql = "DELETE FROM `用户数据` WHERE `用户名` = %s"
        cursor.execute(delete_user_sql, (username,))
        
        affected_rows = cursor.rowcount
        conn.commit()
        
        cursor.close()
        conn.close()
        
        if affected_rows > 0:
            return jsonify({'success': True, 'message': f'成功删除用户 "{username}" 及其所有数据'})
        else:
            return jsonify({'success': False, 'error': f'未找到用户 "{username}"'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/update_stock', methods=['POST'])
def update_stock_data():
    """管理者更新股票数据"""
    try:
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'error': '无权限'})
        
        data = request.json
        stock_code = data.get('股票代码')
        date = data.get('日期')
        field = data.get('字段')
        value = data.get('值')
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        update_sql = f"UPDATE `{TABLE_NAME}` SET `{field}` = %s WHERE `股票代码` = %s AND `日期` = %s"
        cursor.execute(update_sql, (value, stock_code, date))
        conn.commit()
        
        affected_rows = cursor.rowcount
        cursor.close()
        conn.close()
        
        if affected_rows > 0:
            return jsonify({'success': True, 'message': f'成功更新{affected_rows}条记录'})
        else:
            return jsonify({'success': False, 'error': '未找到匹配的记录'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/delete_record', methods=['POST'])
def delete_record():
    """管理者删除记录"""
    try:
        if session.get('user_type') != 'admin':
            return jsonify({'success': False, 'error': '无权限'})
        
        data = request.json
        stock_code = data.get('股票代码')
        date = data.get('日期')
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        delete_sql = f"DELETE FROM `{TABLE_NAME}` WHERE `股票代码` = %s AND `日期` = %s"
        cursor.execute(delete_sql, (stock_code, date))
        conn.commit()
        
        affected_rows = cursor.rowcount
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'成功删除{affected_rows}条记录'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== 公共数据API ====================

@app.route('/api/stock_list')
def get_stock_list():
    """获取所有股票代码和名称列表"""
    try:
        db = get_db_connection()
        sql = f"SELECT DISTINCT `股票代码`, `股票名称` FROM `{TABLE_NAME}` ORDER BY `股票代码`"
        df = db.query_data(sql)
        
        if df.empty:
            return jsonify({'success': True, 'data': []})
        
        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                'code': row['股票代码'],
                'name': row.get('股票名称', '')
            })
        
        return jsonify({'success': True, 'data': stocks})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/search_stocks')
def search_stocks():
    """根据股票名称或代码搜索股票"""
    try:
        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return jsonify({'success': True, 'data': []})
        
        db = get_db_connection()
        # 使用参数化查询防止SQL注入
        sql = f"""
        SELECT DISTINCT `股票代码`, `股票名称` 
        FROM `{TABLE_NAME}` 
        WHERE `股票名称` LIKE %s OR `股票代码` LIKE %s
        ORDER BY `股票代码`
        LIMIT 50
        """
        # LIKE 参数需要添加通配符
        search_pattern = f"%{keyword}%"
        df = pd.read_sql_query(sql, db.engine, params=(search_pattern, search_pattern))
        
        if df.empty:
            return jsonify({'success': True, 'data': []})
        
        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                'code': row['股票代码'],
                'name': row.get('股票名称', '')
            })
        
        return jsonify({'success': True, 'data': stocks})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/trend_data/<stock_code>')
def get_trend_data(stock_code):
    """获取趋势分析数据(支持月份筛选)"""
    try:
        # 获取月份参数(格式:YYYY-MM)
        month = request.args.get('month', None)
        
        print(f"\n[DEBUG] 请求股票数据: stock_code={stock_code}, month={month}")
        
        db = get_db_connection()
        
        if not db.engine:
            print("[ERROR] 数据库引擎未连接")
            return jsonify({'success': False, 'error': '数据库连接失败'})
        
        # 构建基础SQL - 使用参数化查询防止SQL注入
        base_sql = f"""
        SELECT `日期`, `收盘价`, `MA5`, `MA10`, `MA20`, `成交量`, `股票名称`
        FROM `{TABLE_NAME}`
        WHERE `股票代码` = %s
        """
        params = (stock_code,)  # 使用元组而不是列表
        
        # 如果指定了月份,添加月份过滤条件
        if month:
            try:
                # 解析月份参数
                year, mon = month.split('-')
                # 计算该月的起始和结束日期
                from datetime import datetime
                import calendar
                start_date = f"{year}-{mon}-01"
                last_day = calendar.monthrange(int(year), int(mon))[1]
                end_date = f"{year}-{mon}-{last_day:02d}"
                
                base_sql += " AND `日期` >= %s AND `日期` <= %s"
                params = params + (start_date, end_date)  # 元组拼接
                print(f"[DEBUG] 月份过滤: {start_date} 至 {end_date}")
            except Exception as e:
                print(f"[ERROR] 月份参数解析失败: {e}")
        
        base_sql += " ORDER BY `日期` ASC"
        
        # 如果没有指定月份,限制返回最近100条记录
        if not month:
            base_sql += " LIMIT 100"
        
        print(f"[DEBUG] 执行SQL: {base_sql}")
        print(f"[DEBUG] SQL参数: {params}")
        
        # 使用pandas的read_sql_query进行参数化查询
        df = pd.read_sql_query(base_sql, db.engine, params=params)
        
        print(f"[DEBUG] 查询结果: {len(df)} 条记录")
        
        if df.empty:
            print(f"[WARN] 未找到股票 {stock_code} 的数据")
            return jsonify({'success': False, 'error': f'未找到股票代码 {stock_code} 的数据'})
        
        stock_name = df.iloc[0]['股票名称'] if '股票名称' in df.columns and not df.empty else stock_code
        print(f"[DEBUG] 股票名称: {stock_name}")
        
        dates = df['日期'].astype(str).tolist()
        prices = df['收盘价'].tolist()
        ma5 = df['MA5'].tolist() if 'MA5' in df.columns else []
        ma10 = df['MA10'].tolist() if 'MA10' in df.columns else []
        ma20 = df['MA20'].tolist() if 'MA20' in df.columns else []
        volumes = df['成交量'].tolist() if '成交量' in df.columns else []
        
        return jsonify({
            'success': True,
            'data': {
                'dates': dates,
                'prices': prices,
                'ma5': ma5,
                'ma10': ma10,
                'ma20': ma20,
                'volumes': volumes,
                'stockName': stock_name
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    print("=" * 60)
    print("股票数据分析Web系统启动")
    print("=" * 60)
    print(f"访问地址: http://localhost:5000")
    print("=" * 60)
    print("\n默认管理者账号:")
    print("  用户名: admin")
    print("  密码: admin123")
    print("=" * 60)
    
    # 初始化数据库
    if not db_manager.connect():
        print("数据库连接失败！")
        sys.exit(1)
    
    # 初始化用户表
    init_user_table()
    
    # 初始化管理端登录日志表
    init_admin_login_log_table()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
