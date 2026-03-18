import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify
from sqlalchemy import text
from app.models import db

health_bp = Blueprint('health', __name__)


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


@health_bp.get('/health')
def health_check():
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    try:
        db.session.execute(text('SELECT 1'))
        db_status = 'ok'
    except Exception:
        db_status = 'error'

    if db_status == 'error':
        return error_response('服务异常', 'SERVICE_UNAVAILABLE', 503)

    return success_response({
        'status': 'healthy',
        'db': db_status,
        'timestamp': timestamp,
    })
