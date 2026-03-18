import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import User
from app.services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def success_response(data=None, message='success'):
    return jsonify({
        'code': 'OK',
        'message': message,
        'data': data or {},
        'requestId': str(uuid.uuid4())
    })


def error_response(message, error_code, status=400):
    return jsonify({
        'code': 'ERROR',
        'message': message,
        'errorCode': error_code,
        'retryable': False,
        'details': {},
        'requestId': str(uuid.uuid4())
    }), status


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return error_response('请求体无效', 'VALIDATION_FAILED', 422)
    
    email = data.get('email', '').strip()
    password = data.get('password', '')
    display_name = data.get('displayName', '').strip() or None
    
    if not email or not password:
        return error_response('邮箱和密码必填', 'VALIDATION_FAILED', 422)
    
    if len(password) < 6:
        return error_response('密码至少6位', 'VALIDATION_FAILED', 422)
    
    user, error = AuthService.register(email, password, display_name)
    
    if error == 'EMAIL_ALREADY_EXISTS':
        return error_response('邮箱已注册', 'EMAIL_ALREADY_EXISTS', 409)
    
    if error:
        return error_response('注册失败', error, 500)
    
    db.session.add(user)
    
    refresh_token_obj, refresh_token_str = AuthService.create_refresh_token(user.id)
    db.session.add(refresh_token_obj)
    
    db.session.commit()
    
    access_token = AuthService.generate_access_token(user.id)
    
    return success_response({
        'user': user.to_dict(),
        'accessToken': access_token,
        'accessTokenExpiresIn': 1800,
        'refreshToken': refresh_token_str,
        'refreshTokenExpiresIn': 2592000
    }, '注册成功')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return error_response('请求体无效', 'VALIDATION_FAILED', 422)
    
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return error_response('邮箱和密码必填', 'VALIDATION_FAILED', 422)
    
    user, error = AuthService.login(email, password)
    
    if error == 'INVALID_CREDENTIALS':
        return error_response('账号或密码错误', 'INVALID_CREDENTIALS', 401)
    
    if error == 'ACCOUNT_DISABLED':
        return error_response('账号已禁用', 'ACCOUNT_DISABLED', 403)
    
    if error:
        return error_response('登录失败', error, 500)
    
    refresh_token_obj, refresh_token_str = AuthService.create_refresh_token(user.id)
    db.session.add(refresh_token_obj)
    db.session.commit()
    
    access_token = AuthService.generate_access_token(user.id)
    
    return success_response({
        'user': user.to_dict(),
        'accessToken': access_token,
        'accessTokenExpiresIn': 1800,
        'refreshToken': refresh_token_str,
        'refreshTokenExpiresIn': 2592000
    }, '登录成功')


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    data = request.get_json()
    if not data:
        return error_response('请求体无效', 'VALIDATION_FAILED', 422)
    
    refresh_token_str = data.get('refreshToken', '')
    if not refresh_token_str:
        return error_response('refreshToken 必填', 'VALIDATION_FAILED', 422)
    
    result, error = AuthService.refresh_access_token(refresh_token_str)
    
    if error == 'REFRESH_TOKEN_REVOKED':
        return error_response('refresh token 已吊销', 'REFRESH_TOKEN_REVOKED', 401)
    
    if error == 'REFRESH_TOKEN_EXPIRED':
        return error_response('登录已过期，请重新登录', 'REFRESH_TOKEN_EXPIRED', 401)
    
    if error == 'ACCOUNT_DISABLED':
        return error_response('账号已禁用', 'ACCOUNT_DISABLED', 403)
    
    if error:
        return error_response('刷新失败', error, 500)
    
    db.session.add(result['new_refresh_token_obj'])
    db.session.commit()
    
    return success_response({
        'accessToken': result['access_token'],
        'accessTokenExpiresIn': 1800,
        'refreshToken': result['new_refresh_token']
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    data = request.get_json()
    refresh_token_str = data.get('refreshToken', '') if data else ''
    
    if refresh_token_str:
        AuthService.logout(refresh_token_str)
        db.session.commit()
    
    return success_response({}, '已登出')