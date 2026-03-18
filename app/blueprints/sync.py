import uuid
from flask import Blueprint, request, jsonify, g
from app.blueprints.user import auth_required
from app.services.sync_service import SyncPullService, SyncPushService

sync_bp = Blueprint('sync', __name__, url_prefix='/sync')


def success_response(data=None, message='success'):
    return jsonify({
        'code': 'OK',
        'message': message,
        'data': data or {},
        'requestId': str(uuid.uuid4())
    })


def error_response(message, error_code, status=400, retryable=False):
    return jsonify({
        'code': 'ERROR',
        'message': message,
        'errorCode': error_code,
        'retryable': retryable,
        'details': {},
        'requestId': str(uuid.uuid4())
    }), status


@sync_bp.route('/pull', methods=['GET'])
@auth_required
def pull():
    cursor = request.args.get('cursor', None) or None

    try:
        result = SyncPullService.pull(g.current_user_id, cursor)
    except ValueError as e:
        err = str(e)
        if err == 'CURSOR_INVALID':
            return error_response('cursor 无效', 'CURSOR_INVALID', 422)
        return error_response('cursor 已过期', 'CURSOR_EXPIRED', 409)

    return success_response(result)


@sync_bp.route('/push', methods=['POST'])
@auth_required
def push():
    data = request.get_json()
    if not data:
        return error_response('请求体无效', 'VALIDATION_FAILED', 422)

    device_id = data.get('deviceId', '').strip()
    operations = data.get('operations', [])

    if not device_id:
        return error_response('deviceId 必填', 'VALIDATION_FAILED', 422)

    if not isinstance(operations, list):
        return error_response('operations 必须为数组', 'VALIDATION_FAILED', 422)

    if len(operations) == 0:
        return success_response({'results': [], 'nextCursor': ''})

    result = SyncPushService.push(g.current_user_id, device_id, operations)
    return success_response(result)