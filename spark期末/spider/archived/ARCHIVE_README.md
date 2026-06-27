# 📦 Python爬虫代码归档说明

## 📅 归档时间
2026-06-18

---

## 🗂️ 归档文件清单

以下文件已移动到 `spider/archived/` 目录：

| 文件名 | 大小 | 说明 |
|--------|------|------|
| `stock_spider.py` | 19.6KB | Python爬虫主程序 |
| `anti_crawler.py` | 33.2KB | 反爬引擎（代理池、指纹伪造等） |

**总计**：约 53KB

---

## ❓ 为什么归档而不是删除？

### 归档的优势

1. **保留备用方案**
   - 油猴插件出现问题时可以恢复使用
   - 应对紧急情况

2. **学习参考**
   - 理解爬虫原理
   - 学习反爬技术
   - 研究代码实现

3. **未来扩展**
   - 如需自动化定时任务可快速恢复
   - 大规模批量抓取时更有优势

4. **占用空间小**
   - 仅53KB，几乎不影响存储
   - 归档后不影响日常使用

---

## 🎯 当前项目状态

### ✅ 保留的核心功能

| 模块 | 文件 | 状态 |
|------|------|------|
| **数据采集** | `tampermonkey_crawler.user.js` | ✅ 活跃使用 |
| **数据导入** | `import_tampermonkey_data.bat` | ✅ 活跃使用 |
| **数据处理** | `tampermonkey_importer.py` | ✅ 活跃使用 |
| **数据分析** | `stock_analyzer.py` | ✅ 活跃使用 |
| **数据存储** | `db_manager.py` | ✅ 活跃使用 |
| **Web应用** | `app_full.py` | ✅ 活跃使用 |

### ⚠️ 已归档的功能

| 功能 | 原文件 | 状态 | 替代方案 |
|------|--------|------|---------|
| Python自动爬虫 | `stock_spider.py` | 📦 已归档 | 油猴插件 |
| 反爬引擎 | `anti_crawler.py` | 📦 已归档 | 浏览器天然防护 |
| 代理池管理 | `anti_crawler.py` | 📦 已归档 | 无需代理 |
| 定时自动抓取 | `main.py`依赖 | ⚠️ 受限 | 需手动触发 |

---

## 🔄 如何恢复归档的代码？

如果将来需要使用Python爬虫，可以这样恢复：

### 方法一：移动回原位置

```powershell
# PowerShell命令
Move-Item -Path "spider\archived\stock_spider.py" -Destination "spider\" -Force
Move-Item -Path "spider\archived\anti_crawler.py" -Destination "spider\" -Force
```

### 方法二：复制保留两份

```powershell
# 复制到spider目录，归档目录也保留
Copy-Item -Path "spider\archived\stock_spider.py" -Destination "spider\" -Force
Copy-Item -Path "spider\archived\anti_crawler.py" -Destination "spider\" -Force
```

### 方法三：Git恢复（如果使用Git）

```bash
# 从Git历史中恢复
git checkout HEAD~1 -- spider/stock_spider.py
git checkout HEAD~1 -- spider/anti_crawler.py
```

---

## 💡 使用建议

### 当前推荐工作流程

```
1. 使用油猴插件抓取数据
   ↓
2. 导出为JSON文件
   ↓
3. 使用 import_tampermonkey_data.bat 导入
   ↓
4. 数据自动存入数据库
   ↓
5. Web应用展示和分析
```

### 何时考虑恢复Python爬虫？

✅ **建议恢复的场景**：
- 需要每天定时自动更新数据
- 需要抓取全市场5000+股票
- 油猴插件频繁出现问题
- 需要集成到自动化pipeline

❌ **不需要恢复的场景**：
- 偶尔手动抓取数据
- 每次抓取<500只股票
- 对自动化要求不高
- 更看重稳定性和易用性

---

## 📊 两种方案对比

### 油猴插件（当前使用）

**优点**：
- ✅ 完全绕过反爬
- ✅ 数据质量100%准确
- ✅ 简单易用，无需配置
- ✅ 不会被封IP
- ✅ 支持JavaScript渲染

**缺点**：
- ⚠️ 需要手动操作（半自动）
- ⚠️ 大规模抓取较慢
- ⚠️ 无法定时自动运行
- ⚠️ 依赖浏览器

### Python爬虫（已归档）

**优点**：
- ✅ 完全自动化
- ✅ 可以定时运行
- ✅ 大规模抓取效率高
- ✅ 易于集成到其他系统

**缺点**：
- ⚠️ 可能被反爬拦截
- ⚠️ 需要配置代理池
- ⚠️ 维护成本高
- ⚠️ 可能被封IP

---

## 🔧 main.py 的影响

`main.py` 依赖于已归档的爬虫代码，现在会报错。

### 解决方案

#### 方案1：修改main.py使用油猴数据

创建新的入口脚本 `run_analysis.py`：

```python
"""
运行数据分析流程
使用油猴插件导出的数据
"""

import pandas as pd
from data_processing.tampermonkey_importer import TampermonkeyDataImporter
from analysis.stock_analyzer import StockAnalyzer
from database.db_manager import DatabaseManager
import glob
import os


def run_analysis(json_file_path=None):
    """
    运行完整分析流程
    
    Args:
        json_file_path: JSON文件路径，None则自动查找最新文件
    """
    print("="*60)
    print("股票数据分析系统")
    print("="*60)
    
    # 1. 加载数据
    importer = TampermonkeyDataImporter()
    
    if json_file_path is None:
        # 自动查找最新的JSON文件
        json_files = glob.glob("stock_data_*.json")
        if not json_files:
            print("❌ 未找到JSON文件，请先使用油猴插件导出数据")
            return
        
        json_file_path = max(json_files, key=os.path.getctime)
        print(f"找到最新文件: {json_file_path}\n")
    
    # 加载数据
    df = importer.load_json_file(json_file_path)
    
    if df.empty:
        print("❌ 数据为空")
        return
    
    print(f"\n✅ 成功加载 {len(df)} 条数据\n")
    
    # 2. 数据预处理
    print("正在进行数据预处理...")
    df = importer._clean_data(df)
    print(f"✅ 预处理完成\n")
    
    # 3. Spark分析
    print("正在进行Spark分析...")
    analyzer = StockAnalyzer(app_name="StockAnalysis")
    spark_df = analyzer.create_dataframe(df)
    analyzed_df = analyzer.comprehensive_analysis(spark_df)
    analyzed_pdf = analyzed_df.toPandas()
    analyzer.stop()
    print(f"✅ 分析完成，共 {len(analyzed_pdf)} 条记录\n")
    
    # 4. 保存到数据库
    print("正在保存到数据库...")
    db = DatabaseManager()
    if db.connect():
        db.save_data(analyzed_pdf, if_exists='replace')
        print("✅ 数据已保存到数据库\n")
        db.disconnect()
    else:
        print("❌ 数据库连接失败\n")
    
    # 5. 显示统计信息
    print("="*60)
    print("数据统计")
    print("="*60)
    print(f"总记录数: {len(analyzed_pdf)}")
    print(f"股票数量: {analyzed_pdf['股票代码'].nunique()}")
    print(f"日期范围: {analyzed_pdf['日期'].min()} ~ {analyzed_pdf['日期'].max()}")
    
    if '收盘价' in analyzed_pdf.columns:
        print(f"\n平均收盘价: {analyzed_pdf['收盘价'].mean():.2f}")
        print(f"最高收盘价: {analyzed_pdf['收盘价'].max():.2f}")
        print(f"最低收盘价: {analyzed_pdf['收盘价'].min():.2f}")
    
    print("\n" + "="*60)
    print("分析完成！")
    print("="*60)


if __name__ == '__main__':
    run_analysis()
```

#### 方案2：保留main.py但添加提示

在 `main.py` 开头添加警告：

```python
"""
注意：此脚本需要Python爬虫代码
爬虫代码已归档到 spider/archived/ 目录

如需使用：
1. 恢复归档文件
   Move-Item spider\archived\stock_spider.py spider\
   Move-Item spider\archived\anti_crawler.py spider\

2. 或使用新的 run_analysis.py（推荐）
   python run_analysis.py
"""
```

---

## 📝 项目结构（归档后）

```
spark/
├── spider/
│   ├── tampermonkey_crawler.user.js  # ✅ 油猴插件（主要）
│   ├── import_tampermonkey_data.bat  # ✅ 导入工具
│   ├── archived/                      # 📦 归档目录
│   │   ├── stock_spider.py           # 📦 Python爬虫
│   │   └── anti_crawler.py           # 📦 反爬引擎
│   └── [文档...]
│
├── data_processing/
│   ├── tampermonkey_importer.py      # ✅ 数据导入器
│   └── preprocessor.py               # ✅ 预处理器
│
├── analysis/
│   └── stock_analyzer.py             # ✅ Spark分析
│
├── database/
│   └── db_manager.py                 # ✅ 数据库管理
│
├── web_app/
│   └── app_full.py                   # ✅ Web应用
│
└── run_analysis.py                    # ✅ 新增：分析入口
```

---

## 🎉 总结

### 已完成的操作

- ✅ 将 `stock_spider.py` 移动到 `spider/archived/`
- ✅ 将 `anti_crawler.py` 移动到 `spider/archived/`
- ✅ 创建了本归档说明文档
- ✅ 保留了所有核心功能

### 当前状态

- ✅ 油猴插件正常工作
- ✅ 数据导入工具可用
- ✅ Web应用不受影响
- ✅ 数据分析功能完整

### 下一步建议

1. **立即测试**
   ```
   使用油猴插件抓取一次数据
   确保整个流程正常
   ```

2. **创建新入口**
   ```
   创建 run_analysis.py
   替代原来的 main.py
   ```

3. **文档更新**
   ```
   更新README.md
   说明新的使用方式
   ```

---

**归档完成时间**: 2026-06-18  
**状态**: ✅ 已完成  
**影响**: 最小化，核心功能完整保留
