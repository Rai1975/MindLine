from flask import Blueprint, Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Welcome!"

if __name__ == "__main__":
    app.run(port=8080, debug=False)