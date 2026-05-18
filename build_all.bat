@echo off
chcp 65001 >nul
echo ========================================
echo   一键发布工具 — 构建
echo ========================================
echo.

echo [1/2] 构建主程序...
pyinstaller build_gui.spec --noconfirm
if %errorlevel% neq 0 exit /b %errorlevel%

echo.
echo [2/2] 复制启动器到 dist...
copy /Y "启动发布工具.bat" "dist\一键发布工具\"
if %errorlevel% neq 0 (
    echo 警告: 复制启动器失败
)

echo.
echo ========================================
echo   构建完成！
echo   dist/一键发布工具/一键发布工具.exe
echo ========================================
pause
