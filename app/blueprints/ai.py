import uuid
from flask import Blueprint, request, g, jsonify
from app.blueprints.user import auth_required
from app.services.ai_config_service import AiConfigMissingError
from app.services.ai_service import analyze_sentence, extract_sentences, NoBodiesFoundError

ai_bp = Blueprint('ai', __name__)


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


@ai_bp.post('/api/analyze')
@auth_required
def api_analyze():
    body = request.get_json(silent=True) or {}
    sentence = (body.get('sentence') or '').strip()

    if not sentence:
        return _err('VALIDATION_FAILED', '请提供需要分析的句子')

    try:
        result = analyze_sentence(g.current_user_id, sentence)
        return _ok(result)
    except AiConfigMissingError as e:
        return _err('AI_CONFIG_MISSING',
                    'AI 服务暂未配置，请联系管理员或在设置中填写自有 Key',
                    http_status=503)
    except (ValueError, Exception) as e:
        error_msg = str(e)
        if 'JSON' in error_msg or '缺少必要字段' in error_msg:
            return _err('AI_CALL_FAILED', f'AI 返回格式异常，请重试: {error_msg}',
                        http_status=502, retryable=True)
        return _err('AI_CALL_FAILED', f'AI 调用失败: {error_msg}',
                    http_status=502, retryable=True)


@ai_bp.post('/api/ocr')
@auth_required
def api_ocr():
    body = request.get_json(silent=True) or {}
    image = (body.get('image') or '').strip()
    mime = body.get('mime', 'image/jpeg')

    if not image:
        return _err('VALIDATION_FAILED', '请提供图片数据')

    try:
        sentences = extract_sentences(g.current_user_id, image, mime)
        return _ok({'sentences': sentences})
    except AiConfigMissingError:
        return _err('AI_CONFIG_MISSING',
                    'AI 服务暂未配置，请联系管理员或在设置中填写自有 Key',
                    http_status=503)
    except NoBodiesFoundError as e:
        return _err('NO_SENTENCES_FOUND', str(e), http_status=422)
    except Exception as e:
        return _err('AI_CALL_FAILED', f'OCR 调用失败: {str(e)}',
                    http_status=502, retryable=True)
