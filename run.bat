@echo off
echo ========================================
echo   正畸复诊拍照对比服务 - 启动脚本
echo ========================================
echo.
echo 启动服务，访问 http://localhost:8000/docs 查看API文档
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
