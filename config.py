import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-secret-key')
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