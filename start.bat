@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 🚀 启动 AI学习资料生成工作台...
echo ====================================
python backend\app.py
if %errorlevel% neq 0 (
    echo.
    echo ❌ 启动失败，请确认已安装依赖: pip install flask flask-cors
    pause
)
