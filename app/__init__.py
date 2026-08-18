import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app(config_object="config.Config"):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.auth.routes import auth_bp
    from app.staff.routes import staff_bp
    from app.manager.routes import manager_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(manager_bp)

    from app import models  # noqa: F401  (register models with SQLAlchemy)

    @login_manager.user_loader
    def load_user(user_id):
        # ids are namespaced as "user:<id>" or "member:<id>"
        from app.models import User, Member

        try:
            kind, raw_id = user_id.split(":")
        except ValueError:
            return None
        if kind == "user":
            return User.query.get(int(raw_id))
        if kind == "member":
            return Member.query.get(int(raw_id))
        return None

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {"current_year": datetime.utcnow().year}

    with app.app_context():
        db.create_all()
        from app.seed import seed_if_empty
        seed_if_empty()

    return app
