from flask import Blueprint
from .auth import auth_bp
from .user import user_bp

__all__ = ['auth_bp', 'user_bp']