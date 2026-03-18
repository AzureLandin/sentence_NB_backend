import re
import uuid
import os
import requests as http_requests
from flask import Blueprint, request, jsonify, g, current_app
from app.models import db, User
from app.services.auth_service import AuthService
from app.blueprints.user import auth_required

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


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


def _token_expires():
    """从 config 动态读取 token 过期时间（秒），避免硬编码与 config 不同步。"""
    access = current_app.config['ACCESS_TOKEN_EXPIRE_MINUTES'] * 60
    refresh = current_app.config['REFRESH_TOKEN_EXPIRE_DAYS'] * 86400
    return access, refresh


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

    if not EMAIL_RE.match(email):
        return error_response('邮箱格式无效', 'VALIDATION_FAILED', 422)

    if len(password) < 6:
        return error_response('密码至少6位', 'VALIDATION_FAILED', 422)

    if display_name and len(display_name) > 100:
        return error_response('displayName 不能超过 100 字符', 'VALIDATION_FAILED', 422)

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
    access_expires, refresh_expires = _token_expires()

    return success_response({
        'user': user.to_dict(),
        'accessToken': access_token,
        'accessTokenExpiresIn': access_expires,
        'refreshToken': refresh_token_str,
        'refreshTokenExpiresIn': refresh_expires,
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
    access_expires, refresh_expires = _token_expires()

    return success_response({
        'user': user.to_dict(),
        'accessToken': access_token,
        'accessTokenExpiresIn': access_expires,
        'refreshToken': refresh_token_str,
        'refreshTokenExpiresIn': refresh_expires,
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

    access_expires, _ = _token_expires()

    return success_response({
        'accessToken': result['access_token'],
        'accessTokenExpiresIn': access_expires,
        'refreshToken': result['new_refresh_token'],
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    data = request.get_json()
    refresh_token_str = data.get('refreshToken', '') if data else ''

    if refresh_token_str:
        AuthService.logout(refresh_token_str)
        db.session.commit()

    return success_response({}, '已登出')


def _call_wechat_code2session(code):
    """调用微信 code2session 接口，返回 (openid, error_code)。
    使用 params 字典传参，防止 code 中特殊字符注入 URL。
    """
    appid = os.environ.get('WECHAT_APPID', '')
    secret = os.environ.get('WECHAT_SECRET', '')

    if not appid or not secret:
        return None, 'WECHAT_CONFIG_MISSING'

    try:
        resp = http_requests.get(
            'https://api.weixin.qq.com/sns/jscode2session',
            params={
                'appid': appid,
                'secret': secret,
                'js_code': code,
                'grant_type': 'authorization_code',
            },
            timeout=5,
        )
        wx_data = resp.json()
    except Exception:
        return None, 'WECHAT_API_UNAVAILABLE'

    if wx_data.get('errcode') and wx_data['errcode'] != 0:
        return None, 'WECHAT_CODE_INVALID'

    openid = wx_data.get('openid')
    if not openid:
        return None, 'WECHAT_CODE_INVALID'

    return openid, None


@auth_bp.route('/wechat', methods=['POST'])
def wechat_login():
    """微信一键登录：code 换 JWT"""
    data = request.get_json()
    if not data:
        return error_response('请求体无效', 'VALIDATION_FAILED', 422)

    code = data.get('code', '').strip()
    if not code:
        return error_response('code 必填', 'VALIDATION_FAILED', 422)

    openid, err = _call_wechat_code2session(code)

    if err == 'WECHAT_CONFIG_MISSING':
        return error_response('微信登录暂不可用', 'WECHAT_CONFIG_MISSING', 500)
    if err == 'WECHAT_API_UNAVAILABLE':
        return error_response('微信服务暂时不可用，请稍后重试', 'WECHAT_API_UNAVAILABLE', 503)
    if err == 'WECHAT_CODE_INVALID':
        return error_response('微信授权已过期，请重试', 'WECHAT_CODE_INVALID', 400)

    # 查找或创建用户；status 检查仅对已存在用户有意义
    user = User.query.filter_by(wechat_openid=openid).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            wechat_openid=openid,
            display_name='微信用户',
            status='active',
        )
        db.session.add(user)
    elif user.status != 'active':
        return error_response('账号已禁用', 'ACCOUNT_DISABLED', 403)

    refresh_token_obj, refresh_token_str = AuthService.create_refresh_token(user.id)
    db.session.add(refresh_token_obj)
    db.session.commit()

    access_token = AuthService.generate_access_token(user.id)
    access_expires, refresh_expires = _token_expires()

    return success_response({
        'user': user.to_dict(),
        'accessToken': access_token,
        'accessTokenExpiresIn': access_expires,
        'refreshToken': refresh_token_str,
        'refreshTokenExpiresIn': refresh_expires,
    }, '微信登录成功')


@auth_bp.route('/bind-wechat', methods=['POST'])
@auth_required
def bind_wechat():
    """将微信 openid 绑定到当前已登录账号"""
    data = request.get_json()
    if not data:
        return error_response('请求体无效', 'VALIDATION_FAILED', 422)

    code = data.get('code', '').strip()
    if not code:
        return error_response('code 必填', 'VALIDATION_FAILED', 422)

    openid, err = _call_wechat_code2session(code)

    if err == 'WECHAT_CONFIG_MISSING':
        return error_response('微信登录暂不可用', 'WECHAT_CONFIG_MISSING', 500)
    if err == 'WECHAT_API_UNAVAILABLE':
        return error_response('微信服务暂时不可用，请稍后重试', 'WECHAT_API_UNAVAILABLE', 503)
    if err == 'WECHAT_CODE_INVALID':
        return error_response('微信授权已过期，请重试', 'WECHAT_CODE_INVALID', 400)

    current_user = g.current_user

    # 当前用户已绑定相同 openid：幂等成功
    if current_user.wechat_openid == openid:
        return success_response({'user': current_user.to_dict()}, '微信已绑定')

    # 当前用户已绑定不同 openid
    if current_user.wechat_openid and current_user.wechat_openid != openid:
        return error_response('当前账号已绑定微信', 'ACCOUNT_ALREADY_HAS_WECHAT', 409)

    # openid 已被其他账号占用
    existing = User.query.filter_by(wechat_openid=openid).first()
    if existing and existing.id != current_user.id:
        return error_response('该微信已绑定其他账号', 'WECHAT_ALREADY_BOUND', 409)

    current_user.wechat_openid = openid
    db.session.commit()

    return success_response({'user': current_user.to_dict()}, '微信绑定成功')
