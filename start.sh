#!/bin/sh
# 微信云托管启动脚本

# 数据库迁移（多实例只会在第一次执行时生效）
flask db upgrade || true

# 启动服务
exec gunicorn run:app \
  --bind 0.0.0.0:${PORT:-80} \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
