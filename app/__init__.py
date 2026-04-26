from flask import Flask

def create_app():
    app = Flask(__name__)

    # Инициализируем SQLite при старте
    from .database import init_db
    init_db()

    from .routes import bar_bp
    app.register_blueprint(bar_bp)

    from .promo import promo_bp
    app.register_blueprint(promo_bp)

    return app
