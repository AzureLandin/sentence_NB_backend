from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import uuid
from datetime import datetime, timezone

db = SQLAlchemy()
migrate = Migrate()


def _now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    display_name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')
    wechat_openid = db.Column(db.String(64), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    refresh_tokens = db.relationship('RefreshToken', backref='user', lazy=True, cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    sentences = db.relationship('Sentence', backref='user', lazy=True, cascade='all, delete-orphan')
    ai_config = db.relationship('UserAIConfig', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'displayName': self.display_name,
            'wechatBound': self.wechat_openid is not None,
        }


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(255), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)


class UserSettings(db.Model):
    __tablename__ = 'user_settings'

    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    use_mode = db.Column(db.String(20), default='simple')
    text_api = db.Column(db.JSON, default=dict)
    vision_api = db.Column(db.JSON, default=dict)
    ui = db.Column(db.JSON, default=dict)
    version = db.Column(db.BigInteger, default=1)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    def to_dict(self):
        return {
            'useMode': self.use_mode,
            'textApi': self.text_api,
            'visionApi': self.vision_api,
            'ui': self.ui,
            'version': self.version,
            'updatedAt': self.updated_at.isoformat() + 'Z' if self.updated_at else None
        }


class Sentence(db.Model):
    __tablename__ = 'sentences'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(20), default='text')
    analysis = db.Column(db.JSON, nullable=True)
    tags = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now, index=True)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    version = db.Column(db.BigInteger, default=1)

    __table_args__ = (
        db.Index('ix_sentences_user_updated', 'user_id', 'updated_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'source': self.source,
            'analysis': self.analysis,
            'tags': self.tags or [],
            'createdAt': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            'deletedAt': self.deleted_at.isoformat() + 'Z' if self.deleted_at else None,
            'version': self.version
        }


class UserAIConfig(db.Model):
    __tablename__ = 'user_ai_configs'

    id              = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id         = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True, nullable=False)
    text_provider   = db.Column(db.String(64), nullable=True)
    text_api_key    = db.Column(db.Text, nullable=True)   # Fernet 加密
    text_endpoint   = db.Column(db.Text, nullable=True)
    text_model      = db.Column(db.String(128), nullable=True)
    vision_provider = db.Column(db.String(64), nullable=True)
    vision_api_key  = db.Column(db.Text, nullable=True)   # Fernet 加密
    vision_endpoint = db.Column(db.Text, nullable=True)
    vision_model    = db.Column(db.String(128), nullable=True)
    created_at      = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at      = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    def to_dict(self, mask_keys=True, decrypted_text_key=None, decrypted_vision_key=None):
        """返回配置字典，mask_keys=True 时 api_key 字段脱敏"""
        def mask(val):
            if not val or not mask_keys:
                return val
            return val[:3] + '****' + val[-4:] if len(val) > 7 else '****'
        return {
            'textProvider':   self.text_provider,
            'textApiKey':     mask(decrypted_text_key),
            'textEndpoint':   self.text_endpoint,
            'textModel':      self.text_model,
            'visionProvider': self.vision_provider,
            'visionApiKey':   mask(decrypted_vision_key),
            'visionEndpoint': self.vision_endpoint,
            'visionModel':    self.vision_model,
        }


class SyncIdempotencyRecord(db.Model):
    __tablename__ = 'sync_idempotency_records'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), nullable=False)
    device_id = db.Column(db.String(100), nullable=False)
    op_id = db.Column(db.String(100), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    result_snapshot = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'device_id', 'op_id', name='uq_idempotency_user_device_op'),
        db.Index('ix_idempotency_user_device_op', 'user_id', 'device_id', 'op_id'),
    )


class DailySentence(db.Model):
    __tablename__ = 'daily_sentences'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content = db.Column(db.Text, nullable=False)
    translation = db.Column(db.Text, nullable=False)
    grammar_point = db.Column(db.String(100), nullable=True)
    date = db.Column(db.Date, nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'translation': self.translation,
            'grammarPoint': self.grammar_point,
            'date': self.date.isoformat() if self.date else None,
        }


class AnalysisTask(db.Model):
    __tablename__ = 'analysis_tasks'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    sentence_id = db.Column(db.String(36), db.ForeignKey('sentences.id'), nullable=True)
    sentence_content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)
    result = db.Column(db.JSON, nullable=True)
    error_code = db.Column(db.String(50), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            'taskId': self.id,
            'sentenceId': self.sentence_id,
            'status': self.status,
            'result': self.result,
            'errorCode': self.error_code,
            'errorMessage': self.error_message,
            'createdAt': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'completedAt': self.completed_at.isoformat() + 'Z' if self.completed_at else None,
        }
