@echo off
REM Docker Compose 停止脚本
REM 版权所有 (c) 何老师的AIGC研究室
echo 何老师的AIGC研究室 - Docker服务管理
echo.
echo 正在停止服务...
docker-compose down -v
echo 服务已停止，按任意键关闭
echo 版权所有 (c) 何老师的AIGC研究室
pause