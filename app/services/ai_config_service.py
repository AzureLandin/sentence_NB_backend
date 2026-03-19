import os
import socket
import ipaddress
from urllib.parse import urlparse
from flask import current_app
from cryptography.fernet import Fernet


class AiConfigMissingError(Exception):
    def __init__(self, config_type=""):
        self.config_type = config_type
        super().__init__(f"AI 服务未配置: {config_type}")


class EndpointNotAllowedError(Exception):
    pass


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def validate_endpoint(url):
    """校验 endpoint URL，阻止内网/回环/元数据地址，防止 SSRF。"""
    if not url:
        return
    try:
        parsed = urlparse(url)
    except Exception:
        raise EndpointNotAllowedError("endpoint URL 格式无效")

    if parsed.scheme not in ("https", "http"):
        raise EndpointNotAllowedError("endpoint 仅支持 http/https 协议")

    hostname = parsed.hostname
    if not hostname:
        raise EndpointNotAllowedError("endpoint URL 缺少主机名")

    # 解析域名为 IP（含 IPv6），逐个检查是否命中黑名单网段
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise EndpointNotAllowedError(f"无法解析主机名: {hostname}")

    for family, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for blocked in _BLOCKED_NETWORKS:
            if ip in blocked:
                raise EndpointNotAllowedError("不允许访问内网或保留地址")


def _get_fernet():
    key = current_app.config.get("AI_CONFIG_ENCRYPT_KEY", "")
    if not key:
        raise RuntimeError("AI_CONFIG_ENCRYPT_KEY 未配置")
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
    若 user_id 为 None 或两者均缺失，使用平台默认 Key。
    若平台默认 Key 也缺失，抛出 AiConfigMissingError。
    """
    from app.models import UserAIConfig

    # 未登录用户直接使用平台默认配置
    if user_id:
        user_cfg = UserAIConfig.query.filter_by(user_id=user_id).first()
        encrypted_key = (
            getattr(user_cfg, f"{config_type}_api_key", None) if user_cfg else None
        )

        user_key = None
        if encrypted_key:
            try:
                user_key = decrypt_key(encrypted_key)
            except Exception:
                user_key = None

        if user_key:
            user_endpoint = getattr(user_cfg, f"{config_type}_endpoint", None)
            user_model = getattr(user_cfg, f"{config_type}_model", None)
            # endpoint 和 model 必须与用户自有 Key 一起填写，不得 fallback 到平台默认值
            # （平台默认 endpoint 只能配合平台默认 Key 使用，二者来自同一个服务商）
            if not user_endpoint:
                raise AiConfigMissingError(
                    f"{config_type}_endpoint（已填写 API Key，请一并填写对应的 API 端点）"
                )
            if not user_model:
                raise AiConfigMissingError(
                    f"{config_type}_model（已填写 API Key，请一并填写对应的模型 ID）"
                )
            validate_endpoint(user_endpoint)
            return {
                "api_key": user_key,
                "endpoint": user_endpoint,
                "model": user_model,
            }

    # 使用平台默认配置
    default_key = current_app.config.get(f"DEFAULT_{config_type.upper()}_API_KEY", "")
    if not default_key:
        raise AiConfigMissingError(config_type)

    return {
        "api_key": default_key,
        "endpoint": current_app.config.get(f"DEFAULT_{config_type.upper()}_ENDPOINT"),
        "model": current_app.config.get(f"DEFAULT_{config_type.upper()}_MODEL"),
    }
