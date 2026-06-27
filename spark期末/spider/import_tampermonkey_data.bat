@echo off
chcp 65001 >nul
echo ========================================
echo   油猴插件数据导入工具
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python
    pause
    exit /b 1
)

echo [1/3] 正在查找JSON文件...
dir stock_data_*.json /b /o:d > temp_files.txt 2>nul

if not exist temp_files.txt (
    echo [提示] 未找到JSON文件
    echo.
    echo 请先使用油猴插件导出数据：
    echo   1. 访问东方财富网页面
    echo   2. 使用油猴插件抓取数据
    echo   3. 点击"导出JSON"按钮
    echo   4. 将下载的文件放到此目录
    echo.
    pause
    exit /b 1
)

set /p LATEST_FILE=<temp_files.txt
del temp_files.txt

echo [找到] %LATEST_FILE%
echo.

echo [2/3] 选择导入方式:
echo   1. 导入为CSV文件
echo   2. 导入为Excel文件
echo   3. 导入到数据库
echo   4. 查看数据统计
echo.
set /p CHOICE=请选择 (1-4): 

if "%CHOICE%"=="1" (
    echo.
    echo [3/3] 正在导入为CSV...
    python -c "from data_processing.tampermonkey_importer import quick_import; quick_import('%LATEST_FILE%', 'csv')"
) else if "%CHOICE%"=="2" (
    echo.
    echo [3/3] 正在导入为Excel...
    python -c "from data_processing.tampermonkey_importer import quick_import; quick_import('%LATEST_FILE%', 'excel')"
) else if "%CHOICE%"=="3" (
    echo.
    echo [3/3] 正在导入到数据库...
    python -c "from data_processing.tampermonkey_importer import quick_import; quick_import('%LATEST_FILE%', 'database')"
) else if "%CHOICE%"=="4" (
    echo.
    echo [3/3] 正在统计数据...
    python -c "from data_processing.tampermonkey_importer import TampermonkeyDataImporter; importer = TampermonkeyDataImporter(); df = importer.load_json_file('%LATEST_FILE%'); stats = importer.get_statistics(df); print('\n统计结果:'); import json; print(json.dumps(stats, ensure_ascii=False, indent=2))"
) else (
    echo [错误] 无效选择
    pause
    exit /b 1
)

echo.
echo ========================================
echo   导入完成！
echo ========================================
pause
