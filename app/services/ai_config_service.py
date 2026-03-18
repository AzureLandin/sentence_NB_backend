import os
from flask import current_app
from cryptography.fernet import Fernet


class AiConfigMissingError(Exception):
    def __init__(self, config_type=''):
        self.config_type = config_type
        super().__init__(f'AI 服务未配置: {config_type}')


def _get_fernet():
    key = current_app.config.get('AI_CONFIG_ENCRYPT_KEY', '')
    if not key:
        raise RuntimeError('AI_CONFIG_ENCRYPT_KEY 未配置')
    return Fernet(key.encode())


def encrypt_key(plain_key: str) -> str:
    """加密明文 API Key，返回加密字符串。"""
    return _get_fernet().encrypt(plain_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    """解密加密的 API Key，返回明文字符串。"""
    return _get_fernet().decrypt(encrypted_key.encode()).decode()


def resolve_api_config(user_id, config_type: str) -> dict:
    """
    返回实际使用的 AI API 配置。
    config_type: 'text' | 'vision'
    优先级：用户自有 Key > 平台默认 Key
    若两者均缺失，抛出 AiConfigMissingError。
    """
    from app.models import UserAIConfig

    user_cfg = UserAIConfig.query.filter_by(user_id=user_id).first()
    encrypted_key = getattr(user_cfg, f'{config_type}_api_key', None) if user_cfg else None

    user_key = None
    if encrypted_key:
        try:
            user_key = decrypt_key(encrypted_key)
        except Exception:
            user_key = None

    if user_key:
        user_endpoint = getattr(user_cfg, f'{config_type}_endpoint', None)
        user_model = getattr(user_cfg, f'{config_type}_model', None)
        # endpoint 和 model 必须与用户自有 Key 一起填写，不得 fallback 到平台默认值
        # （平台默认 endpoint 只能配合平台默认 Key 使用，二者来自同一个服务商）
        if not user_endpoint:
            raise AiConfigMissingError(
                f'{config_type}_endpoint（已填写 API Key，请一并填写对应的 API 端点）'
            )
        if not user_model:
            raise AiConfigMissingError(
                f'{config_type}_model（已填写 API Key，请一并填写对应的模型 ID）'
            )
        return {
            'api_key':  user_key,
            'endpoint': user_endpoint,
            'model':    user_model,
        }

    default_key = current_app.config.get(f'DEFAULT_{config_type.upper()}_API_KEY', '')
    if not default_key:
        raise AiConfigMissingError(config_type)

    return {
        'api_key':  default_key,
        'endpoint': current_app.config.get(f'DEFAULT_{config_type.upper()}_ENDPOINT'),
        'model':    current_app.config.get(f'DEFAULT_{config_type.upper()}_MODEL'),
    }
