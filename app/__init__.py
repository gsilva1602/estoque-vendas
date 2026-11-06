from flask import Flask

from config import Config

from .extensions import db, login_manager
from .timeutils import format_local


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    app.jinja_env.filters["localtime"] = format_local

    from . import models  # noqa: F401  (registra os models e o user_loader)
    from .controllers import register_blueprints
    from .cli import register_commands

    register_blueprints(app)
    register_commands(app)
    return app
