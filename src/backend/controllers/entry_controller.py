from flask import jsonify, request, Blueprint
from src.backend.db_config import connect_db
from werkzeug.security import generate_password_hash, check_password_hash
from src.backend.auth import login_required, generate_token

entries_bp = Blueprint('entries', __name__, url_prefix='/api/entries')

@entries_bp.route('/create', methods=['POST'])
def new_entry():
    cur, conn = connect_db()
    data = request.get_json()
    user_id = data.get('user_id')
    raw_entry = data.get('raw_entry')

    # Once we implement the AI models to take care of this,
    # we will make this a backend ONLY process.
    cleaned_entry = data.get('cleaned_entry')
    insights = data.get('insights')

    cur.execute("SELECT * FROM users WHERE id = %s", (user_id, ))
    if not cur.fetchone():
        return jsonify({'error': 'User does not exist.'}), 400
    
    try:
        cur.execute('''
                    INSERT INTO journal_entries
                    (user_id, raw_entry, cleaned_entry, insights) VALUES
                    (%s, %s, %s, %s)            
                    ''', (user_id, raw_entry, cleaned_entry, insights))
        
        conn.commit()

        cur.close()
        conn.close()

        return jsonify({"message": "Success! New entry recorded"}), 200
    
    except Exception as e:
        return jsonify({"message": f"Error creating new entry: {e}"})


@entries_bp.route('/read', methods=['GET'])
def read_entry():
    cur, conn = connect_db()
    data = request.get_json()
    user_id = data.get('user_id')
    entry_id = data.get('entry_id')

    cur.execute("SELECT * FROM users WHERE id = %s", (user_id, ))
    if not cur.fetchone():
        return jsonify({'error': 'User does not exist.'}), 400
    
    try:
        cur.execute('''
                    SELECT raw_entry, cleaned_entry, insights 
                    FROM journal_entries
                    WHERE user_id = %s and id = %s
                    ''', (user_id, entry_id))
        
    except Exception as e:
        return jsonify({"message": f"Database transaction error: {e}"})
    
    rows = cur.fetchall()
    if len(rows) == 0:
        return jsonify({"message": "No entry with requested id exists"})

    else:
        return jsonify({"entry": rows})