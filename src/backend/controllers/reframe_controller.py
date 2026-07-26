from flask import jsonify, request, Blueprint
from src.backend.db_config import connect_sql_db, run_neo4j_query, run_psql_query
from werkzeug.security import generate_password_hash, check_password_hash
from src.backend.auth import login_required, generate_token
from src.backend.utils import redis_client
import json

reframe_bp = Blueprint('reflect', __name__, url_prefix='/api/reflect')


@reframe_bp.route('/read', methods=['GET'])
def read_reflects():
    user_id = request.args.get('user_id', '')
    entry_id = request.args.get('entry_id', '')

    if user_id == '' or entry_id == '':
        return jsonify({
            "message": "User ID and entry ID are both required."
        }), 400

    # Create a unique cache key for this user's entry
    cache_key = f"reflect:{user_id}:{entry_id}"

    # Check Redis cache first
    cached_data = redis_client.get(cache_key)

    if cached_data:
        return jsonify({
            "message": "Success",
            "data": json.loads(cached_data),
            "cached": True
        }), 200

    query = """
    SELECT entry_id, user_id, question
    FROM reflect
    WHERE user_id = %s AND entry_id = %s
    """

    cur = None
    conn = None

    try:
        cur, conn = connect_sql_db()

        cur.execute(query, (user_id, entry_id))
        results = cur.fetchall()

        # Convert DB results into JSON-serializable data
        # This assumes your cursor returns dictionaries.
        # If it returns tuples, see note below.
        cache_data = json.dumps(results, default=str)

        # Cache for 5 minutes
        redis_client.setex(
            cache_key,
            300,
            cache_data
        )

    except Exception as e:
        return jsonify({
            "message": f"There has been an error: {e}"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return jsonify({
        "message": "Success",
        "data": results,
        "cached": False
    }), 200


@reframe_bp.route('/write', methods=['POST'])
def write_reflect():
    data = request.get_json()

    user_id = data.get('user_id', '')
    entry_id = data.get('entry_id', '')
    question = data.get('question', '')

    if user_id == '' or entry_id == '' or question == '':
        return jsonify({
            "message": "User ID, Entry ID and question are required fields"
        }), 400

    query = """
    INSERT INTO reflect (user_id, entry_id, question)
    VALUES (%s, %s, %s)
    RETURNING id
    """

    cur = None
    conn = None

    try:
        cur, conn = connect_sql_db()

        cur.execute(query, (user_id, entry_id, question))
        results = cur.fetchall()
        conn.commit()

        # Invalidate the cached GET response
        cache_key = f"reflect:{user_id}:{entry_id}"
        redis_client.delete(cache_key)

    except Exception as e:
        return jsonify({
            "message": f"Error: {e}"
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return jsonify({
        "message": "Success",
        "data": results
    }), 200