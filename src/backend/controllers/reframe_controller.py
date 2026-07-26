from flask import jsonify, request, Blueprint
from src.backend.db_config import connect_sql_db, run_neo4j_query, run_psql_query
from werkzeug.security import generate_password_hash, check_password_hash
from src.backend.auth import login_required, generate_token

reframe_bp = Blueprint('reflect', __name__, url_prefix='/api/reflect')

@reframe_bp.route('/read', methods=['GET'])
def read_reflects():
    user_id = request.args.get('user_id', '')
    entry_id = request.args.get('entry_id', '')

    if user_id == '' or entry_id == '':
        return jsonify({"message": "User ID and entry ID are both required."})

    query = """
    SELECT entry_id, user_id, question
    FROM reflect
    WHERE user_id = %s AND entry_id = %s
    """

    try:
        cur, conn = connect_sql_db()

        cur.execute(query, (user_id, entry_id))
        results = cur.fetchall()
    
    except Exception as e:
        return jsonify({"message": f"There has been an error: {e}"})
    
    finally:
        cur.close()
        conn.close()
    
    return jsonify({"message": "Success", "data": results})

@reframe_bp.route('/write', methods=['POST'])
def write_reflect():
    data = request.get_json()

    user_id = data.get('user_id', '')
    entry_id = data.get('entry_id', '')
    question = data.get('question', '')

    if user_id == '' or entry_id == '' or question == '':
        return jsonify({"message": "User ID, Entry ID and question are required fields"})
    
    query = """
    INSERT INTO
    reflect (user_id, entry_id, question)
    VALUES (%s, %s, %s)
    RETURNING id
    """

    try:
        cur, conn = connect_sql_db()

        cur.execute(query, (user_id, entry_id, question))
        results = cur.fetchall()
        conn.commit()
    
    except Exception as e:
        return jsonify({"message": f"Error: {e}"})
    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "Success", "data": results})