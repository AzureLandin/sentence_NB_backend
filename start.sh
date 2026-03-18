#!/bin/sh
# 微信云托管启动脚本

export FLASK_APP=run.py

# 数据库迁移；失败时主动退出，让编排层重试，避免以错误 schema 启动服务
flask db upgrade

# 启动服务
exec gunicorn run:app \
  --bind 0.0.0.0:${PORT:-80} \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
