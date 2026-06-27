"""
股票数据爬虫模块
从东方财富网获取真实股票数据，具有完整的反爬与反反爬能力
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from fake_useragent import UserAgent

# 导入反反爬模块
try:
    from .anti_crawler import AntiCrawlerEngine, AntiCrawlerConfig
except ImportError:
    from spider.anti_crawler import AntiCrawlerEngine, AntiCrawlerConfig


class StockSpider:
    """东方财富网股票数据爬虫
    
    特性：
    - 使用API接口获取真实数据
    - 自动识别市场（上海/深圳）
    - 智能流量控制避免被封
    - 重试机制处理网络异常
    - 完整的反反爬能力（代理池、指纹伪造、会话管理）
    """
    
    def __init__(self, request_delay: tuple = (8, 15), max_retries: int = 3,
                 proxy_api_url: str = ""):
        """
        初始化爬虫
        
        Args:
            request_delay: 请求延迟范围(最小秒数, 最大秒数)
            max_retries: 最大重试次数
            proxy_api_url: 代理池API地址（可选）
        """
        self.request_delay = request_delay
        self.max_retries = max_retries
        
        # 初始化反反爬引擎
        self.anti_crawler = AntiCrawlerEngine(proxy_api_url=proxy_api_url)
        
        # 配置流量控制器
        self.anti_crawler.traffic_controller.min_delay = request_delay[0]
        self.anti_crawler.traffic_controller.max_delay = request_delay[1]
    
    def _get_referer(self, stock_code: str = "") -> str:
        """生成Referer头"""
        if stock_code:
            market_prefix = self._get_market_prefix(stock_code)
            return f"https://quote.eastmoney.com/{market_prefix}{stock_code}.html"
        return "https://quote.eastmoney.com/center/default.html"
    
    def _get_market_prefix(self, stock_code: str) -> str:
        """
        根据股票代码获取市场前缀
        
        Args:
            stock_code: 股票代码
            
        Returns:
            市场前缀 (1表示深圳, 0表示上海)
        """
        if stock_code.startswith(('6', '9')):
            return '1'  # 上海证券交易所（东方财富API中上海是1）
        elif stock_code.startswith(('0', '3')):
            return '0'  # 深圳证券交易所（东方财富API中深圳是0）
        else:
            return '0'  # 默认深圳
    
    def fetch_stock_list(self, market: str = 'all') -> List[str]:
        """
        获取股票列表
        
        Args:
            market: 市场类型 ('sh'=上海, 'sz'=深圳, 'all'=全部)
            
        Returns:
            股票代码列表
        """
        stock_codes = []
        
        # 初始等待，模拟人类行为
        print("正在初始化连接...")
        time.sleep(random.uniform(3, 5))
        
        try:
            # 东方财富网股票列表API
            if market in ['sh', 'all']:
                # 获取上交所股票
                url_sh = 'http://push2.eastmoney.com/api/qt/clist/get'
                params_sh = {
                    'pn': '1',
                    'pz': '10000',  # 每页数量
                    'po': '1',
                    'np': '1',
                    'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                    'fltt': '2',
                    'invt': '2',
                    'fid': 'f3',
                    'fs': 'm:1 t:2,m:1 t:23',  # 上交所A股（m:1=上海）
                    'fields': 'f12',  # 股票代码
                    'wbp2u': '|0|0|0|web',
                }
                # 使用反反爬引擎发起请求
                response = self.anti_crawler.make_request(
                    url=url_sh,
                    params=params_sh,
                    use_proxy=False,  # 股票列表API禁用代理，避免连接问题
                    use_session=True,
                    referer="https://quote.eastmoney.com/center/default.html",
                    is_api=True,
                    timeout=20  # 增加超时时间
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data') and data['data'].get('diff'):
                        for item in data['data']['diff']:
                            stock_codes.append(item['f12'])
                        print(f"获取到上交所 {len(data['data']['diff'])} 只股票")
            
            if market in ['sz', 'all']:
                # 获取深交所股票
                url_sz = 'http://push2.eastmoney.com/api/qt/clist/get'
                params_sz = {
                    'pn': '1',
                    'pz': '10000',
                    'po': '1',
                    'np': '1',
                    'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                    'fltt': '2',
                    'invt': '2',
                    'fid': 'f3',
                    'fs': 'm:0 t:6,m:0 t:80',  # 深交所A股（m:0=深圳）
                    'fields': 'f12',
                    'wbp2u': '|0|0|0|web',
                }
                # 使用反反爬引擎发起请求
                response = self.anti_crawler.make_request(
                    url=url_sz,
                    params=params_sz,
                    use_proxy=False,  # 股票列表API禁用代理，避免连接问题
                    use_session=True,
                    referer="https://quote.eastmoney.com/center/default.html",
                    is_api=True,
                    timeout=20  # 增加超时时间
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data') and data['data'].get('diff'):
                        for item in data['data']['diff']:
                            stock_codes.append(item['f12'])
                        print(f"获取到深交所 {len(data['data']['diff'])} 只股票")
            
            print(f"总共获取到 {len(stock_codes)} 只股票")
            return stock_codes
            
        except Exception as e:
            print(f"获取股票列表失败: {str(e)}")
            return []
    
    def _validate_stock_data(self, df: pd.DataFrame, stock_code: str) -> bool:
        """
        验证股票数据的有效性，识别蜜罐陷阱返回的假数据
        
        Args:
            df: 股票数据DataFrame
            stock_code: 股票代码
            
        Returns:
            True表示数据有效，False表示疑似假数据
        """
        if df.empty:
            return True  # 空数据不算假数据
        
        # 检查1: 所有数值字段是否都为0或相同值（蜜罐常见特征）
        numeric_columns = ['开盘价', '收盘价', '最高价', '最低价', '成交量']
        for col in numeric_columns:
            if col in df.columns:
                unique_values = df[col].nunique()
                if unique_values == 1 and df[col].iloc[0] == 0:
                    print(f"⚠️  [数据验证] 股票 {stock_code} 的 {col} 全部为0，疑似蜜罐假数据")
                    return False
                if unique_values <= 2 and len(df) > 10:
                    # 超过10条数据但只有1-2个不同值，高度可疑
                    print(f"⚠️  [数据验证] 股票 {stock_code} 的 {col} 缺乏变化({unique_values}个唯一值)，疑似蜜罐假数据")
                    return False
        
        # 检查2: 价格是否符合逻辑（最高价 >= 最低价）
        if all(col in df.columns for col in ['最高价', '最低价']):
            invalid_rows = df[df['最高价'] < df['最低价']]
            if len(invalid_rows) > len(df) * 0.1:  # 超过10%的数据不符合逻辑
                print(f"⚠️  [数据验证] 股票 {stock_code} 有{len(invalid_rows)}条数据最高价<最低价，疑似蜜罐假数据")
                return False
        
        # 检查3: 日期是否连续且合理
        if '日期' in df.columns:
            dates = pd.to_datetime(df['日期'])
            if len(dates) > 1:
                date_diffs = dates.diff().dt.days.dropna()
                # 检查是否有异常的日期间隔（如未来日期或间隔过大）
                if (date_diffs < 0).any():
                    print(f"⚠️  [数据验证] 股票 {stock_code} 存在未来日期，疑似蜜罐假数据")
                    return False
                if date_diffs.max() > 365:
                    print(f"⚠️  [数据验证] 股票 {stock_code} 日期间隔异常({date_diffs.max()}天)，疑似蜜罐假数据")
                    return False
        
        # 检查4: 数据量是否合理
        if len(df) > 0 and len(df) < 5:
            # 数据量过少可能是蜜罐返回的样板数据
            print(f"⚠️  [数据验证] 股票 {stock_code} 仅获取到{len(df)}条数据，可能不完整")
            # 不直接返回False，只是警告
        
        return True
    
    def fetch_stock_data(self, stock_code: str, days: int = 30) -> pd.DataFrame:
        """
        获取单只股票的历史K线数据
        
        Args:
            stock_code: 股票代码
            days: 获取天数
            
        Returns:
            包含股票数据的DataFrame
        """
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                # 获取市场前缀
                market = self._get_market_prefix(stock_code)
                secid = f"{market}.{stock_code}"
                
                # 计算开始日期
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
                end_date = datetime.now().strftime('%Y%m%d')
                
                # 东方财富网K线数据API
                url = 'http://push2his.eastmoney.com/api/qt/stock/kline/get'
                params = {
                    'secid': secid,
                    'fields1': 'f1,f2,f3,f4,f5,f6',
                    'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                    'klt': '101',  # 日K线
                    'fqt': '1',    # 前复权
                    'beg': start_date,
                    'end': end_date,
                    'smplmt': '100000',
                    'lmt': '1000000',
                }
                
                # 使用反反爬引擎发起请求
                response = self.anti_crawler.make_request(
                    url=url,
                    params=params,
                    use_proxy=False,  # K线API禁用代理，避免RemoteDisconnected错误
                    use_session=True,
                    referer=self._get_referer(stock_code),
                    is_api=True,
                    timeout=15
                )
                
                if response.status_code != 200:
                    raise Exception(f"HTTP错误: {response.status_code}")
                
                data = response.json()
                
                if not data.get('data') or not data['data'].get('klines'):
                    print(f"股票 {stock_code} 无数据")
                    return pd.DataFrame()
                
                # 获取股票名称
                stock_name = data['data'].get('name', '')
                
                # 解析K线数据
                klines = data['data']['klines']
                parsed_data = []
                
                for line in klines:
                    fields = line.split(',')
                    if len(fields) >= 6:
                        parsed_data.append({
                            '日期': fields[0],
                            '开盘价': float(fields[1]),
                            '收盘价': float(fields[2]),
                            '最高价': float(fields[3]),
                            '最低价': float(fields[4]),
                            '成交量': int(fields[5]),
                            '成交额': float(fields[6]) if len(fields) > 6 else 0,
                            '涨跌幅': float(fields[7]) if len(fields) > 7 else 0,
                            '换手率': float(fields[8]) if len(fields) > 8 else 0,
                            '股票代码': stock_code,
                            '股票名称': stock_name,
                        })
                
                df = pd.DataFrame(parsed_data)
                
                if not df.empty:
                    # 转换日期格式
                    df['日期'] = pd.to_datetime(df['日期'])
                    
                    # 蜜罐反制：验证数据有效性
                    if not self._validate_stock_data(df, stock_code):
                        print(f"❌ 股票 {stock_code} 数据验证失败，判定为蜜罐假数据，丢弃")
                        return pd.DataFrame()
                    
                    print(f"成功获取股票 {stock_code} ({stock_name}) 的 {len(df)} 条数据")
                    return df
                
                return pd.DataFrame()
                
            except Exception as e:
                retry_count += 1
                print(f"爬取股票 {stock_code} 失败 (尝试 {retry_count}/{self.max_retries}): {str(e)}")
                
                if retry_count >= self.max_retries:
                    print(f"股票 {stock_code} 达到最大重试次数，跳过")
                    return pd.DataFrame()
                # 注意：不再手动sleep，由make_request内部的指数退避处理
    
    def fetch_all_stocks(self, stock_codes: List[str] = None, days: int = 30, 
                         limit: Optional[int] = None) -> pd.DataFrame:
        """
        批量获取多只股票数据
        
        Args:
            stock_codes: 股票代码列表，如果为None则自动获取
            days: 每只股票获取的天数
            limit: 限制爬取的股票数量（用于测试），None表示不限制
            
        Returns:
            包含所有股票数据的DataFrame
        """
        if stock_codes is None:
            print("正在获取股票列表...")
            stock_codes = self.fetch_stock_list()
        
        if limit:
            stock_codes = stock_codes[:limit]
            print(f"限制爬取前 {limit} 只股票")
        
        all_data = []
        success_count = 0
        fail_count = 0
        
        print(f"\n开始爬取 {len(stock_codes)} 只股票的数据...")
        print(f"预计耗时: {len(stock_codes) * sum(self.request_delay) / 2 / 60:.1f} 分钟\n")
        
        for i, code in enumerate(stock_codes):
            try:
                print(f"[{i+1}/{len(stock_codes)}] 正在爬取股票: {code}")
                df = self.fetch_stock_data(code, days)
                
                if not df.empty:
                    all_data.append(df)
                    success_count += 1
                else:
                    fail_count += 1
                
                # 随机延迟，避免被封
                delay = random.uniform(*self.request_delay)
                print(f"      等待 {delay:.1f} 秒...\n")
                time.sleep(delay)
                
                # 每爬取50只股票，增加额外延迟
                if (i + 1) % 50 == 0:
                    extra_delay = random.uniform(10, 30)
                    print(f"已爬取 {i+1} 只股票，休息 {extra_delay:.1f} 秒...\n")
                    time.sleep(extra_delay)
                    
            except KeyboardInterrupt:
                print("\n用户中断爬取")
                break
            except Exception as e:
                print(f"爬取股票 {code} 时发生异常: {str(e)}\n")
                fail_count += 1
                continue
        
        if all_data:
            result_df = pd.concat(all_data, ignore_index=True)
            print(f"\n{'='*60}")
            print(f"爬取完成!")
            print(f"成功: {success_count} 只股票")
            print(f"失败: {fail_count} 只股票")
            print(f"总数据量: {len(result_df)} 条记录")
            print(f"{'='*60}")
            return result_df
        else:
            print("未获取到任何数据")
            return pd.DataFrame()
    
    def get_stock_realtime_info(self, stock_code: str) -> Optional[Dict]:
        """
        获取股票实时信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票实时信息字典
        """
        try:
            market = self._get_market_prefix(stock_code)
            secid = f"{market}.{stock_code}"
            
            url = 'http://push2.eastmoney.com/api/qt/stock/get'
            params = {
                'secid': secid,
                'fields': 'f43,f57,f58,f169,f170,f46,f44,f51,f168,f47,f164,f163,f116,f60,f45,f52,f50,f48,f167,f117,f71,f161,f49,f530',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            }
            
            response = self.anti_crawler.make_request(
                url=url,
                params=params,
                use_proxy=False,  # 实时信息API禁用代理，避免RemoteDisconnected错误
                use_session=True,
                referer=self._get_referer(stock_code),
                is_api=True,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    info = data['data']
                    return {
                        '股票代码': info.get('f57'),
                        '股票名称': info.get('f58'),
                        '最新价': info.get('f43'),
                        '涨跌幅': info.get('f169'),
                        '涨跌额': info.get('f170'),
                        '成交量': info.get('f47'),
                        '成交额': info.get('f48'),
                        '最高价': info.get('f44'),
                        '最低价': info.get('f45'),
                        '开盘价': info.get('f46'),
                        '昨收价': info.get('f60'),
                    }
            
            return None
            
        except Exception as e:
            print(f"获取股票 {stock_code} 实时信息失败: {str(e)}")
            return None


if __name__ == '__main__':
    # 测试爬虫功能
    spider = StockSpider(request_delay=(2, 4), max_retries=3)
    
    print("="*60)
    print("测试1: 获取股票列表")
    print("="*60)
    stock_list = spider.fetch_stock_list(market='all')
    print(f"获取到 {len(stock_list)} 只股票\n")
    
    if stock_list:
        print("="*60)
        print("测试2: 获取单只股票的实时信息")
        print("="*60)
        test_code = stock_list[0]
        realtime_info = spider.get_stock_realtime_info(test_code)
        if realtime_info:
            print(json.dumps(realtime_info, ensure_ascii=False, indent=2))
        print()
        
        print("="*60)
        print("测试3: 获取单只股票的历史K线数据")
        print("="*60)
        df = spider.fetch_stock_data(test_code, days=30)
        if not df.empty:
            print(f"\n最近5条数据:")
            print(df.tail())
            print(f"\n数据形状: {df.shape}")
            print(f"列名: {list(df.columns)}")
        print()
        
        print("="*60)
        print("测试4: 批量获取少量股票数据（仅前3只）")
        print("="*60)
        batch_df = spider.fetch_all_stocks(stock_codes=stock_list[:3], days=10)
        if not batch_df.empty:
            print(f"\n批量数据预览:")
            print(batch_df.head(10))
            print(f"\n总数据量: {len(batch_df)} 条")
