import uuid
from flask import Blueprint, jsonify
from datetime import date
from app.models import db, DailySentence

daily_bp = Blueprint('daily', __name__, url_prefix='/daily')


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


@daily_bp.route('/sentence', methods=['GET'])
def get_daily_sentence():
    today = date.today()
    sentence = DailySentence.query.filter_by(date=today).first()
    
    if not sentence:
        return error_response('暂无推荐', 'NOT_FOUND', 404)
    
    return success_response(sentence.to_dict())