from flask import Flask
from flask_cors import CORS
from config import Config
from app.models import db, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, origins=app.config.get("CORS_ALLOWED_ORIGINS", []))

    if not app.config.get("JWT_SECRET_KEY"):
        raise RuntimeError("JWT_SECRET_KEY environment variable must be set")

    db.init_app(app)
    migrate.init_app(app, db)

    from app.blueprints import (
        auth_bp,
        user_bp,
        sync_bp,
        ai_bp,
        ai_config_bp,
        daily_bp,
        health_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(ai_config_bp)
    app.register_blueprint(daily_bp)
    app.register_blueprint(health_bp)

    from app.services.task_executor import init_app as init_task_executor
    init_task_executor(app)

    return app
