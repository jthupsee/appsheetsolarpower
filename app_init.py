import os
import logging
from flask import Flask
from routes import register_routes

def create_initialized_flask_app():
    app = Flask(__name__, static_folder='static')

    # Set Flask secret key
    app.config['SECRET_KEY'] = 'supersecretflaskskey'

    register_routes(app)

    return app