@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
echo 홍보물을 만들고 있어요. 잠시만 기다려 주세요...
echo.
"%PY%" "%~dp0사진변환.py" --open
echo.
echo 끝났어요! 방금 만든 결과 폴더가 열렸습니다.
echo.
pause
