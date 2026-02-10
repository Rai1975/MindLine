from flask import jsonify, request
from functools import wraps
import jwt
import datetime
from src.backend.config import JWT_SECRET

ALGORITHM = "HS256"

def generate_token(payload, expires_in=3600):
    payload = payload.copy()
    payload["exp"] = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=expires_in)
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"message": "Missing or invalid token"}), 401

        token = auth_header.replace("Bearer ", "")
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 403

        request.user = decoded
        return f(*args, **kwargs)

    return decorated_function

def verify_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# if __name__ == "__main__":
#     payload = {"email": "rafeekrn@mail.uc.edu"}
#     print(generate_token(payload))