from flask import Flask
from flask_cors import CORS
from config import Config
from app.models import db, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    CORS(app, origins='*', supports_credentials=True)
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    from app.blueprints import auth_bp, user_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    
    with app.app_context():
        db.create_all()
    
    return app