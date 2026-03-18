import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


def _build_database_url():
    # 微信云托管自动注入的 MySQL 环境变量（优先使用）
    mysql_address = os.getenv('MYSQL_ADDRESS')       # 格式: host:port
    mysql_username = os.getenv('MYSQL_USERNAME')
    mysql_password = os.getenv('MYSQL_PASSWORD')
    mysql_database = os.getenv('MYSQL_DATABASE', 'englishnotebook')

    if mysql_address and mysql_username and mysql_password:
        return (
            f"mysql+pymysql://{quote_plus(mysql_username)}:{quote_plus(mysql_password)}"
            f"@{mysql_address}/{mysql_database}?charset=utf8mb4"
        )

    # 本地开发：通过 DATABASE_URL 手动指定
    return os.getenv('DATABASE_URL', 'sqlite:///app.db')


class Config:
    SQLALCHEMY_DATABASE_URI = _build_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', '')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', 30))
    IDEMPOTENCY_WINDOW_DAYS = int(os.getenv('IDEMPOTENCY_WINDOW_DAYS', 7))

    # AI 配置加密
    AI_CONFIG_ENCRYPT_KEY = os.getenv('AI_CONFIG_ENCRYPT_KEY', '')

    # 平台默认文本 AI 配置
    DEFAULT_TEXT_API_KEY = os.getenv('DEFAULT_TEXT_API_KEY', '')
    DEFAULT_TEXT_ENDPOINT = os.getenv('DEFAULT_TEXT_ENDPOINT', 'https://api.openai.com/v1/chat/completions')
    DEFAULT_TEXT_MODEL = os.getenv('DEFAULT_TEXT_MODEL', 'gpt-4o')

    # 平台默认视觉 AI 配置
    DEFAULT_VISION_API_KEY = os.getenv('DEFAULT_VISION_API_KEY', '')
    DEFAULT_VISION_ENDPOINT = os.getenv('DEFAULT_VISION_ENDPOINT', 'https://api.openai.com/v1/chat/completions')
    DEFAULT_VISION_MODEL = os.getenv('DEFAULT_VISION_MODEL', 'gpt-4o')