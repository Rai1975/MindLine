from flask import Blueprint, Flask
from flask_cors import CORS
from src.backend.controllers.users_controller import users_bp
from src.backend.controllers.entry_controller import entries_bp
from src.backend.controllers.stim_controller import stims_bp
from src.backend.controllers.patterns_controller import patterns_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(users_bp)
app.register_blueprint(entries_bp)
app.register_blueprint(stims_bp)
app.register_blueprint(patterns_bp)

@app.route('/')
def home():
    return "Welcome!"

if __name__ == "__main__":
    app.run(debug=False)