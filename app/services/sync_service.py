import hashlib
import json
import base64
from datetime import datetime, timedelta
from flask import current_app
from app.models import db, Sentence, UserSettings, SyncIdempotencyRecord

# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

def _encode_cursor(snapshot_ts, offset_id):
    """Encode (snapshot_ts_isoformat, last_entity_id) into opaque cursor."""
    payload = json.dumps({'ts': snapshot_ts, 'id': offset_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(cursor_str):
    """Decode cursor. Returns (snapshot_ts, offset_id) or raises ValueError."""
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor_str.encode()).decode())
        return payload['ts'], payload['id']
    except Exception:
        raise ValueError('CURSOR_INVALID')


# ---------------------------------------------------------------------------
# SyncPullService
# ---------------------------------------------------------------------------

class SyncPullService:
    PAGE_SIZE = 50

    @staticmethod
    def pull(user_id, cursor_str=None):
        """
        Pull incremental changes for a user.

        cursor=None  -> full pull from beginning
        cursor=str   -> incremental pull from cursor position

        Returns: { changes, nextCursor, hasMore }
        """
        if cursor_str:
            try:
                snapshot_ts, offset_id = _decode_cursor(cursor_str)
            except ValueError as e:
                raise e
            # Convert snapshot_ts string back to datetime
            try:
                since_dt = datetime.fromisoformat(snapshot_ts)
            except Exception:
                raise ValueError('CURSOR_INVALID')
        else:
            snapshot_ts = None
            since_dt = None
            offset_id = None

        changes = []

        # --- Sentences ---
        sentence_query = Sentence.query.filter_by(user_id=user_id)
        if since_dt is not None:
            sentence_query = sentence_query.filter(
                (Sentence.updated_at > since_dt) |
                ((Sentence.updated_at == since_dt) & (Sentence.id > (offset_id or '')))
            )
        sentence_query = sentence_query.order_by(
            Sentence.updated_at.asc(), Sentence.id.asc()
        ).limit(SyncPullService.PAGE_SIZE + 1)

        sentences = sentence_query.all()

        for s in sentences[:SyncPullService.PAGE_SIZE]:
            changes.append({
                'entityType': 'sentence',
                'entityId': s.id,
                'action': 'upsert',
                'record': s.to_dict()
            })

        # --- Settings ---
        settings = UserSettings.query.filter_by(user_id=user_id).first()
        if settings:
            include_settings = True
            if since_dt is not None:
                include_settings = settings.updated_at > since_dt
            if include_settings:
                changes.append({
                    'entityType': 'setting',
                    'entityId': user_id,
                    'action': 'upsert',
                    'record': settings.to_dict()
                })

        has_more = len(sentences) > SyncPullService.PAGE_SIZE

        # Build next cursor
        if changes:
            last = changes[-1]
            if last['entityType'] == 'sentence':
                last_record = last['record']
                next_ts = last_record['updatedAt'].replace('Z', '')
                next_id = last_record['id']
            else:
                last_record = last['record']
                next_ts = last_record['updatedAt'].replace('Z', '')
                next_id = user_id
            next_cursor = _encode_cursor(next_ts, next_id)
        else:
            # Keep same cursor if no changes
            if cursor_str:
                next_cursor = cursor_str
            else:
                next_cursor = _encode_cursor(
                    datetime.utcnow().isoformat(), ''
                )

        return {
            'changes': changes,
            'nextCursor': next_cursor,
            'hasMore': has_more
        }


# ---------------------------------------------------------------------------
# SyncPushService
# ---------------------------------------------------------------------------

VALID_ACTIONS = {
    'sentence': {'create', 'upsert', 'delete'},
    'setting': {'replace'},
}


def _hash_operation(op):
    """Stable hash of an operation payload for idempotency check."""
    canonical = json.dumps({
        'entityType': op.get('entityType'),
        'entityId': op.get('entityId'),
        'action': op.get('action'),
        'baseVersion': op.get('baseVersion'),
        'payload': op.get('payload'),
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


class SyncPushService:

    @staticmethod
    def push(user_id, device_id, operations):
        """
        Process a batch of sync operations.
        Returns { results, nextCursor }
        """
        results = []

        for op in operations:
            op_id = op.get('opId', '')
            entity_type = op.get('entityType', '')
            entity_id = op.get('entityId', '')
            action = op.get('action', '')
            base_version = op.get('baseVersion', 0)
            payload = op.get('payload')
            request_hash = _hash_operation(op)

            result = SyncPushService._process_operation(
                user_id=user_id,
                device_id=device_id,
                op_id=op_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                base_version=base_version,
                payload=payload,
                request_hash=request_hash,
            )
            results.append(result)

        # Build cursor reflecting latest server state
        next_cursor = _encode_cursor(datetime.utcnow().isoformat(), '')

        return {'results': results, 'nextCursor': next_cursor}

    @staticmethod
    def _process_operation(user_id, device_id, op_id, entity_type,
                           entity_id, action, base_version, payload, request_hash):
        base_result = {
            'opId': op_id,
            'entityType': entity_type,
            'entityId': entity_id,
        }

        # --- Basic validation ---
        if entity_type not in VALID_ACTIONS:
            return {**base_result, 'status': 'invalid',
                    'errorCode': 'VALIDATION_FAILED', 'retryable': False,
                    'details': {'reason': f'Unknown entityType: {entity_type}'}}

        allowed = VALID_ACTIONS.get(entity_type, set())
        if action not in allowed:
            return {**base_result, 'status': 'invalid',
                    'errorCode': 'ACTION_NOT_ALLOWED', 'retryable': False,
                    'details': {'allowed': list(allowed)}}

        if action != 'delete' and not payload:
            return {**base_result, 'status': 'invalid',
                    'errorCode': 'VALIDATION_FAILED', 'retryable': False,
                    'details': {'reason': 'payload required for non-delete actions'}}

        # --- Idempotency check ---
        window = timedelta(days=current_app.config['IDEMPOTENCY_WINDOW_DAYS'])
        expires_at = datetime.utcnow() + window

        existing_idempotency = SyncIdempotencyRecord.query.filter_by(
            user_id=user_id, device_id=device_id, op_id=op_id
        ).first()

        if existing_idempotency:
            if existing_idempotency.request_hash != request_hash:
                return {**base_result, 'status': 'invalid',
                        'errorCode': 'IDEMPOTENCY_KEY_REUSED', 'retryable': False, 'details': {}}
            # Return cached result
            return existing_idempotency.result_snapshot

        # --- Dispatch to entity handler ---
        try:
            if entity_type == 'sentence':
                result = SyncPushService._handle_sentence(
                    user_id, entity_id, action, base_version, payload, base_result
                )
            elif entity_type == 'setting':
                result = SyncPushService._handle_setting(
                    user_id, base_version, payload, base_result
                )
            else:
                result = {**base_result, 'status': 'invalid',
                          'errorCode': 'VALIDATION_FAILED', 'retryable': False, 'details': {}}
        except Exception as e:
            db.session.rollback()
            return {**base_result, 'status': 'retryable_error',
                    'errorCode': 'TEMPORARY_BACKEND_ERROR', 'retryable': True,
                    'details': {'reason': str(e)}}

        # --- Save idempotency record if applied ---
        if result.get('status') == 'applied':
            record = SyncIdempotencyRecord(
                user_id=user_id,
                device_id=device_id,
                op_id=op_id,
                request_hash=request_hash,
                result_snapshot=result,
                expires_at=expires_at,
            )
            db.session.add(record)
            db.session.commit()

        return result

    @staticmethod
    def _handle_sentence(user_id, entity_id, action, base_version, payload, base_result):
        sentence = Sentence.query.filter_by(id=entity_id, user_id=user_id).first()

        if action == 'delete':
            if not sentence:
                # Already gone — treat as applied (idempotent)
                return {**base_result, 'status': 'applied'}
            if sentence.version != base_version:
                return {**base_result, 'status': 'conflict',
                        'errorCode': 'VERSION_MISMATCH', 'retryable': False,
                        'serverVersion': sentence.version, 'details': {}}
            sentence.deleted_at = datetime.utcnow()
            sentence.version += 1
            sentence.updated_at = datetime.utcnow()
            db.session.commit()
            return {**base_result, 'status': 'applied',
                    'serverVersion': sentence.version,
                    'serverUpdatedAt': sentence.updated_at.isoformat() + 'Z'}

        if action == 'create':
            if sentence:
                # ID collision — treat as upsert conflict
                if sentence.version != base_version:
                    return {**base_result, 'status': 'conflict',
                            'errorCode': 'VERSION_MISMATCH', 'retryable': False,
                            'serverVersion': sentence.version, 'details': {}}
            else:
                sentence = Sentence(id=entity_id, user_id=user_id, version=0)
                db.session.add(sentence)

        if action in ('create', 'upsert'):
            if sentence and sentence.deleted_at is not None:
                return {**base_result, 'status': 'conflict',
                        'errorCode': 'TOMBSTONE_CONFLICT', 'retryable': False,
                        'serverVersion': sentence.version, 'details': {}}

            if sentence and sentence.version != base_version:
                return {**base_result, 'status': 'conflict',
                        'errorCode': 'VERSION_MISMATCH', 'retryable': False,
                        'serverVersion': sentence.version, 'details': {}}

            # Apply payload fields
            if 'content' in payload:
                content = str(payload['content'] or '')
                if not 1 <= len(content) <= 2000:
                    return {**base_result, 'status': 'invalid',
                            'errorCode': 'VALIDATION_FAILED', 'retryable': False,
                            'details': {'field': 'content', 'reason': 'length must be 1-2000'}}
                sentence.content = content
            if 'tags' in payload:
                tags = payload['tags']
                if not isinstance(tags, list):
                    tags = []
                sentence.tags = [str(t)[:30] for t in tags[:50]]
            if 'analysis' in payload:
                sentence.analysis = payload['analysis']
            if 'source' in payload:
                sentence.source = str(payload.get('source', 'text'))

            sentence.version += 1
            sentence.updated_at = datetime.utcnow()
            db.session.commit()

            return {**base_result, 'status': 'applied',
                    'serverVersion': sentence.version,
                    'serverUpdatedAt': sentence.updated_at.isoformat() + 'Z'}

        return {**base_result, 'status': 'invalid',
                'errorCode': 'ACTION_NOT_ALLOWED', 'retryable': False, 'details': {}}

    @staticmethod
    def _handle_setting(user_id, base_version, payload, base_result):
        settings = UserSettings.query.filter_by(user_id=user_id).first()

        if settings is None:
            # First-time creation: accept any baseVersion=0
            if base_version != 0:
                return {**base_result, 'status': 'conflict',
                        'errorCode': 'VERSION_MISMATCH', 'retryable': False,
                        'serverVersion': 0, 'details': {}}
            settings = UserSettings(user_id=user_id, version=0)
            db.session.add(settings)
        else:
            if settings.version != base_version:
                return {**base_result, 'status': 'conflict',
                        'errorCode': 'VERSION_MISMATCH', 'retryable': False,
                        'serverVersion': settings.version, 'details': {}}

        settings.use_mode = payload.get('useMode', settings.use_mode)
        settings.text_api = payload.get('textApi', settings.text_api)
        settings.vision_api = payload.get('visionApi', settings.vision_api)
        settings.ui = payload.get('ui', settings.ui)
        settings.version += 1
        settings.updated_at = datetime.utcnow()
        db.session.commit()

        return {**base_result, 'status': 'applied',
                'serverVersion': settings.version,
                'serverUpdatedAt': settings.updated_at.isoformat() + 'Z'}