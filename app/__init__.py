from flask import Flask

def create_app():
    app = Flask(__name__)
    from .routes import bar_bp
    app.register_blueprint(bar_bp)
    return app
