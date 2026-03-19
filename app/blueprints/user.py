import uuid
from flask import Blueprint, jsonify, g, request
from functools import wraps
from app.models import db, User
from app.services.auth_service import AuthService

user_bp = Blueprint('user', __name__, url_prefix='')


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


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return error_response('未授权', 'UNAUTHORIZED', 401)

        token = auth_header[7:]
        user_id = AuthService.verify_access_token(token)

        if not user_id:
            return error_response('token 无效或已过期', 'UNAUTHORIZED', 401)

        user = db.session.get(User, user_id)
        if not user or user.status != 'active':
            return error_response('账号不存在或已禁用', 'UNAUTHORIZED', 401)

        g.current_user = user
        g.current_user_id = user.id

        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    """可选鉴权：有 token 则验证，无 token 则跳过"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            user_id = AuthService.verify_access_token(token)

            if user_id:
                user = db.session.get(User, user_id)
                if user and user.status == 'active':
                    g.current_user = user
                    g.current_user_id = user.id
                    return f(*args, **kwargs)

        g.current_user = None
        g.current_user_id = None
        return f(*args, **kwargs)
    return decorated


@user_bp.route('/me', methods=['GET'])
@auth_required
def get_me():
    return success_response(g.current_user.to_dict())
