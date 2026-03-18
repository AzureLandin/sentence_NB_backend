import uuid
import hashlib
import bcrypt
import jwt
from datetime import datetime, timedelta
from flask import current_app
from app.models import User, RefreshToken


class AuthService:
    @staticmethod
    def normalize_email(email):
        return email.strip().lower()

    @staticmethod
    def hash_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password, password_hash):
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def generate_access_token(user_id):
        expires = datetime.utcnow() + timedelta(minutes=current_app.config['ACCESS_TOKEN_EXPIRE_MINUTES'])
        payload = {
            'sub': user_id,
            'type': 'access',
            'exp': expires,
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm=current_app.config['JWT_ALGORITHM'])

    @staticmethod
    def generate_refresh_token():
        return 'rt_' + str(uuid.uuid4()).replace('-', '')

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    @staticmethod
    def create_user(email, password, display_name=None):
        normalized_email = AuthService.normalize_email(email)
        password_hash = AuthService.hash_password(password)
        
        user = User(
            id=str(uuid.uuid4()),
            email=normalized_email,
            password_hash=password_hash,
            display_name=display_name or normalized_email.split('@')[0]
        )
        return user

    @staticmethod
    def register(email, password, display_name=None):
        normalized_email = AuthService.normalize_email(email)
        
        existing = User.query.filter_by(email=normalized_email).first()
        if existing:
            return None, 'EMAIL_ALREADY_EXISTS'
        
        user = AuthService.create_user(email, password, display_name)
        return user, None

    @staticmethod
    def login(email, password):
        normalized_email = AuthService.normalize_email(email)
        user = User.query.filter_by(email=normalized_email).first()
        
        if not user:
            return None, 'INVALID_CREDENTIALS'
        
        if user.status != 'active':
            return None, 'ACCOUNT_DISABLED'
        
        if not AuthService.verify_password(password, user.password_hash):
            return None, 'INVALID_CREDENTIALS'
        
        return user, None

    @staticmethod
    def create_refresh_token(user_id):
        token = AuthService.generate_refresh_token()
        token_hash = AuthService.hash_token(token)
        expires_at = datetime.utcnow() + timedelta(days=current_app.config['REFRESH_TOKEN_EXPIRE_DAYS'])
        
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        return refresh_token, token

    @staticmethod
    def refresh_access_token(refresh_token_str):
        token_hash = AuthService.hash_token(refresh_token_str)
        refresh_token = RefreshToken.query.filter_by(token_hash=token_hash).first()
        
        if not refresh_token:
            return None, 'REFRESH_TOKEN_REVOKED'
        
        if refresh_token.revoked_at:
            return None, 'REFRESH_TOKEN_REVOKED'
        
        if refresh_token.expires_at < datetime.utcnow():
            return None, 'REFRESH_TOKEN_EXPIRED'
        
        user = User.query.get(refresh_token.user_id)
        if not user or user.status != 'active':
            return None, 'ACCOUNT_DISABLED'
        
        refresh_token.revoked_at = datetime.utcnow()
        
        new_refresh_token_obj, new_refresh_token_str = AuthService.create_refresh_token(user.id)
        
        access_token = AuthService.generate_access_token(user.id)
        
        return {
            'user': user,
            'access_token': access_token,
            'new_refresh_token_obj': new_refresh_token_obj,
            'new_refresh_token': new_refresh_token_str
        }, None

    @staticmethod
    def logout(refresh_token_str):
        token_hash = AuthService.hash_token(refresh_token_str)
        refresh_token = RefreshToken.query.filter_by(token_hash=token_hash).first()
        
        if refresh_token and not refresh_token.revoked_at:
            refresh_token.revoked_at = datetime.utcnow()
        
        return True

    @staticmethod
    def verify_access_token(token):
        try:
            payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=[current_app.config['JWT_ALGORITHM']])
            if payload.get('type') != 'access':
                return None
            return payload.get('sub')
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None