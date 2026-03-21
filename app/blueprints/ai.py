import uuid
from flask import Blueprint, request, g, jsonify
from app.blueprints.user import auth_required, optional_auth
from app.models import db, AnalysisTask
from app.services.ai_config_service import AiConfigMissingError, EndpointNotAllowedError
from app.services.ai_service import (
    extract_sentences,
    NoBodiesFoundError,
)
from app.services.task_executor import submit_analysis_task

ai_bp = Blueprint("ai", __name__)

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_SENTENCE_LEN = 2000
MAX_IMAGE_B64_BYTES = 10 * 1024 * 1024  # 10 MB


def _ok(data):
    return jsonify(
        {
            "code": "OK",
            "message": "success",
            "data": data,
            "requestId": str(uuid.uuid4()),
        }
    )


def _err(error_code, message, http_status=400, retryable=False):
    return (
        jsonify(
            {
                "code": "ERROR",
                "errorCode": error_code,
                "message": message,
                "retryable": retryable,
                "requestId": str(uuid.uuid4()),
            }
        ),
        http_status,
    )


@ai_bp.post("/api/analyze")
@auth_required
def api_analyze():
    body = request.get_json(silent=True) or {}
    sentence = (body.get("sentence") or "").strip()

    if not sentence:
        return _err("VALIDATION_FAILED", "请提供需要分析的句子")

    if len(sentence) > MAX_SENTENCE_LEN:
        return _err("VALIDATION_FAILED", f"句子过长，最多 {MAX_SENTENCE_LEN} 字符")

    try:
        task = AnalysisTask(
            user_id=g.current_user_id,
            sentence_content=sentence,
            status='pending',
        )
        db.session.add(task)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _err("SERVICE_UNAVAILABLE", "服务暂时不可用", http_status=503, retryable=True)

    submit_analysis_task(task.id, g.current_user_id, sentence)

    return _ok({"taskId": task.id, "status": "pending"})


@ai_bp.get("/api/analyze/<task_id>")
@auth_required
def api_analyze_status(task_id):
    task = db.session.get(AnalysisTask, task_id)

    if not task:
        return _err("TASK_NOT_FOUND", "任务不存在", http_status=404)

    if task.user_id != g.current_user_id:
        return _err("FORBIDDEN", "无权访问此任务", http_status=403)

    return _ok(task.to_dict())


@ai_bp.post("/api/ocr")
@optional_auth
def api_ocr():
    body = request.get_json(silent=True) or {}
    image = (body.get("image") or "").strip()
    mime = body.get("mime", "image/jpeg")

    if not image:
        return _err("VALIDATION_FAILED", "请提供图片数据")

    if mime not in ALLOWED_MIMES:
        return _err("VALIDATION_FAILED", "不支持的图片格式，仅支持 jpeg/png/gif/webp")

    if len(image) > MAX_IMAGE_B64_BYTES:
        return _err("VALIDATION_FAILED", "图片过大，最多 10MB")

    try:
        sentences = extract_sentences(g.current_user_id, image, mime)
        return _ok({"sentences": sentences})
    except AiConfigMissingError:
        return _err(
            "AI_CONFIG_MISSING", "AI 服务暂未配置，请联系管理员或在设置中填写自有 Key", http_status=503
        )
    except EndpointNotAllowedError as e:
        return _err("VALIDATION_FAILED", str(e), http_status=422)
    except NoBodiesFoundError as e:
        return _err("NO_SENTENCES_FOUND", str(e), http_status=422)
    except Exception as e:
        return _err(
            "AI_CALL_FAILED", f"OCR 调用失败: {str(e)}", http_status=502, retryable=True
        )
