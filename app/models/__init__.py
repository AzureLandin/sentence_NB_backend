from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import uuid
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    refresh_tokens = db.relationship('RefreshToken', backref='user', lazy=True, cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    sentences = db.relationship('Sentence', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'displayName': self.display_name
        }


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserSettings(db.Model):
    __tablename__ = 'user_settings'

    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    use_mode = db.Column(db.String(20), default='simple')
    text_api = db.Column(db.JSON, default=dict)
    vision_api = db.Column(db.JSON, default=dict)
    ui = db.Column(db.JSON, default=dict)
    version = db.Column(db.BigInteger, default=1)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
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


class SyncIdempotencyRecord(db.Model):
    __tablename__ = 'sync_idempotency_records'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), nullable=False)
    device_id = db.Column(db.String(100), nullable=False)
    op_id = db.Column(db.String(100), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    result_snapshot = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'device_id', 'op_id', name='uq_idempotency_user_device_op'),
        db.Index('ix_idempotency_user_device_op', 'user_id', 'device_id', 'op_id'),
    )