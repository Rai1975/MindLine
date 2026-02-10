from flask import jsonify, request, Blueprint
from src.backend.db_config import connect_db
from werkzeug.security import generate_password_hash, check_password_hash
from src.backend.auth import login_required, generate_token

users_bp = Blueprint('users', __name__, url_prefix='/api/users')

@users_bp.route('/create', methods=['POST'])
def new_user():
    cur, conn = connect_db()
    data = request.get_json()
    f_name = data.get('first_name')
    l_name = data.get('last_name')
    uname = data.get('username')
    password = data.get('password')
    email = data.get('email')

    cur.execute(f"SELECT * FROM users WHERE email = \'{email}\'")
    if cur.fetchone():
        return jsonify({'error': 'User already exists'}), 409

    hashed_pwd = generate_password_hash(password)

    try:
        cur.execute('''
                    INSERT INTO users
                    (first_name, last_name, username, email, password) VALUES
                    (%s, %s, %s, %s, %s)
                    ''', (f_name, l_name, uname, email, hashed_pwd))
        conn.commit()

        token = generate_token({"email": email})

        cur.execute('SELECT id FROM users WHERE email = %s', (email,))
        rows = cur.fetchall()
        id = rows[0].get('id')

        cur.close()
        conn.close()
        return jsonify({"message": "Success! New User Created", "token": token, "first_name": f_name, "user_id": id}), 200
    except Exception as e:
        return jsonify({"message": f"Error creating new user: {e}"}), 400

@users_bp.route('/validate', methods=['POST'])
def validate_user():
    cur, conn = connect_db()
    data = request.get_json()
    email_or_uname = data.get('email_or_uname')
    password = data.get('password')

    try:
        cur.execute("SELECT password, id, first_name FROM users WHERE email = %s OR username = %s", (email_or_uname, email_or_uname))
    except Exception as e:
        return jsonify({"message": f"Database transaction error: {e}"}), 400

    rows = cur.fetchall()
    if len(rows) == 0:
        return jsonify({'error': "No User exists with that email or username"}), 400

    hashed_pwd = rows[0].get('password')

    if check_password_hash(hashed_pwd, password):
        token = generate_token({"email": email_or_uname})
        id = rows[0].get('id')
        name = rows[0].get('first_name')

        cur.close()
        conn.close()
        return jsonify({"message": "Valid Credentials! Login Success", "token": token, "name": name, "user_id": id}), 200
    else:
        return jsonify({"message": "Invalid Credentials! Wrong password."}), 200