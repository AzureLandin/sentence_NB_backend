#!/bin/sh
# 微信云托管启动脚本

export FLASK_APP=run.py

# 调试：打印 MySQL 环境变量
echo "=== MySQL Environment Variables ==="
echo "MYSQL_ADDRESS: $MYSQL_ADDRESS"
echo "MYSQL_USERNAME: $MYSQL_USERNAME"
echo "MYSQL_DATABASE: $MYSQL_DATABASE"
echo "==================================="

# 数据库迁移；失败时主动退出，让编排层重试，避免以错误 schema 启动服务
flask db upgrade

# 启动服务
exec gunicorn run:app \
  --bind 0.0.0.0:${PORT:-80} \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
