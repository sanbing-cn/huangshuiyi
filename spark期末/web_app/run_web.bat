@echo off
echo ========================================
echo   Stock Data Visualization Web Service
echo ========================================
echo.

echo [1/2] Checking Flask dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo    Installing Flask and pymysql...
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple flask pymysql
) else (
    echo    Flask already installed
)

echo.
echo [2/2] Starting Web service...
echo ========================================
python app_full.py

pause
