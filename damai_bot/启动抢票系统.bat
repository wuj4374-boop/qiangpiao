﻿﻿@echo off
chcp 65001 >nul 2>nul
title 大麦抢票系统
cd /d "%~dp0"

echo.
echo  ================================================================
echo.
echo                      免 责 声 明
echo                     DISCLAIMER NOTICE
echo.
echo  ================================================================
echo.
echo    软件名称: 大麦抢票系统
echo    作者印记: 小吴
echo    版本性质: 学习研究专用软件
echo.
echo  ---------------------------------------------------------------
echo.
echo    一、本软件为 Python + Playwright 自动化技术的 学习示例项目，
echo       仅供开发者学习 Web 自动化、浏览器控制、前后端交互等技术
echo       原理使用，严禁用于任何商业用途或非法用途。
echo.
echo    二、本软件不提供任何 ticket 抢购、代购、转售等服务，亦不
echo       保证任何 ticket 获取的成功率。使用者应自行承担使用本
echo       软件所产生的一切后果。
echo.
echo    三、使用者应遵守所在国家和地区的法律法规，以及相关平台的
echo       用户协议和服务条款。因使用本软件而产生的任何法律纠纷，
echo       由使用者自行承担全部责任，与本软件作者无关。
echo.
echo    四、本软件不收集、不存储、不传输任何用户个人信息及账号
echo       数据。所有登录凭据均保存在使用者本地设备，不会上传至
echo       任何第三方服务器。
echo.
echo    五、本软件按 "现状" 提供，不作任何明示或暗示的保证。作者
echo       不对软件的准确性、可靠性、完整性作任何承诺，亦不对因
echo       使用或无法使用本软件而造成的任何损失承担责任。
echo.
echo    六、本软件完全免费开源，任何以本软件名义进行收费、倒卖、
echo       二次分发的行为均与原作者无关。
echo.
echo  ---------------------------------------------------------------
echo.
echo    如您继续使用本软件，即表示您已完整阅读、理解并同意上述
echo    免责声明的全部内容。
echo.
echo  ================================================================
echo.
echo    作者: 小吴
echo    用途: 学习研究 / 技术交流
echo.
echo  ================================================================
echo.

:agree_prompt
set "USER_INPUT="
set /p "USER_INPUT=  请输入 agree 并按回车同意声明，输入其他内容退出: "

if /i "%USER_INPUT%"=="agree" (
    echo.
    echo  [√] 已同意免责声明，正在启动系统...
    echo.
    goto :start_system
)

echo.
echo  [×] 您未同意免责声明，程序即将退出。
echo.
pause
exit /b 0

:start_system
echo ========================================
echo   大麦抢票系统 - 一键启动
echo ========================================
echo.

:: -------------------------------------------------------
:: 1. 自动查找 Python
:: -------------------------------------------------------
set "PYTHON_CMD="

:: 优先使用 PATH 中的 python
python --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :found_python
)

:: 尝试 py 启动器
py --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    goto :found_python
)

:: 尝试常见 Anaconda 路径
if exist "%USERPROFILE%\anaconda3\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\anaconda3\python.exe"
    goto :found_python
)
if exist "%USERPROFILE%\miniconda3\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\miniconda3\python.exe"
    goto :found_python
)
if exist "D:\Anaconda\python.exe" (
    set "PYTHON_CMD=D:\Anaconda\python.exe"
    goto :found_python
)
if exist "D:\Anaconda3\python.exe" (
    set "PYTHON_CMD=D:\Anaconda3\python.exe"
    goto :found_python
)
if exist "C:\Anaconda3\python.exe" (
    set "PYTHON_CMD=C:\Anaconda3\python.exe"
    goto :found_python
)
if exist "C:\ProgramData\anaconda3\python.exe" (
    set "PYTHON_CMD=C:\ProgramData\anaconda3\python.exe"
    goto :found_python
)

:: 未找到 Python
echo [错误] 未找到 Python，请先安装 Python 3.8+
echo.
echo 下载地址: https://www.python.org/downloads/
echo 安装时请勾选 "Add Python to PATH"
echo.
pause
exit /b 1

:found_python
echo [√] 找到 Python: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

:: -------------------------------------------------------
:: 2. 设置 Playwright 浏览器路径（使用项目自带的浏览器）
:: -------------------------------------------------------
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0ms-playwright"
if exist "%PLAYWRIGHT_BROWSERS_PATH%\chromium-1208" (
    echo [√] 使用项目自带的 Chromium 浏览器
) else (
    echo [!] 未找到自带浏览器，Playwright 可能需要下载浏览器
)
echo.

:: -------------------------------------------------------
:: 3. 检查并安装依赖（使用清华镜像源）
:: -------------------------------------------------------
echo [i] 正在检查依赖...

%PYTHON_CMD% -c "import fastapi, uvicorn, jose, playwright" >nul 2>nul
if %errorlevel% neq 0 (
    echo [i] 正在安装依赖（使用清华镜像源，请稍候）...
    %PYTHON_CMD% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
    if %errorlevel% neq 0 (
        echo.
        echo [!] 依赖安装失败，请检查网络连接
        echo [!] 也可以手动执行: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo [√] 依赖安装完成
) else (
    echo [√] 依赖已就绪
)
echo.

:: -------------------------------------------------------
:: 4. 启动系统
:: -------------------------------------------------------
echo ========================================
echo   正在启动后端服务...
echo   启动后会自动打开浏览器
echo   按 Ctrl+C 可停止服务
echo ========================================
echo.

%PYTHON_CMD% start_web.py

echo.
echo 系统已停止。
pause
