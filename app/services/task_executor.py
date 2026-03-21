import atexit
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 3

_executor = None
_app = None


def init_app(app):
    """初始化任务执行器，在 app context 中调用。"""
    global _app, _executor
    _app = app
    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ai_task_")
    atexit.register(_shutdown)

    with app.app_context():
        cleanup_stale_tasks()


def _shutdown():
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None


def submit_task(task_id):
    """提交任务到线程池执行。"""
    if _executor is None:
        logger.error("TaskExecutor 未初始化，无法提交任务 %s", task_id)
        return
    _executor.submit(_execute_task, task_id)


def _execute_task(task_id):
    """执行任务，根据 task_type 分发到不同处理函数。"""
    if _app is None:
        return

    with _app.app_context():
        try:
            from app.models import db, AnalysisTask

            task = db.session.get(AnalysisTask, task_id)
            if not task:
                return

            if task.task_type == 'ocr':
                _do_ocr(task)
            else:
                _do_analysis(task)
        finally:
            from app.models import db
            db.session.remove()


def _do_analysis(task):
    """执行句子分析任务。"""
    from app.models import db, Sentence
    from app.services.ai_service import analyze_sentence
    from app.services.ai_config_service import AiConfigMissingError, EndpointNotAllowedError

    user_id = task.user_id
    sentence_content = task.sentence_content

    # 标记为处理中
    try:
        task.status = 'processing'
        task.started_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("任务 %s 状态更新失败", task.id)
        return

    # 内部重试循环
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = analyze_sentence(user_id, sentence_content)

            sentence = Sentence(
                id=str(uuid.uuid4()),
                user_id=user_id,
                content=sentence_content,
                source='analysis',
                analysis=result,
            )
            db.session.add(sentence)
            db.session.flush()

            task.status = 'completed'
            task.sentence_id = sentence.id
            task.result = result
            task.retry_count = attempt
            task.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            return

        except (AiConfigMissingError, EndpointNotAllowedError) as e:
            db.session.rollback()
            _fail_task(
                task.id,
                error_code='AI_CONFIG_MISSING' if isinstance(e, AiConfigMissingError) else 'ENDPOINT_NOT_ALLOWED',
                error_message=str(e),
                retry_count=attempt,
            )
            return

        except Exception as e:
            db.session.rollback()
            last_error = e
            logger.warning("分析任务 %s 第 %d 次尝试失败: %s", task.id, attempt + 1, e)

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
                task = db.session.get(type(task), task.id)
                if not task:
                    return
                continue

    error_msg = str(last_error) if last_error else '未知错误'
    if len(error_msg) > 500:
        error_msg = error_msg[:500] + '...'
    _fail_task(
        task.id,
        error_code='AI_CALL_FAILED',
        error_message=f'AI 调用失败: {error_msg}',
        retry_count=MAX_RETRIES,
    )


def _do_ocr(task):
    """执行 OCR 任务。"""
    from app.models import db
    from app.services.ai_service import extract_sentences, NoBodiesFoundError
    from app.services.ai_config_service import AiConfigMissingError, EndpointNotAllowedError

    user_id = task.user_id
    image_data = task.image_data
    image_mime = task.image_mime or 'image/jpeg'

    # 标记为处理中
    try:
        task.status = 'processing'
        task.started_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("任务 %s 状态更新失败", task.id)
        return

    # 内部重试循环
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            sentences = extract_sentences(user_id, image_data, image_mime)

            task.status = 'completed'
            task.result = {'sentences': sentences}
            task.image_data = None
            task.retry_count = attempt
            task.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            return

        except (AiConfigMissingError, EndpointNotAllowedError) as e:
            db.session.rollback()
            _fail_task(
                task.id,
                error_code='AI_CONFIG_MISSING' if isinstance(e, AiConfigMissingError) else 'ENDPOINT_NOT_ALLOWED',
                error_message=str(e),
                retry_count=attempt,
            )
            return

        except NoBodiesFoundError as e:
            db.session.rollback()
            _fail_task(
                task.id,
                error_code='NO_SENTENCES_FOUND',
                error_message=str(e),
                retry_count=attempt,
            )
            return

        except Exception as e:
            db.session.rollback()
            last_error = e
            logger.warning("OCR 任务 %s 第 %d 次尝试失败: %s", task.id, attempt + 1, e)

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
                task = db.session.get(type(task), task.id)
                if not task:
                    return

    error_msg = str(last_error) if last_error else '未知错误'
    if len(error_msg) > 500:
        error_msg = error_msg[:500] + '...'
    _fail_task(
        task.id,
        error_code='AI_CALL_FAILED',
        error_message=f'OCR 调用失败: {error_msg}',
        retry_count=MAX_RETRIES,
    )


def _fail_task(task_id, error_code, error_message, retry_count=0):
    """将任务标记为失败。独立 try/except 保证不会因更新失败而丢失错误。"""
    from app.models import db, AnalysisTask

    try:
        task = db.session.get(AnalysisTask, task_id)
        if not task:
            return
        task.status = 'failed'
        task.error_code = error_code
        task.error_message = error_message
        task.retry_count = retry_count
        task.completed_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("任务 %s 标记失败时出错", task_id)


def cleanup_stale_tasks():
    """清理卡在 processing/pending 状态超过 5 分钟的任务。容器启动时调用。"""
    from app.models import db, AnalysisTask

    stale_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    try:
        from sqlalchemy import inspect as sa_inspect
        if not sa_inspect(db.engine).has_table('analysis_tasks'):
            return

        now = datetime.now(timezone.utc)
        fail_attrs = {
            AnalysisTask.status: 'failed',
            AnalysisTask.error_code: 'TIMEOUT',
            AnalysisTask.error_message: '任务执行超时（容器重启）',
            AnalysisTask.completed_at: now,
        }

        # 清理卡在 processing 超过 5 分钟的任务
        processing_count = AnalysisTask.query.filter(
            AnalysisTask.status == 'processing',
            AnalysisTask.started_at < stale_time,
        ).update(fail_attrs, synchronize_session='fetch')

        # 清理 pending 超过 5 分钟的孤儿任务（线程池已不存在）
        pending_count = AnalysisTask.query.filter(
            AnalysisTask.status == 'pending',
            AnalysisTask.created_at < stale_time,
        ).update(fail_attrs, synchronize_session='fetch')

        db.session.commit()

        total = processing_count + pending_count
        if total:
            logger.info("清理了 %d 个过期任务（processing=%d, pending=%d）",
                         total, processing_count, pending_count)
    except Exception:
        db.session.rollback()
        logger.exception("清理过期任务失败")