# Backend - Sentence Notebook API

Flask 后端服务，提供账号认证与数据同步 API。

## 快速开始

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境配置
cp .env.example .env
# 编辑 .env 配置数据库连接

# 初始化数据库
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# 启动服务
python run.py
```

## API 接口

### 认证

- `POST /auth/register` - 注册
- `POST /auth/login` - 登录
- `POST /auth/refresh` - 刷新 token
- `POST /auth/logout` - 登出
- `GET /me` - 获取当前用户信息

## 开发

```bash
# 运行测试
pytest

# 代码格式化
black app/
```