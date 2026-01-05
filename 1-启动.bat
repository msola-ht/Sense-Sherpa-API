@echo off
REM Docker Compose 启动脚本 (兼容性修正版)
REM 版权所有 (c) 老何的AIGC研究室
REM 当前时间: 2026/1/4

chcp 936 >nul
echo ==========================================
echo    老何的AIGC研究室 - Docker服务管理
echo ==========================================
echo.

echo [1/2] 正在定位配置文件...
set COMPOSE_FILE=
if exist docker-compose.yml set COMPOSE_FILE=docker-compose.yml
if exist docker-compose.yaml set COMPOSE_FILE=docker-compose.yaml

if "%COMPOSE_FILE%"=="" (
    echo [错误] 找不到 docker-compose 配置文件。
    pause
    exit /b 1
)
echo [确认] 使用文件: %COMPOSE_FILE%

REM --- 阶段 2: 启动服务 ---
echo [2/2] 正在启动服务...
docker-compose -f %COMPOSE_FILE% up -d

REM 检查启动结果 (移除嵌套括号以规避语法错误)
if %ERRORLEVEL% EQU 0 goto SUCCESS
goto FAILED

:SUCCESS
echo.
echo ==========================================
echo    服务部署成功！
echo    版权所有 ^(c^) 老何的AIGC研究室
echo ==========================================
goto END

:FAILED
echo.
echo [错误] 服务启动失败，请检查配置文件内容。
goto END

:END
pause
