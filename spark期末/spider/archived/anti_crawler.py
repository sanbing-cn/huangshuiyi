"""
反反爬核心模块
提供完整的反反爬能力，包括：
- 请求伪装与指纹伪造
- 分布式代理池管理
- 智能流量调度引擎
- 会话状态管理
- 人机行为模拟
"""

import requests
from fake_useragent import UserAgent
import time
import random
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import threading


class AntiCrawlerConfig:
    """反反爬配置类"""
    
    # 请求延迟配置（秒）
    MIN_DELAY = 2.0
    MAX_DELAY = 5.0
    EXTRA_DELAY_INTERVAL = 50  # 每N个请求增加额外延迟
    EXTRA_DELAY_MIN = 10.0
    EXTRA_DELAY_MAX = 30.0
    
    # 重试配置
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 3.0
    RETRY_MAX_DELAY = 60.0
    
    # 代理池配置
    PROXY_API_URL = "http://api.91http.com/v1/get-ip?trade_no=A300665190048&secret=7lR7dIupsbpN7ZB3&num=10&protocol=1&format=json&sep=1&auto_white=1&time=1&pw=1"  # 代理池API地址（JSON格式，带自动白名单、时间戳和密码认证）
    PROXY_TIMEOUT = 15  # 增加超时时间到15秒，提高代理稳定性
    PROXY_REFRESH_INTERVAL = 300  # 代理刷新间隔（秒）
    # 注意：当API URL中包含pw=1时，91HTTP会为每个代理返回独立的认证信息（http_user和http_pass）
    
    # 会话配置
    SESSION_MAX_REQUESTS = 100  # 单个会话最大请求数
    SESSION_ROTATE_INTERVAL = 600  # 会话轮换间隔（秒）
    
    # 指纹配置
    ENABLE_CANVAS_FINGERPRINT = True
    ENABLE_WEBGL_FINGERPRINT = True
    
    # 蜜罐检测配置
    HONEYPOT_DETECTION_ENABLED = True  # 启用蜜罐检测
    SUSPICIOUS_RESPONSE_TIME = 0.1  # 可疑响应时间阈值（秒），过快可能是蜜罐
    DATA_VALIDATION_ENABLED = True  # 启用数据有效性校验


class ProxyPool:
    """分布式代理池管理器（增强版 - 蜜罐规避）"""
    
    def __init__(self, api_url: str = "", timeout: int = 5):
        """
        初始化代理池
        
        Args:
            api_url: 代理池API地址
            timeout: 代理超时时间（秒）
        """
        self.api_url = api_url or AntiCrawlerConfig.PROXY_API_URL
        self.timeout = timeout
        self.proxies: List[Dict] = []
        self.current_proxy_index = 0
        self.last_refresh_time = 0
        self.lock = threading.Lock()
        
        # 蜜罐规避：IP黑名单和信誉评分系统
        self.blacklisted_ips = set()  # 黑名单IP集合
        self.ip_reputation = {}  # IP信誉评分 {ip: score}，分数越低越可疑
        self.ip_failure_count = {}  # IP失败次数统计
        self.HONEYPOT_THRESHOLD = 3  # 蜜罐判定阈值：失败3次加入黑名单
        
        # 蜜罐规避：IP黑名单和信誉评分系统
        self.blacklisted_ips = set()  # 黑名单IP集合
        self.ip_reputation = {}  # IP信誉评分 {ip: score}，分数越低越可疑
        self.ip_failure_count = {}  # IP失败次数统计
        self.HONEYPOT_THRESHOLD = 3  # 蜜罐判定阈值：失败3次加入黑名单
        
        # 如果提供了API地址，立即获取代理
        if self.api_url:
            self.refresh_proxies()
    
    def refresh_proxies(self) -> bool:
        """
        从API刷新代理列表
        
        Returns:
            是否刷新成功
        """
        if not self.api_url:
            print("警告: 代理池API未配置，将不使用代理")
            return False
        
        try:
            response = requests.get(self.api_url, timeout=self.timeout)
            if response.status_code == 200:
                # 检测响应格式（JSON或纯文本）
                content_type = response.headers.get('Content-Type', '')
                
                if 'text/plain' in content_type or not response.text.strip().startswith('{'):
                    # 格式4: 纯文本格式，每行一个 ip:port
                    proxy_list = [line.strip() for line in response.text.strip().split('\n') if line.strip()]
                    print(f"检测到纯文本格式，解析到 {len(proxy_list)} 个代理")
                else:
                    # JSON格式
                    data = response.json()
                    
                    # 支持多种API响应格式
                    if isinstance(data, list):
                        # 格式1: 直接返回代理列表 ["ip:port", "ip:port"]
                        proxy_list = data
                    elif isinstance(data, dict) and 'proxies' in data:
                        # 格式2: {"proxies": ["ip:port", ...]}
                        proxy_list = data['proxies']
                    elif isinstance(data, dict) and 'data' in data:
                        # 格式3: {"data": {"proxy_list": [...]}}
                        raw_list = data['data'].get('proxy_list', [])
                        
                        # 检查是否为对象格式 [{"ip": "...", "port": ..., "http_user": "...", "http_pass": "..."}]
                        if raw_list and isinstance(raw_list[0], dict):
                            # 转换为带认证的 "username:password@ip:port" 格式
                            authenticated_proxies = []
                            for item in raw_list:
                                if 'ip' in item and 'port' in item:
                                    ip = item['ip']
                                    port = item['port']
                                    # 91HTTP返回的独立认证信息
                                    user = item.get('http_user', '')
                                    password = item.get('http_pass', '')
                                    if user and password:
                                        authenticated_proxies.append(f"{user}:{password}@{ip}:{port}")
                                    else:
                                        authenticated_proxies.append(f"{ip}:{port}")
                            proxy_list = authenticated_proxies
                            print(f"检测到对象格式，转换后得到 {len(proxy_list)} 个代理（带认证）")
                        else:
                            proxy_list = raw_list
                    else:
                        proxy_list = []
                
                # 构建代理字典（91HTTP代理已包含认证信息）
                # 蜜罐规避：过滤黑名单IP
                filtered_proxies = []
                for p in proxy_list:
                    if not self._validate_proxy_format(p):
                        continue
                    # 提取IP地址进行黑名单检查（p的格式可能是 username:password@ip:port 或 ip:port）
                    if '@' in p:
                        ip_address = p.split('@')[1].split(':')[0]
                    else:
                        ip_address = p.split(':')[0]
                    
                    if ip_address in self.blacklisted_ips:
                        print(f"   ⚠️  过滤黑名单IP: {ip_address}")
                        continue
                    # p已经包含认证信息：username:password@ip:port
                    filtered_proxies.append({"http": f"http://{p}", "https": f"http://{p}"})
                
                self.proxies = filtered_proxies
                
                with self.lock:
                    self.current_proxy_index = 0
                    self.last_refresh_time = time.time()
                
                print(f"代理池刷新成功，获取到 {len(self.proxies)} 个可用代理")
                return len(self.proxies) > 0
            else:
                print(f"代理池API返回错误: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"刷新代理池失败: {str(e)}")
            return False
    
    def _validate_proxy_format(self, proxy: str) -> bool:
        """验证代理格式（支持 username:password@ip:port 或 ip:port）"""
        try:
            # 如果包含@，说明是带认证的格式
            if '@' in proxy:
                # 提取@后面的 ip:port 部分
                ip_port = proxy.split('@')[1]
            else:
                ip_port = proxy
            
            parts = ip_port.split(':')
            if len(parts) == 2:
                ip, port = parts
                port_num = int(port)
                return 0 < port_num < 65536
            return False
        except:
            return False
    
    def get_proxy(self, force_refresh: bool = False) -> Optional[Dict]:
        """
        获取一个代理（每次返回不同IP）
        
        Args:
            force_refresh: 是否强制刷新代理池
            
        Returns:
            代理字典或None
        """
        with self.lock:
            # 检查是否需要刷新代理
            if force_refresh or time.time() - self.last_refresh_time > AntiCrawlerConfig.PROXY_REFRESH_INTERVAL:
                self.refresh_proxies()
            
            if not self.proxies:
                return None
            
            # 随机选择一个代理，而不是轮询
            proxy = random.choice(self.proxies)
            return proxy
    
    def remove_bad_proxy(self, proxy: Dict, is_honeypot: bool = False):
        """
        移除失效的代理并记录信誉
        
        Args:
            proxy: 代理字典
            is_honeypot: 是否因为蜜罐检测而移除
        """
        with self.lock:
            if proxy in self.proxies:
                # 提取IP地址（处理 username:password@ip:port 格式）
                proxy_url = proxy.get('http', '')
                if '@' in proxy_url:
                    ip_address = proxy_url.split('@')[1].split(':')[0]
                else:
                    ip_address = proxy_url.replace('http://', '').split(':')[0]
                
                # 更新失败计数
                self.ip_failure_count[ip_address] = self.ip_failure_count.get(ip_address, 0) + 1
                failure_count = self.ip_failure_count[ip_address]
                
                # 降低信誉评分
                current_rep = self.ip_reputation.get(ip_address, 100)
                penalty = 30 if is_honeypot else 15  # 蜜罐惩罚更重
                self.ip_reputation[ip_address] = max(0, current_rep - penalty)
                
                # 如果失败次数超过阈值或信誉过低，加入黑名单
                if failure_count >= self.HONEYPOT_THRESHOLD or self.ip_reputation[ip_address] < 30:
                    self.blacklisted_ips.add(ip_address)
                    print(f"🚫 [黑名单] IP {ip_address} 已加入黑名单 (失败{failure_count}次, 信誉{self.ip_reputation[ip_address]})")
                
                # 从当前代理池移除
                self.proxies.remove(proxy)
                reason = "蜜罐陷阱" if is_honeypot else "连接失败"
                print(f"❌ 已移除失效代理 ({reason}): {ip_address}")
    
    def restore_ip_reputation(self, ip_address: str):
        """恢复IP信誉（成功请求后调用）"""
        with self.lock:
            # 如果传入的是完整URL，提取IP
            if '@' in ip_address:
                ip_address = ip_address.split('@')[1].split(':')[0]
            elif '://' in ip_address:
                ip_address = ip_address.split('://')[1].split(':')[0]
            
            if ip_address in self.ip_reputation:
                self.ip_reputation[ip_address] = min(100, self.ip_reputation[ip_address] + 5)
                # 如果信誉恢复到安全水平，从黑名单移除
                if self.ip_reputation[ip_address] >= 80 and ip_address in self.blacklisted_ips:
                    self.blacklisted_ips.remove(ip_address)
                    print(f"✅ [信誉恢复] IP {ip_address} 已从黑名单移除 (信誉{self.ip_reputation[ip_address]})")


class FingerprintGenerator:
    """浏览器指纹生成器"""
    
    @staticmethod
    def generate_canvas_fingerprint() -> str:
        """生成Canvas指纹"""
        canvas_data = f"canvas_{random.random()}_{time.time()}"
        return hashlib.md5(canvas_data.encode()).hexdigest()
    
    @staticmethod
    def generate_webgl_fingerprint() -> str:
        """生成WebGL指纹"""
        vendors = [
            "Google Inc. (NVIDIA)",
            "Google Inc. (Intel)",
            "Google Inc. (AMD)",
            "ATI Technologies Inc.",
        ]
        renderers = [
            "ANGLE (NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0)",
            "ANGLE (Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)",
            "ANGLE (AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)",
        ]
        vendor = random.choice(vendors)
        renderer = random.choice(renderers)
        fingerprint = f"{vendor}_{renderer}"
        return hashlib.md5(fingerprint.encode()).hexdigest()
    
    @staticmethod
    def generate_screen_resolution() -> Dict[str, int]:
        """生成屏幕分辨率"""
        resolutions = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
            {"width": 2560, "height": 1440},
            {"width": 3840, "height": 2160},
        ]
        return random.choice(resolutions)
    
    @staticmethod
    def generate_timezone() -> str:
        """生成时区"""
        timezones = [
            "Asia/Shanghai",
            "America/New_York",
            "Europe/London",
            "Asia/Tokyo",
        ]
        return random.choice(timezones)


class SessionManager:
    """会话管理器 - 管理Cookie和Session生命周期"""
    
    def __init__(self):
        self.sessions: List[requests.Session] = []
        self.current_session_index = 0
        self.session_request_count = {}
        self.session_create_time = {}
        self.lock = threading.Lock()
    
    def get_session(self, ua_generator: UserAgent) -> requests.Session:
        """
        获取或创建会话
        
        Args:
            ua_generator: User-Agent生成器
            
        Returns:
            requests.Session对象
        """
        with self.lock:
            now = time.time()
            self._cleanup_sessions(now)
            
            if self.sessions:
                session = self.sessions[self.current_session_index]
                session_id = id(session)
                
                if (self.session_request_count.get(session_id, 0) < AntiCrawlerConfig.SESSION_MAX_REQUESTS and
                    now - self.session_create_time.get(session_id, 0) < AntiCrawlerConfig.SESSION_ROTATE_INTERVAL):
                    self.session_request_count[session_id] = self.session_request_count.get(session_id, 0) + 1
                    self.current_session_index = (self.current_session_index + 1) % len(self.sessions)
                    return session
            
            new_session = self._create_new_session(ua_generator)
            session_id = id(new_session)
            self.sessions.append(new_session)
            self.session_request_count[session_id] = 1
            self.session_create_time[session_id] = now
            
            return new_session
    
    def _create_new_session(self, ua_generator: UserAgent) -> requests.Session:
        """创建新的会话"""
        session = requests.Session()
        headers = RequestHeaderGenerator.generate_complete_headers(ua_generator)
        session.headers.update(headers)
        return session
    
    def _cleanup_sessions(self, current_time: float):
        """清理过期或超限的会话"""
        expired_sessions = []
        
        for session in self.sessions:
            session_id = id(session)
            request_count = self.session_request_count.get(session_id, 0)
            create_time = self.session_create_time.get(session_id, 0)
            
            if (request_count >= AntiCrawlerConfig.SESSION_MAX_REQUESTS or
                current_time - create_time >= AntiCrawlerConfig.SESSION_ROTATE_INTERVAL):
                expired_sessions.append(session)
        
        for session in expired_sessions:
            session.close()
            session_id = id(session)
            self.sessions.remove(session)
            self.session_request_count.pop(session_id, None)
            self.session_create_time.pop(session_id, None)


class RequestHeaderGenerator:
    """请求头生成器 - 生成高度仿真的HTTP请求头"""
    
    @staticmethod
    def generate_complete_headers(ua_generator: UserAgent) -> Dict[str, str]:
        """生成完整的请求头"""
        ua = ua_generator.random
        browser_info = RequestHeaderGenerator._parse_ua(ua)
        
        headers = {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        if 'Chrome' in ua:
            sec_ch_ua = RequestHeaderGenerator._generate_sec_ch_ua(browser_info)
            headers.update(sec_ch_ua)
        
        return headers
    
    @staticmethod
    def _parse_ua(ua: str) -> Dict[str, str]:
        """解析User-Agent获取浏览器信息"""
        info = {'browser': 'Chrome', 'version': '120', 'platform': 'Windows NT 10.0'}
        
        if 'Chrome/' in ua:
            version_start = ua.index('Chrome/') + 7
            version_end = ua.index('.', version_start)
            info['version'] = ua[version_start:version_end]
        
        if 'Windows NT' in ua:
            info['platform'] = 'Windows'
        elif 'Macintosh' in ua:
            info['platform'] = 'macOS'
        elif 'Linux' in ua:
            info['platform'] = 'Linux'
        
        return info
    
    @staticmethod
    def _generate_sec_ch_ua(browser_info: Dict) -> Dict[str, str]:
        """生成Sec-Ch-Ua头部"""
        version = browser_info.get('version', '120')
        return {
            'Sec-Ch-Ua': f'"Not_A Brand";v="8", "Chromium";v="{version}", "Google Chrome";v="{version}"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': f'"{browser_info.get("platform", "Windows")}"',
            'Sec-Ch-Ua-Platform-Version': '"10.0.0"',
            'Sec-Ch-Ua-Arch': '"x86"',
            'Sec-Ch-Ua-Model': '""',
            'Sec-Ch-Ua-Bitness': '"64"',
        }
    
    @staticmethod
    def generate_api_headers(ua_generator: UserAgent, referer: str = "") -> Dict[str, str]:
        """生成API请求头"""
        ua = ua_generator.random
        headers = {
            'User-Agent': ua,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'X-Requested-With': 'XMLHttpRequest',
        }
        
        if referer:
            headers['Referer'] = referer
        
        if 'Chrome' in ua:
            browser_info = RequestHeaderGenerator._parse_ua(ua)
            sec_ch_ua = RequestHeaderGenerator._generate_sec_ch_ua(browser_info)
            headers.update(sec_ch_ua)
        
        return headers


class TrafficController:
    """智能流量控制器 - 实现随机延迟和指数退避"""
    
    def __init__(self, min_delay: float = None, max_delay: float = None):
        self.min_delay = min_delay or AntiCrawlerConfig.MIN_DELAY
        self.max_delay = max_delay or AntiCrawlerConfig.MAX_DELAY
        self.request_count = 0
        self.last_request_time = 0
        # 蜜罐规避：记录请求模式，避免过于规律
        self.request_intervals = []  # 记录请求间隔历史
        self.pattern_detection_threshold = 10  # 模式检测阈值
    
    def wait_before_request(self):
        """在请求前执行智能等待（增强版 - 避免触发蜜罐）"""
        base_delay = random.uniform(self.min_delay, self.max_delay)
        
        # 蜜罐规避1: 引入更复杂的行为因子，模拟人类浏览习惯
        behavior_factor = random.choices(
            [0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5], 
            weights=[5, 10, 20, 30, 15, 10, 7, 3], 
            k=1
        )[0]
        
        # 蜜罐规避2: 添加微小抖动（±20%），打破固定模式
        jitter = random.uniform(0.8, 1.2)
        delay = base_delay * behavior_factor * jitter
        
        # 蜜罐规避3: 检查是否存在明显的请求模式
        if len(self.request_intervals) >= self.pattern_detection_threshold:
            avg_interval = sum(self.request_intervals[-self.pattern_detection_threshold:]) / self.pattern_detection_threshold
            # 如果当前间隔与平均值过于接近，增加随机性
            if abs(delay - avg_interval) < avg_interval * 0.1:
                delay *= random.uniform(1.3, 2.0)  # 显著偏离平均值
        
        self.request_count += 1
        
        # 定期额外休息（随机化周期）
        extra_interval = random.randint(40, 60)  # 在40-60之间随机，而非固定的50
        if self.request_count % extra_interval == 0:
            extra_delay = random.uniform(AntiCrawlerConfig.EXTRA_DELAY_MIN, AntiCrawlerConfig.EXTRA_DELAY_MAX)
            print(f"[流量控制] 已发送 {self.request_count} 个请求，额外休息 {extra_delay:.1f} 秒")
            delay += extra_delay
        
        if delay > 0:
            time.sleep(delay)
        
        # 记录请求间隔用于模式分析
        current_time = time.time()
        if self.last_request_time > 0:
            interval = current_time - self.last_request_time
            self.request_intervals.append(interval)
            # 只保留最近的100个间隔记录
            if len(self.request_intervals) > 100:
                self.request_intervals = self.request_intervals[-100:]
        
        self.last_request_time = current_time
    
    def exponential_backoff(self, retry_count: int, status_code: int = 0) -> float:
        """指数退避策略"""
        base_delay = AntiCrawlerConfig.RETRY_BASE_DELAY
        
        if status_code == 429:
            multiplier = 2.5
        elif status_code == 403:
            multiplier = 3.0
        elif status_code == 503:
            multiplier = 2.0
        else:
            multiplier = 2.0
        
        exponential_delay = base_delay * (multiplier ** retry_count)
        jitter = random.uniform(0.8, 1.2)
        wait_time = min(exponential_delay * jitter, AntiCrawlerConfig.RETRY_MAX_DELAY)
        
        print(f"[指数退避] 第{retry_count}次重试，等待 {wait_time:.1f} 秒 (状态码: {status_code})")
        return wait_time


class AntiCrawlerEngine:
    """反反爬引擎 - 整合所有反反爬能力"""
    
    def __init__(self, proxy_api_url: str = ""):
        """
        初始化反反爬引擎
        
        Args:
            proxy_api_url: 代理池API地址
        """
        self.ua_generator = UserAgent()
        self.proxy_pool = ProxyPool(api_url=proxy_api_url)
        self.session_manager = SessionManager()
        self.fingerprint_gen = FingerprintGenerator()
        self.traffic_controller = TrafficController()
        
        self.canvas_fp = self.fingerprint_gen.generate_canvas_fingerprint()
        self.webgl_fp = self.fingerprint_gen.generate_webgl_fingerprint()
        self.screen_res = self.fingerprint_gen.generate_screen_resolution()
        self.timezone = self.fingerprint_gen.generate_timezone()
        
        # 蜜罐检测状态
        self.honeypot_suspicious_count = 0
        self.last_request_time = 0
        self.request_history = []  # 记录最近请求历史用于模式分析
        
        print("="*60)
        print("反反爬引擎初始化完成")
        print(f"Canvas指纹: {self.canvas_fp}")
        print(f"WebGL指纹: {self.webgl_fp}")
        print(f"屏幕分辨率: {self.screen_res['width']}x{self.screen_res['height']}")
        print(f"时区: {self.timezone}")
        print(f"蜜罐检测: {'已启用' if AntiCrawlerConfig.HONEYPOT_DETECTION_ENABLED else '已禁用'}")
        print("="*60)
    
    def _detect_honeypot(self, response: requests.Response, request_start_time: float, url: str) -> bool:
        """
        检测是否为蜜罐陷阱
        
        Args:
            response: 响应对象
            request_start_time: 请求开始时间
            url: 请求URL
            
        Returns:
            True表示疑似蜜罐，False表示正常
        """
        if not AntiCrawlerConfig.HONEYPOT_DETECTION_ENABLED:
            return False
        
        is_suspicious = False
        reasons = []
        
        # 1. 检测响应时间异常（过快或过慢）
        response_time = time.time() - request_start_time
        if response_time < AntiCrawlerConfig.SUSPICIOUS_RESPONSE_TIME:
            reasons.append(f"响应过快({response_time:.3f}s)")
            is_suspicious = True
        
        # 2. 检测异常状态码
        if response.status_code == 200 and len(response.text) < 100:
            # 返回200但内容极少，可能是蜜罐
            reasons.append("响应内容过少")
            is_suspicious = True
        
        # 3. 检测HTML中的蜜罐特征
        if 'text/html' in response.headers.get('Content-Type', ''):
            html_content = response.text.lower()
            honeypot_keywords = ['honeypot', 'trap', 'decoy', '禁止访问', '异常访问', '验证失败']
            for keyword in honeypot_keywords:
                if keyword in html_content:
                    reasons.append(f"发现蜜罐关键词: {keyword}")
                    is_suspicious = True
                    break
        
        # 4. 检测API响应的数据合理性
        if 'application/json' in response.headers.get('Content-Type', ''):
            try:
                data = response.json()
                # 检查是否返回全零或固定模式的假数据
                if isinstance(data, dict):
                    # 检查关键字段是否都为0或空
                    if all(v == 0 or v == '' or v is None for v in data.values()):
                        reasons.append("API返回全空数据")
                        is_suspicious = True
            except:
                pass
        
        if is_suspicious:
            self.honeypot_suspicious_count += 1
            print(f"\n⚠️  [蜜罐检测] 疑似蜜罐陷阱！")
            print(f"   URL: {url}")
            print(f"   原因: {', '.join(reasons)}")
            print(f"   累计可疑次数: {self.honeypot_suspicious_count}")
            
            # 如果连续多次检测到蜜罐，采取更激进的措施
            if self.honeypot_suspicious_count >= 3:
                print("   ⚡ 触发紧急规避策略：强制刷新代理池 + 延长等待时间")
                self.proxy_pool.refresh_proxies()
                time.sleep(random.uniform(10, 20))
                self.honeypot_suspicious_count = 0  # 重置计数器
        
        return is_suspicious
    
    def make_request(self, url: str, method: str = 'GET', 
                     params: Dict = None, data: Dict = None,
                     use_proxy: bool = True, use_session: bool = True,
                     referer: str = "", is_api: bool = False,
                     timeout: int = 15) -> requests.Response:
        """
        发起带有反反爬保护的请求
        """
        retry_count = 0
        last_exception = None
        
        while retry_count <= AntiCrawlerConfig.MAX_RETRIES:
            try:
                if retry_count == 0:
                    self.traffic_controller.wait_before_request()
                else:
                    wait_time = self.traffic_controller.exponential_backoff(retry_count)
                    print(f"[指数退避] 第{retry_count}次重试，等待 {wait_time:.1f} 秒...")
                    print("(按 Ctrl+C 可中断)")
                    time.sleep(wait_time)
                
                if use_session:
                    session = self.session_manager.get_session(self.ua_generator)
                else:
                    session = requests.Session()
                
                if is_api:
                    headers = RequestHeaderGenerator.generate_api_headers(self.ua_generator, referer)
                else:
                    headers = RequestHeaderGenerator.generate_complete_headers(self.ua_generator)
                
                session.headers.update(headers)
                
                proxies = None
                if use_proxy:
                    proxy = self.proxy_pool.get_proxy()
                    if proxy:
                        proxies = proxy
                
                # 记录请求开始时间用于蜜罐检测
                request_start_time = time.time()
                
                response = session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data if method == 'POST' else None,
                    data=data if method == 'POST' and isinstance(data, dict) else None,
                    proxies=proxies,
                    timeout=timeout,
                    allow_redirects=True
                )
                
                # 蜜罐检测
                if self._detect_honeypot(response, request_start_time, url):
                    print("   🔄 正在切换代理并重试...")
                    if proxies:
                        # 标记为蜜罐陷阱，加重惩罚
                        self.proxy_pool.remove_bad_proxy(proxies, is_honeypot=True)
                    self.proxy_pool.refresh_proxies()
                    retry_count += 1
                    last_exception = Exception("检测到蜜罐陷阱")
                    continue
                
                if response.status_code == 200:
                    # 重置蜜罐计数器（成功请求）
                    self.honeypot_suspicious_count = max(0, self.honeypot_suspicious_count - 1)
                    
                    # 恢复IP信誉（成功请求）
                    if proxies:
                        proxy_url = proxies.get('http', '')
                        self.proxy_pool.restore_ip_reputation(proxy_url)
                    
                    return response
                elif response.status_code in [403, 429, 503]:
                    print(f"[反爬检测] 遇到状态码 {response.status_code}，准备重试...")
                    if response.status_code == 403 and proxies:
                        self.proxy_pool.remove_bad_proxy(proxies)
                    # 强制刷新代理池，获取新IP
                    self.proxy_pool.refresh_proxies()
                    retry_count += 1
                    last_exception = Exception(f"HTTP {response.status_code}")
                    continue
                else:
                    response.raise_for_status()
                
            except requests.exceptions.ProxyError as e:
                print(f"[代理错误] {str(e)}")
                if proxies:
                    self.proxy_pool.remove_bad_proxy(proxies)
                # 强制刷新代理池
                self.proxy_pool.refresh_proxies()
                retry_count += 1
                last_exception = e
                continue
                
            except requests.exceptions.Timeout as e:
                print(f"[超时错误] {str(e)}")
                retry_count += 1
                last_exception = e
                continue
                
            except requests.exceptions.ConnectionError as e:
                print(f"[连接错误] {str(e)}")
                # 连接错误可能是代理问题，尝试移除当前代理
                if proxies:
                    self.proxy_pool.remove_bad_proxy(proxies)
                    print("已移除失效代理，准备刷新代理池...")
                
                # 强制刷新代理池，获取新IP
                refresh_success = self.proxy_pool.refresh_proxies()
                if not refresh_success:
                    print("警告: 代理池刷新失败，将尝试不使用代理")
                    # 如果刷新失败，下次重试时不使用代理
                    use_proxy = False
                
                retry_count += 1
                last_exception = e
                continue
                
            except KeyboardInterrupt:
                print("\n\n⚠️  用户中断请求")
                print(f"已重试 {retry_count} 次，正在退出...")
                raise
            
            except Exception as e:
                print(f"[请求异常] {str(e)}")
                retry_count += 1
                last_exception = e
                continue
        
        raise Exception(f"请求失败，已达到最大重试次数: {last_exception}")
    
    def get_fingerprint_info(self) -> Dict:
        """获取当前指纹信息"""
        return {
            'canvas_fingerprint': self.canvas_fp,
            'webgl_fingerprint': self.webgl_fp,
            'screen_resolution': self.screen_res,
            'timezone': self.timezone,
            'user_agent': self.ua_generator.random,
        }
