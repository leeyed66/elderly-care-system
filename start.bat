@echo off
chcp 65001 >nul
echo ==========================================
echo    智能老人远程监护系统
echo ==========================================
echo.

:: 检查Python版本
python --version 2>nul | findstr "3.13" >nul
if errorlevel 1 (
    echo [警告] 建议使用Python 3.13版本
    echo 当前版本:
    python --version
    echo.
)

:: 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo [1/4] 激活虚拟环境...
    call venv\Scripts\activate.bat
) else (
    echo [1/4] 虚拟环境不存在，使用系统Python
)

:: 检查依赖
echo [2/4] 检查依赖...
pip show ultralytics >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -r requirements.txt
)

:: 创建必要目录
echo [3/4] 创建必要目录...
if not exist "config\logs" mkdir config\logs
if not exist "config\data" mkdir config\data
if not exist "config\models" mkdir config\models

:: 启动系统
echo [4/4] 启动系统...
echo.
echo ==========================================
echo 系统启动中...
echo Web界面: http://localhost:5000
echo 按 Ctrl+C 停止系统
echo ==========================================
echo.

python main.py

echo.
echo 系统已停止
pause
