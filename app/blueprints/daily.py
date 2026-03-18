import uuid
import requests
from flask import Blueprint, jsonify
from datetime import date
from app.models import db, DailySentence

daily_bp = Blueprint('daily', __name__, url_prefix='/daily')

ZENQUOTES_API = 'https://zenquotes.io/api/today'


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


def fetch_zenquotes():
    try:
        resp = requests.get(ZENQUOTES_API, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data and len(data) > 0:
            quote = data[0]
            return {
                'content': quote.get('q', ''),
                'author': quote.get('a', 'Unknown'),
            }
    except Exception:
        pass
    return None


@daily_bp.route('/sentence', methods=['GET'])
def get_daily_sentence():
    today = date.today()
    sentence = DailySentence.query.filter_by(date=today).first()
    
    if sentence:
        return success_response(sentence.to_dict())
    
    zen = fetch_zenquotes()
    if not zen:
        return error_response('暂无推荐', 'NOT_FOUND', 404)
    
    sentence = DailySentence(
        content=zen['content'],
        translation=zen['author'],
        grammar_point=None,
        date=today,
    )
    db.session.add(sentence)
    db.session.commit()
    
    return success_response(sentence.to_dict())