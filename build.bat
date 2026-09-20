@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

REM ============================================
REM  AutoISP300 一键打包脚本 (Win10/11, onefile)
REM  前置: 已安装 Python + PyInstaller
REM ============================================

REM 坑 #5: 清空 PYTHONPATH, 避免 IDE shim 污染
set PYTHONPATH=

REM 国内源: 若未安装 PyInstaller 则自动安装
where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [0/3] 未检测到 PyInstaller, 从清华镜像安装...
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pyinstaller
)

echo [1/3] 清理旧构建产物 build/ dist/...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/3] PyInstaller 打包单文件 exe...
pyinstaller --onefile --windowed ^
    --name AutoISP300 ^
    --distpath "dist" ^
    --manifest dpi.manifest ^
    --icon "assets/icon.ico" ^
    --add-data "assets/icon.ico;assets" ^
    --collect-all pywinauto ^
    --collect-all pynput ^
    --collect-all pyautogui ^
    main.py

echo [3/3] 打包完成: dist\AutoISP300.exe
echo        部署时把 exe 与 config\ 文件夹一起拷贝即可 (config 自动建在 exe 旁)。
pause