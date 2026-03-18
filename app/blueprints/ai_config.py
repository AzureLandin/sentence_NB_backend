import uuid
from flask import Blueprint, request, g, jsonify
from app.blueprints.user import auth_required
from app.models import db, UserAIConfig
from app.services.ai_config_service import (
    encrypt_key, resolve_api_config, AiConfigMissingError
)

ai_config_bp = Blueprint('ai_config', __name__)


def _ok(data):
    return jsonify({'code': 'OK', 'message': 'success', 'data': data, 'requestId': str(uuid.uuid4())})


def _err(error_code, message, http_status=400, retryable=False):
    return jsonify({
        'code': 'ERROR',
        'errorCode': error_code,
        'message': message,
        'retryable': retryable,
        'requestId': str(uuid.uuid4()),
    }), http_status


@ai_config_bp.get('/api/ai-config')
@auth_required
def get_ai_config():
    user_id = g.current_user_id
    cfg = UserAIConfig.query.filter_by(user_id=user_id).first()

    if cfg is None:
        return _ok({
            'textProvider': None, 'textApiKey': None,
            'textEndpoint': None, 'textModel': None,
            'visionProvider': None, 'visionApiKey': None,
            'visionEndpoint': None, 'visionModel': None,
        })

    # 解密后传给 to_dict 做脱敏
    from app.services.ai_config_service import decrypt_key
    def _safe_decrypt(val):
        if not val:
            return None
        try:
            return decrypt_key(val)
        except Exception:
            return None

    text_plain = _safe_decrypt(cfg.text_api_key)
    vision_plain = _safe_decrypt(cfg.vision_api_key)

    return _ok(cfg.to_dict(mask_keys=True,
                            decrypted_text_key=text_plain,
                            decrypted_vision_key=vision_plain))


@ai_config_bp.put('/api/ai-config')
@auth_required
def put_ai_config():
    user_id = g.current_user_id
    body = request.get_json(silent=True) or {}

    cfg = UserAIConfig.query.filter_by(user_id=user_id).first()
    if cfg is None:
        cfg = UserAIConfig(id=str(uuid.uuid4()), user_id=user_id)
        db.session.add(cfg)

    # 只更新请求中明确传入的字段；传 null 则清空（回退平台默认）
    if 'textProvider' in body:
        cfg.text_provider = body['textProvider']
    if 'textApiKey' in body:
        raw = body['textApiKey']
        cfg.text_api_key = encrypt_key(raw) if raw else None
    if 'textEndpoint' in body:
        cfg.text_endpoint = body['textEndpoint'] or None
    if 'textModel' in body:
        cfg.text_model = body['textModel'] or None
    if 'visionProvider' in body:
        cfg.vision_provider = body['visionProvider']
    if 'visionApiKey' in body:
        raw = body['visionApiKey']
        cfg.vision_api_key = encrypt_key(raw) if raw else None
    if 'visionEndpoint' in body:
        cfg.vision_endpoint = body['visionEndpoint'] or None
    if 'visionModel' in body:
        cfg.vision_model = body['visionModel'] or None

    db.session.commit()
    return _ok({'saved': True})


@ai_config_bp.post('/api/ai-config/test')
@auth_required
def test_ai_config():
    user_id = g.current_user_id
    body = request.get_json(silent=True) or {}
    config_type = body.get('type', 'text')

    if config_type not in ('text', 'vision'):
        return _err('VALIDATION_FAILED', 'type 必须为 "text" 或 "vision"')

    try:
        api_config = resolve_api_config(user_id, config_type)
    except AiConfigMissingError as e:
        return _err('AI_CONFIG_MISSING', str(e), http_status=503)

    import requests as req
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_config["api_key"]}',
        }
        body_payload = {
            'model': api_config['model'],
            'messages': [{'role': 'user', 'content': 'Hi'}],
            'max_tokens': 10,
        }
        resp = req.post(api_config['endpoint'], headers=headers, json=body_payload, timeout=30)
        resp.raise_for_status()
        return _ok({'success': True})
    except Exception as e:
        return _ok({'success': False, 'message': str(e)})
