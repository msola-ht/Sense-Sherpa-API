@echo off
REM Docker Compose 镜像更新脚本
REM 版权所有 (c) 何老师的AIGC研究室

echo 何老师的AIGC研究室 - Docker服务管理
echo.

if exist docker-compose.yml (
    set COMPOSE_FILE=docker-compose.yml
) else if exist docker-compose.yaml (
    set COMPOSE_FILE=docker-compose.yaml
) else (
    echo 错误：未找到 docker-compose 配置文件
    pause
    exit /b 1
)

echo 正在启动服务...

REM 启动服务并立即显示日志（不会在后台运行）
docker-compose -f %COMPOSE_FILE% pull

REM 当用户按Ctrl+C后，脚本会执行到这里
echo.
echo 启动完毕.按任意键退出.
echo 版权所有 (c) 何老师的AIGC研究室
pause
