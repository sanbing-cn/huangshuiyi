// ==UserScript==
// @name         东方财富股票数据抓取器
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  从东方财富网获取股票数据并导出为JSON格式，支持批量抓取和历史K线数据
// @author       StockCrawler
// @match        https://www.eastmoney.com/*
// @match        https://quote.eastmoney.com/*
// @match        http://push2.eastmoney.com/*
// @match        https://push2.eastmoney.com/*
// @match        http://push2his.eastmoney.com/*
// @match        https://push2his.eastmoney.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_download
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addStyle
// @grant        GM_deleteValue
// @connect      eastmoney.com
// @connect      *.eastmoney.com
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ==================== 配置区域 ====================
    const CONFIG = {
        // 请求延迟（毫秒）— 模拟正常用户行为
        MIN_DELAY: 1500,
        MAX_DELAY: 3000,
        
        // 批量抓取时每只股票的间隔时间（毫秒）
        BATCH_DELAY: 2000,
        
        // 每N只股票后的额外休息时间（毫秒）
        REST_INTERVAL: 20,  // 每20只股票休息
        REST_MIN_DELAY: 15000,  // 最少休息15秒
        REST_MAX_DELAY: 30000,  // 最多休息30秒
        
        // 每N只股票的大休息（防止长期封禁）
        MEGA_REST_INTERVAL: 50,
        MEGA_REST_MIN: 180000,  // 最少休悤3分钟
        MEGA_REST_MAX: 300000,  // 最多休悤5分钟
        
        // 是否启用自动重试
        ENABLE_RETRY: true,
        MAX_RETRIES: 3,
        
        // 默认获取天数
        DEFAULT_DAYS: 30,
        
        // API基础URL（优先HTTPS，失败自动降级HTTP）
        API_BASE: {
            STOCK_LIST: 'push2.eastmoney.com/api/qt/clist/get',
            KLINE_DATA: 'push2his.eastmoney.com/api/qt/stock/kline/get',
            REALTIME: 'push2.eastmoney.com/api/qt/stock/get'
        },
        // 协议缓存：首次请求后记住哪个协议可用
        _protocolCache: {}
    };

    // ==================== 持久化存储 ====================

    /**
     * 保存数据到 Tampermonkey 存储（自动分片，防止超出大小限制）
     */
    function saveToStorage(key, data) {
        try {
            const json = JSON.stringify(data);
            // Tampermonkey 存储单个值有大小限制，分片存储
            const CHUNK_SIZE = 500000; // 每片约500KB
            if (json.length > CHUNK_SIZE) {
                const totalChunks = Math.ceil(json.length / CHUNK_SIZE);
                GM_setValue(key + '_chunks', totalChunks);
                for (let i = 0; i < totalChunks; i++) {
                    GM_setValue(key + '_chunk_' + i, json.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE));
                }
                console.log(`[存储] ${key}: 分 ${totalChunks} 片保存，总大小 ${json.length} 字节`);
            } else {
                GM_setValue(key, json);
                GM_setValue(key + '_chunks', 0); // 标记非分片
            }
            return true;
        } catch (e) {
            console.error('[存储] 保存失败:', key, e);
            return false;
        }
    }

    /**
     * 从 Tampermonkey 存储读取数据
     */
    function loadFromStorage(key, defaultValue) {
        try {
            const chunks = GM_getValue(key + '_chunks', 0);
            let json;
            if (chunks > 0) {
                // 分片读取
                let parts = [];
                for (let i = 0; i < chunks; i++) {
                    parts.push(GM_getValue(key + '_chunk_' + i, ''));
                }
                json = parts.join('');
            } else {
                json = GM_getValue(key, null);
            }
            if (json === null || json === undefined) return defaultValue;
            return JSON.parse(json);
        } catch (e) {
            console.error('[存储] 读取失败:', key, e);
            return defaultValue;
        }
    }

    /**
     * 清除指定 key 的存储
     */
    function clearStorage(key) {
        try {
            const chunks = GM_getValue(key + '_chunks', 0);
            if (chunks > 0) {
                for (let i = 0; i < chunks; i++) {
                    GM_deleteValue(key + '_chunk_' + i);
                }
            }
            GM_deleteValue(key);
            GM_deleteValue(key + '_chunks');
        } catch (e) {
            console.error('[存储] 清除失败:', key, e);
        }
    }

    // 存储键名常量
    const STORAGE_KEYS = {
        STOCK_LIST: 'spark_stock_list',
        FETCHED_DATA: 'spark_fetched_data',
        BATCH_PROGRESS: 'spark_batch_progress',  // { lastIndex, stockCode, total, days }
        IS_RUNNING: 'spark_is_running'
    };

    // ==================== 工具函数 ====================
    
    /**
     * 随机延迟函数
     */
    function randomDelay(min, max) {
        return new Promise(resolve => {
            const delay = Math.floor(Math.random() * (max - min + 1)) + min;
            setTimeout(resolve, delay);
        });
    }

    /**
     * 获取市场前缀
     */
    function getMarketPrefix(stockCode) {
        if (stockCode.startsWith('6') || stockCode.startsWith('9')) {
            return '1'; // 上海
        } else if (stockCode.startsWith('0') || stockCode.startsWith('3')) {
            return '0'; // 深圳
        } else if (stockCode.startsWith('4') || stockCode.startsWith('8')) {
            return '0'; // 北交所（也走深圳接口）
        }
        return '0';
    }

    /**
     * 生成secid
     */
    function generateSecId(stockCode) {
        const market = getMarketPrefix(stockCode);
        return `${market}.${stockCode}`;
    }

    /**
     * 显示通知消息
     */
    function showNotification(message, type = 'info') {
        const colors = {
            info: '#3498db',
            success: '#2ecc71',
            warning: '#f39c12',
            error: '#e74c3c'
        };
        
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type]};
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999999;
            font-size: 14px;
            max-width: 400px;
            animation: slideIn 0.3s ease-out;
        `;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // ==================== 核心功能 ====================

    /**
     * 解析API响应（自动处理JSONP和纯JSON）
     */
    function parseApiResponse(responseText) {
        let text = responseText.trim();
        // 处理JSONP格式: jQuery112304xxx_16xxx({...}) 或 callback({...})
        const jsonpMatch = text.match(/^[a-zA-Z_$][\w$]*\(([\s\S]+)\);?$/);
        if (jsonpMatch) {
            text = jsonpMatch[1];
        }
        return JSON.parse(text);
    }

    /**
     * 调试：直接测试股票列表API
     */
    async function debugStockListApi() {
        const testUrls = [
            // 方式1: 全A股
            'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81&fields=f12,f58',
            // 方式2: 仅沪市
            'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:1+t:2,m:1+t:23&fields=f12,f58',
            // 方式3: 仅深市
            'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80&fields=f12,f58',
            // 方式4: HTTP
            'http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81&fields=f12,f58'
        ];
        const labels = ['全A股(HTTPS)', '仅沪市(HTTPS)', '仅深市(HTTPS)', '全A股(HTTP)'];
        let results = [];
        
        for (let i = 0; i < testUrls.length; i++) {
            updateStatus(`调试API: ${labels[i]}...`);
            try {
                const resp = await new Promise((resolve, reject) => {
                    GM_xmlhttpRequest({
                        method: 'GET', url: testUrls[i], timeout: 15000,
                        onload: resolve, onerror: reject, ontimeout: () => reject('timeout')
                    });
                });
                const text = resp.responseText || '';
                let total = '?', itemCount = '?', firstItems = '';
                try {
                    let jsonText = text.trim();
                    const m = jsonText.match(/^[a-zA-Z_$][\w$]*\(([\s\S]+)\);?$/);
                    if (m) jsonText = m[1];
                    const data = JSON.parse(jsonText);
                    total = data.data ? data.data.total : 'no data';
                    const diff = data.data ? data.data.diff : null;
                    if (diff) {
                        const arr = Array.isArray(diff) ? diff : Object.values(diff);
                        itemCount = arr.length;
                        firstItems = arr.slice(0, 3).map(x => x.f12 + ':' + x.f58).join(', ');
                    }
                } catch(e) { /* ignore */ }
                results.push(`${labels[i]}:\n  status=${resp.status}, total=${total}, items=${itemCount}\n  前100字符: ${text.substring(0, 100)}\n  示例: ${firstItems}`);
            } catch(e) {
                results.push(`${labels[i]}:\n  ❌ 失败: ${e.error || e.message || e}`);
            }
            await randomDelay(500, 1000);
        }
        
        const report = '=== API调试报告 ===\n\n' + results.join('\n\n');
        updateStatus('API调试完成');
        console.log(report);
        alert(report);
    }

    /**
     * 发起API请求的通用函数（自动尝试 HTTPS → HTTP）
     */
    function apiRequest(urlPath, timeout = 30000) {
        // 确定完整URL：根据协议缓存决定先用哪个
        let fullUrl;
        if (urlPath.startsWith('http://') || urlPath.startsWith('https://')) {
            fullUrl = urlPath;
        } else {
            // 从路径中提取域名作为缓存key
            const host = urlPath.split('/')[0];
            const cachedProto = CONFIG._protocolCache[host];
            const proto = cachedProto || 'https';
            fullUrl = proto + '://' + urlPath;
        }
        
        return new Promise((resolve, reject) => {
            console.log(`[API] 请求: ${fullUrl}`);
            GM_xmlhttpRequest({
                method: 'GET',
                url: fullUrl,
                timeout: timeout,
                onload: function(resp) {
                    if (resp.status >= 200 && resp.status < 300) {
                        // 记住成功的协议
                        const host = fullUrl.replace(/^https?:\/\//, '').split('/')[0];
                        CONFIG._protocolCache[host] = fullUrl.startsWith('https') ? 'https' : 'http';
                        console.log(`[API] 成功: ${fullUrl} (status=${resp.status})`);
                        resolve(resp);
                    } else if (resp.status === 0) {
                        // status=0 通常是协议不可用，尝试降级
                        const fallbackUrl = fullUrl.startsWith('https') 
                            ? fullUrl.replace('https://', 'http://') 
                            : fullUrl.replace('http://', 'https://');
                        console.warn(`[API] ${fullUrl} 返回 status=0，尝试 ${fallbackUrl}`);
                        GM_xmlhttpRequest({
                            method: 'GET',
                            url: fallbackUrl,
                            timeout: timeout,
                            onload: function(resp2) {
                                if (resp2.status >= 200 && resp2.status < 300) {
                                    const host = fallbackUrl.replace(/^https?:\/\//, '').split('/')[0];
                                    CONFIG._protocolCache[host] = fallbackUrl.startsWith('https') ? 'https' : 'http';
                                    console.log(`[API] 降级成功: ${fallbackUrl}`);
                                    resolve(resp2);
                                } else {
                                    reject(new Error(`HTTP ${resp2.status}: ${resp2.statusText || '未知错误'}`));
                                }
                            },
                            onerror: function(err2) {
                                console.error(`[API] 完全失败: ${fullUrl} 和 ${fallbackUrl} 均无法连接`);
                                reject(new Error(`网络请求失败: ${err2.error || err2.message || 'HTTPS和HTTP均无法连接'} (当前页面: ${location.protocol}//${location.hostname})`));
                            },
                            ontimeout: function() {
                                reject(new Error('请求超时 (' + timeout/1000 + '秒)'));
                            }
                        });
                    } else {
                        reject(new Error(`HTTP ${resp.status}: ${resp.statusText || '未知错误'}`));
                    }
                },
                onerror: function(err) {
                    // onerror 也可能是协议问题，尝试降级
                    const fallbackUrl = fullUrl.startsWith('https') 
                        ? fullUrl.replace('https://', 'http://') 
                        : fullUrl.replace('http://', 'https://');
                    console.warn(`[API] ${fullUrl} 请求失败，尝试 ${fallbackUrl}`);
                    GM_xmlhttpRequest({
                        method: 'GET',
                        url: fallbackUrl,
                        timeout: timeout,
                        onload: function(resp2) {
                            if (resp2.status >= 200 && resp2.status < 300) {
                                const host = fallbackUrl.replace(/^https?:\/\//, '').split('/')[0];
                                CONFIG._protocolCache[host] = fallbackUrl.startsWith('https') ? 'https' : 'http';
                                console.log(`[API] 降级成功: ${fallbackUrl}`);
                                resolve(resp2);
                            } else {
                                reject(new Error(`网络请求失败: HTTPS和HTTP均失败 (${err.error || err.message || '未知'})`));
                            }
                        },
                        onerror: function(err2) {
                            console.error(`[API] 完全失败: ${fullUrl} 和 ${fallbackUrl} 均无法连接`);
                            console.error(`[API] 错误详情:`, { originalError: err, fallbackError: err2, currentPage: location.href });
                            reject(new Error(`网络请求失败: HTTPS和HTTP均无法连接 (原始错误: ${err.error || err.message || '未知'}, 备用错误: ${err2.error || err2.message || '未知'})`));
                        },
                        ontimeout: function() {
                            reject(new Error('请求超时 (' + timeout/1000 + '秒)'));
                        }
                    });
                },
                ontimeout: function() {
                    reject(new Error('请求超时 (' + timeout/1000 + '秒)'));
                }
            });
        });
    }

    /**
     * 获取股票列表（支持分页，覆盖全部A股市场）
     */
    async function fetchStockList(market = 'all') {
        const stocks = [];
        
        // 定义各市场的 fs 过滤条件
        const marketFilters = {
            sh: [{ fs: 'm:1 t:2,m:1 t:23', label: '上交所(主板+科创板)' }],
            sz: [{ fs: 'm:0 t:6,m:0 t:80', label: '深交所(主板+创业板)' }],
            bj: [{ fs: 'm:0 t:81', label: '北交所' }]
        };
        
        // 根据用户选择确定要抓取的市场
        let filtersToFetch = [];
        if (market === 'all') {
            filtersToFetch = [...marketFilters.sh, ...marketFilters.sz, ...marketFilters.bj];
        } else if (marketFilters[market]) {
            filtersToFetch = marketFilters[market];
        } else {
            filtersToFetch = [...marketFilters.sh, ...marketFilters.sz, ...marketFilters.bj];
        }
        
        try {
            showNotification('正在获取股票列表...', 'info');
            
            for (const filter of filtersToFetch) {
                let page = 1;
                let totalPages = 1;
                const pageSize = 5000;
                let marketCount = 0;
                
                while (page <= totalPages) {
                    const params = {
                        pn: String(page),
                        pz: String(pageSize),
                        po: '1',
                        np: '1',
                        ut: 'bd1d9ddb04089700cf9c27f6f7426281',
                        fltt: '2',
                        invt: '2',
                        fid: 'f3',
                        fs: filter.fs,
                        fields: 'f12,f58',
                        wbp2u: '|0|0|0|web'
                    };
                    
                    const url = CONFIG.API_BASE.STOCK_LIST + '?' + 
                        Object.entries(params).map(([k, v]) => `${k}=${v}`).join('&');
                    
                    await randomDelay(500, 1500);
                    
                    const response = await apiRequest(url);
                    
                    let data;
                    try {
                        data = parseApiResponse(response.responseText);
                    } catch (parseErr) {
                        console.error(`[${filter.label}] 响应解析失败，原始响应前200字符:`, response.responseText.substring(0, 200));
                        throw new Error(`${filter.label} 数据格式异常: ${parseErr.message}`);
                    }
                    
                    if (data.data && data.data.diff) {
                        const items = Array.isArray(data.data.diff) ? data.data.diff : Object.values(data.data.diff);
                        const total = data.data.total || items.length;
                        
                        totalPages = Math.ceil(total / pageSize);
                        
                        items.forEach(item => {
                            const code = item.f12;
                            let stockMarket = 'sz';
                            if (code.startsWith('6') || code.startsWith('9')) stockMarket = 'sh';
                            else if (code.startsWith('4') || code.startsWith('8')) stockMarket = 'bj';
                            
                            stocks.push({
                                code: code,
                                name: item.f58,
                                market: stockMarket
                            });
                        });
                        
                        marketCount += items.length;
                        console.log(`[${filter.label}] 第${page}/${totalPages}页，本页${items.length}只，API总数${total}`);
                        
                        if (page === 1 && total > pageSize) {
                            updateStatus(`${filter.label} 共${total}只，分${totalPages}页获取...`);
                        }
                    } else {
                        console.warn(`[${filter.label}] 第${page}页无数据`, data);
                        break;
                    }
                    
                    page++;
                }
                
                console.log(`[${filter.label}] 完成，共获取 ${marketCount} 只`);
            }
            
            showNotification(`成功获取 ${stocks.length} 只股票`, 'success');
            updateStatus(`股票列表: ${stocks.length} 只 (上交所${stocks.filter(s=>s.market==='sh').length} + 深交所${stocks.filter(s=>s.market==='sz').length} + 北交所${stocks.filter(s=>s.market==='bj').length})`);
            return stocks;
            
        } catch (error) {
            console.error('获取股票列表失败:', error);
            const errorMsg = error.message || '未知错误';
            let suggestion = '';
            
            if (errorMsg.includes('HTTPS和HTTP均无法连接')) {
                suggestion = '\n\n可能原因：\n' +
                    '1. 当前页面不是东方财富网站（需要在 www.eastmoney.com 或 quote.eastmoney.com 运行）\n' +
                    '2. Tampermonkey 权限未正确配置\n' +
                    '3. 网络连接问题或被防火墙拦截\n' +
                    '4. 浏览器安全策略限制\n\n' +
                    '建议：点击“🧪 连接诊断”按钮检查详细问题';
            }
            
            showNotification('获取股票列表失败: ' + errorMsg + suggestion, 'error');
            updateStatus('❌ 获取失败: ' + errorMsg);
            return stocks;
        }
    }

    /**
     * 检测是否为限流/被封响应
     */
    function isRateLimited(responseText) {
        try {
            const data = JSON.parse(responseText);
            // 东方财富限流时通常返回 rc=50 或 data 为 null 且 rc 非 0
            if (data.rc !== undefined && data.rc !== 0) return true;
            if (data.retcode !== undefined && data.retcode !== 0) return true;
            return false;
        } catch (e) {
            // 非 JSON 响应（如 HTML 验证码页面）也算限流
            if (responseText.includes('验证码') || responseText.includes('频繁')) return true;
            return false;
        }
    }

    /**
     * 获取单只股票的K线数据
     */
    async function fetchStockKLine(stockCode, days = 30, retryCount = 0) {
        try {
            const secid = generateSecId(stockCode);
            const endDate = new Date();
            const startDate = new Date();
            startDate.setDate(startDate.getDate() - days);
            
            const beg = startDate.toISOString().slice(0, 10).replace(/-/g, '');
            const end = endDate.toISOString().slice(0, 10).replace(/-/g, '');
            
            const params = {
                secid: secid,
                fields1: 'f1,f2,f3,f4,f5,f6',
                fields2: 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                klt: '101', // 日K线
                fqt: '1',   // 前复权
                beg: beg,
                end: end,
                smplmt: '100000',
                lmt: '1000000'
            };
            
            const url = CONFIG.API_BASE.KLINE_DATA + '?' + 
                Object.entries(params).map(([k, v]) => `${k}=${v}`).join('&');
            
            await randomDelay(CONFIG.MIN_DELAY, CONFIG.MAX_DELAY);
            
            const response = await apiRequest(url);
            
            // 检测限流
            if (isRateLimited(response.responseText)) {
                if (retryCount < CONFIG.MAX_RETRIES) {
                    const backoff = (retryCount + 1) * 15000 + Math.random() * 10000;
                    showNotification(`股票 ${stockCode} 触发限流，等待 ${Math.round(backoff/1000)} 秒后重试 (${retryCount+1}/${CONFIG.MAX_RETRIES})`, 'warning');
                    console.warn(`[限流] 股票 ${stockCode}，退避 ${Math.round(backoff/1000)} 秒`);
                    await randomDelay(backoff, backoff + 5000);
                    return fetchStockKLine(stockCode, days, retryCount + 1);
                } else {
                    showNotification(`股票 ${stockCode} 重试 ${CONFIG.MAX_RETRIES} 次仍被限流，跳过`, 'error');
                    return [];
                }
            }
            
            let data;
            try {
                data = parseApiResponse(response.responseText);
            } catch (parseErr) {
                console.error(`股票 ${stockCode} 响应解析失败:`, response.responseText.substring(0, 200));
                if (retryCount < CONFIG.MAX_RETRIES) {
                    await randomDelay(5000, 10000);
                    return fetchStockKLine(stockCode, days, retryCount + 1);
                }
                return [];
            }
            
            if (!data.data || !data.data.klines) {
                console.warn(`股票 ${stockCode} 无数据`);
                return [];
            }
            
            const stockName = data.data.name || '';
            const klines = data.data.klines;
            const parsedData = [];
            
            klines.forEach(line => {
                const fields = line.split(',');
                if (fields.length >= 6) {
                    parsedData.push({
                        日期: fields[0],
                        开盘价: parseFloat(fields[1]),
                        收盘价: parseFloat(fields[2]),
                        最高价: parseFloat(fields[3]),
                        最低价: parseFloat(fields[4]),
                        成交量: parseInt(fields[5]),
                        成交额: parseFloat(fields[6]) || 0,
                        涨跌幅: parseFloat(fields[7]) || 0,
                        换手率: parseFloat(fields[8]) || 0,
                        股票代码: stockCode,
                        股票名称: stockName
                    });
                }
            });
            
            console.log(`成功获取股票 ${stockCode} (${stockName}) 的 ${parsedData.length} 条数据`);
            return parsedData;
            
        } catch (error) {
            // 网络错误重试（增大退避时间，避免IP封禁后快速重试浪费机会）
            if (retryCount < CONFIG.MAX_RETRIES) {
                const backoff = (retryCount + 1) * 30000 + Math.random() * 15000;
                showNotification(`股票 ${stockCode} 请求失败，${Math.round(backoff/1000)} 秒后重试 (${retryCount+1}/${CONFIG.MAX_RETRIES})`, 'warning');
                await randomDelay(backoff, backoff + 10000);
                return fetchStockKLine(stockCode, days, retryCount + 1);
            }
            console.error(`获取股票 ${stockCode} 数据失败:`, error);
            return [];
        }
    }

    /**
     * 批量获取多只股票数据（支持断点续传 + 持久化）
     */
    async function batchFetchStocks(stockCodes, days = 30, limit = null, resumeFrom = 0) {
        const allData = [];
        let successCount = 0;
        let failCount = 0;
        let consecutiveFailCount = 0; // 连续失败计数
        let adaptiveDelayMultiplier = 1; // 自适应延迟倍数
        
        // 根据天数自动调整节奏（天数越大，响应越大，越容易限流）
        const paceFactor = Math.max(1, Math.ceil(days / 30)); // 30天=1x, 60天=2x, 365天=13x
        const adjustedBatchDelay = CONFIG.BATCH_DELAY * Math.min(paceFactor, 4); // 最高4倍
        const adjustedRestInterval = Math.max(10, Math.floor(CONFIG.REST_INTERVAL / Math.min(paceFactor, 3)));
        const adjustedMegaInterval = Math.max(25, Math.floor(CONFIG.MEGA_REST_INTERVAL / Math.min(paceFactor, 3)));
        
        const codesToFetch = limit ? stockCodes.slice(0, limit) : stockCodes;
        const startIndex = resumeFrom;
        
        showNotification(`开始批量抓取（从第${startIndex+1}只开始，共${codesToFetch.length}只，${days}天数据，节奏${paceFactor}x）`, 'info');
        updateStatus(`从第${startIndex+1}只继续，间隔${Math.round(adjustedBatchDelay/1000)}秒，每${adjustedRestInterval}只小休，每${adjustedMegaInterval}只大休`);
        
        // 标记运行状态
        GM_setValue(STORAGE_KEYS.IS_RUNNING, true);
        
        for (let i = startIndex; i < codesToFetch.length; i++) {
            const stock = typeof codesToFetch[i] === 'string' ? 
                { code: codesToFetch[i], name: '' } : codesToFetch[i];
            
            try {
                const progressPct = Math.round((i + 1) / codesToFetch.length * 100);
                console.log(`[${i + 1}/${codesToFetch.length} ${progressPct}%] 抓取: ${stock.code} ${stock.name}`);
                updateStatus(`[${i + 1}/${codesToFetch.length} ${progressPct}%] ${stock.code} ${stock.name}`);
                
                const data = await fetchStockKLine(stock.code, days);
                
                if (data.length > 0) {
                    allData.push(...data);
                    successCount++;
                    consecutiveFailCount = 0;
                    // 成功时逐渐降低自适应延迟
                    adaptiveDelayMultiplier = Math.max(1, adaptiveDelayMultiplier * 0.9);
                    
                    // 每成功5只股票，持久化一次数据
                    if (successCount % 5 === 0) {
                        saveToStorage(STORAGE_KEYS.FETCHED_DATA, allData);
                        GM_setValue(STORAGE_KEYS.BATCH_PROGRESS, {
                            lastIndex: i,
                            stockCode: stock.code,
                            total: codesToFetch.length,
                            days: days,
                            successCount: successCount,
                            failCount: failCount,
                            timestamp: new Date().toISOString()
                        });
                    }
                } else {
                    failCount++;
                    consecutiveFailCount++;
                    // 失败时增加自适应延迟（最高5倍）
                    adaptiveDelayMultiplier = Math.min(5, adaptiveDelayMultiplier * 1.5);
                }
                
                // 连续失败超过3次，触发冷却休息
                if (consecutiveFailCount >= 3) {
                    const cooldown = (90 + Math.random() * 60) * 1000; // 90-150秒
                    showNotification(`连续失败${consecutiveFailCount}次，冷却${Math.round(cooldown/1000)}秒...`, 'warning');
                    updateStatus(`⚠️ 被限流，冷却${Math.round(cooldown/1000)}秒...`);
                    // 冷却前持久化
                    saveToStorage(STORAGE_KEYS.FETCHED_DATA, allData);
                    GM_setValue(STORAGE_KEYS.BATCH_PROGRESS, {
                        lastIndex: i, stockCode: stock.code, total: codesToFetch.length,
                        days: days, successCount: successCount, failCount: failCount,
                        timestamp: new Date().toISOString()
                    });
                    await randomDelay(cooldown, cooldown + 30000);
                    consecutiveFailCount = 0;
                    adaptiveDelayMultiplier = 2; // 冷却后仍保持较高延迟
                }
                
                // 每只股票之间的延迟（包含自适应倍数 + 天数调节）
                if (i < codesToFetch.length - 1) {
                    const baseDelay = adjustedBatchDelay * adaptiveDelayMultiplier;
                    await randomDelay(baseDelay, baseDelay + 2000);
                }
                
                // 大休息
                if ((i + 1) % adjustedMegaInterval === 0) {
                    const megaRest = CONFIG.MEGA_REST_MIN + Math.random() * (CONFIG.MEGA_REST_MAX - CONFIG.MEGA_REST_MIN);
                    showNotification(`已抓取${i + 1}只，大休息${Math.round(megaRest/1000)}秒...`, 'warning');
                    updateStatus(`💤 已处理${i+1}只，大休息${Math.round(megaRest/1000)}秒`);
                    saveToStorage(STORAGE_KEYS.FETCHED_DATA, allData);
                    GM_setValue(STORAGE_KEYS.BATCH_PROGRESS, {
                        lastIndex: i, stockCode: stock.code, total: codesToFetch.length,
                        days: days, successCount: successCount, failCount: failCount,
                        timestamp: new Date().toISOString()
                    });
                    await randomDelay(megaRest, megaRest + 30000);
                    adaptiveDelayMultiplier = 1; // 大休息后重置延迟
                }
                // 小休息
                else if ((i + 1) % adjustedRestInterval === 0) {
                    const restDelay = CONFIG.REST_MIN_DELAY + Math.random() * (CONFIG.REST_MAX_DELAY - CONFIG.REST_MIN_DELAY);
                    showNotification(`已抓取${i + 1}只，休息${Math.round(restDelay/1000)}秒`, 'warning');
                    saveToStorage(STORAGE_KEYS.FETCHED_DATA, allData);
                    GM_setValue(STORAGE_KEYS.BATCH_PROGRESS, {
                        lastIndex: i, stockCode: stock.code, total: codesToFetch.length,
                        days: days, successCount: successCount, failCount: failCount,
                        timestamp: new Date().toISOString()
                    });
                    await randomDelay(restDelay, restDelay + 5000);
                }
                
            } catch (error) {
                console.error(`抓取股票 ${stock.code} 时出错:`, error);
                failCount++;
                consecutiveFailCount++;
                adaptiveDelayMultiplier = Math.min(5, adaptiveDelayMultiplier * 1.5);
            }
        }
        
        // 最终持久化
        saveToStorage(STORAGE_KEYS.FETCHED_DATA, allData);
        GM_setValue(STORAGE_KEYS.IS_RUNNING, false);
        GM_setValue(STORAGE_KEYS.BATCH_PROGRESS, null);
        
        showNotification(`批量抓取完成！成功: ${successCount}, 失败: ${failCount}, 共 ${allData.length} 条`, 'success');
        return allData;
    }

    /**
     * 导出数据为JSON文件
     */
    function exportToJSON(data, filename = 'stock_data.json') {
        const jsonStr = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showNotification(`数据已导出为 ${filename}`, 'success');
    }

    /**
     * 复制到剪贴板
     */
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification('数据已复制到剪贴板', 'success');
        }).catch(err => {
            console.error('复制失败:', err);
            showNotification('复制失败', 'error');
        });
    }

    // ==================== UI界面 ====================

    /**
     * 创建控制面板
     */
    function createControlPanel() {
        const panel = document.createElement('div');
        panel.id = 'stock-crawler-panel';
        panel.style.cssText = `
            position: fixed;
            top: 20px;
            left: 20px;
            width: 350px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.15);
            z-index: 999998;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            overflow: hidden;
        `;
        
        // 标题栏
        const header = document.createElement('div');
        header.style.cssText = `
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            font-size: 16px;
            font-weight: bold;
            cursor: move;
            display: flex;
            justify-content: space-between;
            align-items: center;
        `;
        header.innerHTML = `
            <span>📊 股票数据抓取器</span>
            <button id="toggle-panel" style="background: none; border: none; color: white; cursor: pointer; font-size: 20px;">−</button>
        `;
        
        // 内容区
        const content = document.createElement('div');
        content.id = 'panel-content';
        content.style.cssText = `
            padding: 20px;
            max-height: 500px;
            overflow-y: auto;
        `;
        
        content.innerHTML = `
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-weight: 500; color: #333;">市场选择:</label>
                <select id="market-select" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px;">
                    <option value="all">全部市场 (沪深京 ~5500只)</option>
                    <option value="sh">仅上海 (主板+科创板)</option>
                    <option value="sz">仅深圳 (主板+创业板)</option>
                    <option value="bj">仅北交所</option>
                </select>
            </div>
            
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-weight: 500; color: #333;">获取天数:</label>
                <input type="number" id="days-input" value="30" min="1" max="365" 
                       style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px;">
            </div>
            
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-weight: 500; color: #333;">限制数量 (可选):</label>
                <input type="number" id="limit-input" placeholder="不填则全部获取" min="1"
                       style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px;">
            </div>
            
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-weight: 500; color: #333;">自定义股票代码 (用逗号分隔):</label>
                <textarea id="custom-codes" rows="3" placeholder="例如: 600519,000001,300750"
                          style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 6px; resize: vertical;"></textarea>
            </div>
            
            <div style="display: grid; gap: 10px;">
                <button id="fetch-list-btn" 
                        style="padding: 10px; background: #3498db; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500;">
                    📋 获取股票列表
                </button>
                
                <button id="batch-fetch-btn" 
                        style="padding: 10px; background: #2ecc71; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500;">
                    🚀 批量抓取数据
                </button>
                
                <button id="export-json-btn" 
                        style="padding: 10px; background: #f39c12; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500;">
                    💾 导出JSON
                </button>
                
                <button id="clear-data-btn" 
                        style="padding: 10px; background: #e74c3c; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500;">
                    🗑️ 清空数据
                </button>
                
                <button id="test-conn-btn" 
                        style="padding: 10px; background: #9b59b6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500;">
                    🧪 连接诊断
                </button>
                
                <button id="debug-api-btn" 
                        style="padding: 10px; background: #e67e22; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500;">
                    🔍 API调试
                </button>
            </div>
            
            <div id="status-area" style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 6px; font-size: 12px; max-height: 150px; overflow-y: auto;">
                <div style="color: #666;">就绪状态...</div>
            </div>
        `;
        
        panel.appendChild(header);
        panel.appendChild(content);
        document.body.appendChild(panel);
        
        // 绑定事件
        bindPanelEvents();
        
        // 使面板可拖动
        makeDraggable(panel, header);
    }

    /**
     * 绑定面板事件
     */
    function bindPanelEvents() {
        // 从持久化存储恢复数据
        let cachedStockList = loadFromStorage(STORAGE_KEYS.STOCK_LIST, []);
        let fetchedData = loadFromStorage(STORAGE_KEYS.FETCHED_DATA, []);
        
        // 检查是否有未完成的批量任务
        const savedProgress = GM_getValue(STORAGE_KEYS.BATCH_PROGRESS, null);
        if (savedProgress && cachedStockList.length > 0) {
            updateStatus(`发现未完成任务：已抓取 ${savedProgress.successCount || '?'} 只，上次位置：${savedProgress.stockCode}（${savedProgress.timestamp}）`);
            showNotification(`发现上次未完成的抓取任务（第 ${savedProgress.lastIndex + 1} 只），可点击"批量抓取"继续`, 'warning');
        }
        if (fetchedData.length > 0) {
            updateStatus(`已恢复上次数据：${fetchedData.length} 条记录`);
        }
        if (cachedStockList.length > 0) {
            updateStatus(`已恢复股票列表：${cachedStockList.length} 只`);
        }
        
        // 获取股票列表
        document.getElementById('fetch-list-btn').addEventListener('click', async () => {
            const market = document.getElementById('market-select').value;
            updateStatus('正在获取股票列表...');
            cachedStockList = await fetchStockList(market);
            // 持久化保存股票列表
            saveToStorage(STORAGE_KEYS.STOCK_LIST, cachedStockList);
            updateStatus(`已获取 ${cachedStockList.length} 只股票（已保存）`);
        });
        
        // 批量抓取（支持断点续传）
        document.getElementById('batch-fetch-btn').addEventListener('click', async () => {
            const customCodes = document.getElementById('custom-codes').value.trim();
            const days = parseInt(document.getElementById('days-input').value) || 30;
            const limitInput = document.getElementById('limit-input').value.trim();
            const limit = limitInput ? parseInt(limitInput) : null;
            
            let stocksToFetch = [];
            
            if (customCodes) {
                stocksToFetch = customCodes.split(',').map(code => ({
                    code: code.trim(),
                    name: ''
                }));
                // 自定义代码时清除旧的续传进度
                GM_setValue(STORAGE_KEYS.BATCH_PROGRESS, null);
            } else if (cachedStockList.length > 0) {
                stocksToFetch = cachedStockList;
            } else {
                showNotification('请先获取股票列表或输入自定义代码', 'warning');
                return;
            }
            
            // 检查是否有可续传的进度
            const progress = GM_getValue(STORAGE_KEYS.BATCH_PROGRESS, null);
            let resumeFrom = 0;
            if (progress && !customCodes) {
                const confirmResume = confirm(
                    `发现上次未完成的抓取任务：\n` +
                    `• 已抓取到第 ${progress.lastIndex + 1}/${progress.total} 只（${progress.stockCode}）\n` +
                    `• 时间：${progress.timestamp}\n\n` +
                    `点击"确定"从断点继续，点击"取消"重新开始`
                );
                if (confirmResume) {
                    resumeFrom = progress.lastIndex + 1;
                    // 恢复之前已抓取的数据
                    const savedData = loadFromStorage(STORAGE_KEYS.FETCHED_DATA, []);
                    if (savedData.length > 0) {
                        fetchedData = savedData;
                        updateStatus(`已恢复 ${fetchedData.length} 条历史数据，从第 ${resumeFrom + 1} 只继续`);
                    }
                } else {
                    // 重新开始，清除旧进度和旧数据
                    GM_setValue(STORAGE_KEYS.BATCH_PROGRESS, null);
                    clearStorage(STORAGE_KEYS.FETCHED_DATA);
                    fetchedData = [];
                }
            }
            
            updateStatus('开始批量抓取...');
            const newData = await batchFetchStocks(stocksToFetch, days, limit, resumeFrom);
            // 合并数据（如果是续传，newData 只包含新抓的；否则替换）
            if (resumeFrom > 0) {
                fetchedData = [...fetchedData, ...newData];
            } else {
                fetchedData = newData;
            }
            // 最终持久化
            saveToStorage(STORAGE_KEYS.FETCHED_DATA, fetchedData);
            updateStatus(`抓取完成！共 ${fetchedData.length} 条数据（已保存）`);
        });
        
        // 导出JSON
        document.getElementById('export-json-btn').addEventListener('click', () => {
            if (fetchedData.length === 0) {
                // 尝试从存储恢复
                fetchedData = loadFromStorage(STORAGE_KEYS.FETCHED_DATA, []);
            }
            if (fetchedData.length === 0) {
                showNotification('没有可导出的数据', 'warning');
                return;
            }
            const timestamp = new Date().toISOString().slice(0, 10);
            exportToJSON(fetchedData, `stock_data_${timestamp}.json`);
        });
        
        // 清空数据
        document.getElementById('clear-data-btn').addEventListener('click', () => {
            cachedStockList = [];
            fetchedData = [];
            // 清除所有持久化数据
            clearStorage(STORAGE_KEYS.STOCK_LIST);
            clearStorage(STORAGE_KEYS.FETCHED_DATA);
            GM_setValue(STORAGE_KEYS.BATCH_PROGRESS, null);
            GM_setValue(STORAGE_KEYS.IS_RUNNING, false);
            updateStatus('数据已清空（含持久化存储）');
            showNotification('所有数据已清空', 'info');
        });
        
        // 连接诊断测试
        document.getElementById('test-conn-btn').addEventListener('click', async () => {
            updateStatus('🧪 开始连接诊断...');
            const testUrl = 'push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:1+t:2&fields=f12,f58';
            const protocols = ['https', 'http'];
            let results = [];
            
            for (const proto of protocols) {
                const fullUrl = proto + '://' + testUrl;
                updateStatus(`测试 ${proto}://push2.eastmoney.com ...`);
                try {
                    const resp = await new Promise((resolve, reject) => {
                        GM_xmlhttpRequest({
                            method: 'GET',
                            url: fullUrl,
                            timeout: 15000,
                            onload: resolve,
                            onerror: (err) => reject(err),
                            ontimeout: () => reject({ error: 'timeout' })
                        });
                    });
                    const status = resp.status;
                    const bodyLen = (resp.responseText || '').length;
                    const preview = (resp.responseText || '').substring(0, 80);
                    results.push(`✅ ${proto}: status=${status}, 响应${bodyLen}字节\n   ${preview}`);
                } catch (err) {
                    const errInfo = err.error || err.statusText || err.message || JSON.stringify(err);
                    results.push(`❌ ${proto}: ${errInfo}\n   详情: ${JSON.stringify(err)}`);
                }
            }
            
            // 测试 GM_xmlhttpRequest 是否可用
            let gmAvailable = 'unknown';
            try {
                const gmTest = await new Promise((resolve, reject) => {
                    GM_xmlhttpRequest({
                        method: 'GET',
                        url: 'https://www.baidu.com',
                        timeout: 10000,
                        onload: (r) => resolve(r.status),
                        onerror: (err) => reject(err),
                        ontimeout: () => reject('timeout')
                    });
                });
                gmAvailable = `正常 (百度 status=${gmTest})`;
            } catch (e) {
                gmAvailable = `异常: ${e.error || e.message || JSON.stringify(e)}`;
            }
            
            // 检查当前页面协议
            const currentProtocol = location.protocol;
            const currentHost = location.hostname;
            
            // 检查 Tampermonkey 权限
            let permissionsInfo = '';
            if (typeof GM_info !== 'undefined') {
                permissionsInfo = `Tampermonkey版本: ${GM_info.version || '未知'}\n`;
                permissionsInfo += `脚本UUID: ${GM_info.script.uuid || '无'}\n`;
                if (GM_info.scriptGrant) {
                    permissionsInfo += `已授权: ${GM_info.scriptGrant.join(', ')}`;
                }
            }
            
            const report = `=== 连接诊断报告 ===\n\n` +
                `当前页面: ${currentProtocol}//${currentHost}\n` +
                `完整URL: ${location.href.substring(0, 100)}\n\n` +
                `${permissionsInfo}\n\n` +
                `GM_xmlhttpRequest: ${gmAvailable}\n\n` +
                results.join('\n\n') + '\n\n' +
                `=== 建议解决方案 ===\n` +
                `1. 确保在东方财富网站运行此脚本（www.eastmoney.com 或 quote.eastmoney.com）\n` +
                `2. 如果所有测试都失败，尝试刷新页面后重试\n` +
                `3. 检查浏览器控制台(F12)查看详细错误日志\n` +
                `4. 确认 Tampermonkey 扩展已启用且脚本已激活\n` +
                `5. 尝试清除浏览器缓存和 Cookie`;
            
            updateStatus('诊断完成，查看详情');
            console.log(report);
            alert(report);
        });
        
        // API调试
        document.getElementById('debug-api-btn').addEventListener('click', () => {
            debugStockListApi();
        });
        
        // 折叠面板
        document.getElementById('toggle-panel').addEventListener('click', (e) => {
            const content = document.getElementById('panel-content');
            if (content.style.display === 'none') {
                content.style.display = 'block';
                e.target.textContent = '−';
            } else {
                content.style.display = 'none';
                e.target.textContent = '+';
            }
        });
    }

    /**
     * 更新状态区域
     */
    function updateStatus(message) {
        const statusArea = document.getElementById('status-area');
        if (statusArea) {
            const time = new Date().toLocaleTimeString();
            statusArea.innerHTML += `<div style="margin-top: 5px;">[${time}] ${message}</div>`;
            statusArea.scrollTop = statusArea.scrollHeight;
        }
    }

    /**
     * 使元素可拖动
     */
    function makeDraggable(element, handle) {
        let isDragging = false;
        let startX, startY, initialX, initialY;
        
        handle.addEventListener('mousedown', (e) => {
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            initialX = element.offsetLeft;
            initialY = element.offsetTop;
            e.preventDefault();
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            
            element.style.left = `${initialX + deltaX}px`;
            element.style.top = `${initialY + deltaY}px`;
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }

    // ==================== 初始化 ====================

    /**
     * 添加CSS动画
     */
    function addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(400px); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(400px); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 主初始化函数
     */
    function init() {
        console.log('东方财富股票数据抓取器已加载');
        addStyles();
        createControlPanel();
        showNotification('股票数据抓取器已启动！', 'success');
    }

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
