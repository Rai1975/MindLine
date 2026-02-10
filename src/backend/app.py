from flask import Blueprint, Flask
from flask_cors import CORS
from src.backend.controllers.users_controller import users_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(users_bp)

@app.route('/')
def home():
    return "Welcome!"

if __name__ == "__main__":
    app.run(debug=True)