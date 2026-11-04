@echo off
chcp 65001 >nul
cd /d "D:\Study\Claw University\ziping-app"
echo 正在启动 子平推演 ...
start http://127.0.0.1:5000
"C:\Users\zzh10\.workbuddy\binaries\python\envs\default\Scripts\python.exe" app.py
pause
