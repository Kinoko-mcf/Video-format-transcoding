@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   视频格式转码工具 - 打包脚本
echo ========================================
echo.

:: ===== 检查 Python =====
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)
echo [1/5] Python 环境: OK

:: ===== 检查 FFmpeg =====
if not exist "ffmpeg\ffmpeg.exe" (
    echo [警告] 未找到 ffmpeg\ffmpeg.exe
    echo   请从以下地址下载 ffmpeg.exe 并放入 ffmpeg 目录:
    echo   https://www.gyan.dev/ffmpeg/builds/
    echo   （下载 "release essentials" 版本即可）
    echo.
    choice /c yn /m "是否继续打包（不包含 FFmpeg）？"
    if errorlevel 2 exit /b 1
) else (
    echo [2/5] FFmpeg: OK
)

:: ===== 安装依赖 =====
echo [3/5] 安装 Python 依赖...
pip install PyQt6>=6.5.0 pyinstaller>=6.0.0 -q
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo   依赖安装完成

:: ===== 清理旧构建 =====
echo [4/5] 清理旧构建文件...
if exist "build" rmdir /s /q "build"
if exist "dist\%APP_NAME%" rmdir /s /q "dist\视频格式转码工具"

:: ===== PyInstaller 打包 =====
echo [5/5] PyInstaller 打包中（请耐心等待）...
echo.
pyinstaller build.spec --noconfirm --clean

if %errorlevel% neq 0 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包成功！
echo   输出目录: dist\视频格式转码工具\
echo   可执行文件: dist\视频格式转码工具\VideoTranscoder.exe
echo ========================================

:: ===== 询问是否创建桌面快捷方式 =====
echo.
choice /c yn /m "是否创建桌面快捷方式？"
if errorlevel 2 goto :end

:: 创建快捷方式（使用 PowerShell）
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\视频格式转码工具.lnk"
set "TARGET_PATH=%~dp0dist\视频格式转码工具\VideoTranscoder.exe"
set "WORKING_DIR=%~dp0dist\视频格式转码工具"

powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); ^
     $s.TargetPath = '%TARGET_PATH%'; ^
     $s.WorkingDirectory = '%WORKING_DIR%'; ^
     $s.Description = 'MKV 转 MP4，无损视频格式转码工具'; ^
     $s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo 桌面快捷方式已创建
) else (
    echo 快捷方式创建失败（可手动创建）
)

:end
echo.
echo 按任意键退出...
pause >nul
