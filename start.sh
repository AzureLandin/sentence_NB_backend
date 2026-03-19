#!/bin/sh
# 微信云托管启动脚本

export FLASK_APP=run.py

# 调试：打印 MySQL 环境变量
echo "=== MySQL Environment Variables ==="
echo "MYSQL_ADDRESS: $MYSQL_ADDRESS"
echo "MYSQL_USERNAME: $MYSQL_USERNAME"
echo "MYSQL_DATABASE: $MYSQL_DATABASE"
echo "==================================="

# 如果使用 MySQL，先创建数据库（如果不存在）
if [ -n "$MYSQL_ADDRESS" ] && [ -n "$MYSQL_USERNAME" ] && [ -n "$MYSQL_PASSWORD" ]; then
    echo "Creating database if not exists..."
    python -c "
import pymysql
import os
host_port = os.getenv('MYSQL_ADDRESS', '').split(':')
host = host_port[0]
port = int(host_port[1]) if len(host_port) > 1 else 3306
user = os.getenv('MYSQL_USERNAME')
password = os.getenv('MYSQL_PASSWORD')
database = os.getenv('MYSQL_DATABASE', 'englishnotebook')
conn = pymysql.connect(host=host, port=port, user=user, password=password)
cursor = conn.cursor()
cursor.execute(f'CREATE DATABASE IF NOT EXISTS \`{database}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
conn.commit()
conn.close()
print(f'Database {database} ready')
"
fi

# 数据库迁移；失败时主动退出，让编排层重试，避免以错误 schema 启动服务
flask db upgrade

# 启动服务
exec gunicorn run:app \
  --bind 0.0.0.0:${PORT:-80} \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
