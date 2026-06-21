from flask import jsonify, request, Blueprint
from src.backend.entry_analysis.text_operations import textCleaner as textPipeline
import threading
from src.backend.entry_analysis.pipeline import final_pipeline as finalPipeline
from src.backend.controllers.stim_controller import new_stim
from src.backend.db_config import connect_sql_db, run_neo4j_query
from werkzeug.security import generate_password_hash, check_password_hash
from src.backend.auth import login_required, generate_token
from src.backend.classes.entry import Entry
from src.backend.classes.stimulus import Stimulus

entries_bp = Blueprint('entries', __name__, url_prefix='/api/entries')

@entries_bp.route('/create', methods=['POST'])
def new_entry():
    cur, conn = connect_sql_db()
    data = request.get_json()

    user_id = data.get('user_id')
    raw_entry = data.get('raw_entry')

    cur.execute('SELECT * FROM "Users" WHERE "id" = %s', (user_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({'error': 'User does not exist.'}), 400

    try:
        cur.execute(
            '''
            INSERT INTO journal_entries (user_id, raw_entry)
            VALUES (%s, %s)
            RETURNING id
            ''',
            (user_id, raw_entry)
        )
        result = cur.fetchall()
        entry_id = result[0].get('id')
        conn.commit()

        cleaned_entry = textPipeline(text=raw_entry)


        cur.execute(
            'UPDATE journal_entries SET cleaned_entry = %s WHERE id = %s',
            (cleaned_entry, entry_id)
        )
        conn.commit()

        model_output = finalPipeline(text=cleaned_entry)
        for ep in model_output.significant_pairs:
            try:
                id = new_stim(
                    entity = ep.entity,
                    adjective=ep.adjective,
                    sentence = ep.sentence,
                    sentence_sentiment = ep.sentence_sentiment,
                    adjective_sentiment = ep.adjective_sentiment,
                    e1 = ep.emotion1,
                    e2 = ep.emotion2,
                    e3 = ep.emotion3,
                    user_id = user_id,
                    entry_id = entry_id
                )
            except Exception as e:
                return jsonify({"message": f"Error: {e}"}, 400)

        return jsonify({"message": "Success! New entry recorded"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"message": f"Error creating new entry: {e}"}), 500

    finally:
        cur.close()
        conn.close()

@entries_bp.route('/read', methods=['GET'])
def read_entry():
    cur, conn = connect_sql_db()
    data = request.get_json()
    # Again, will be gone
    user_id = data.get('user_id')
    entry_id = data.get('entry_id')

    cur.execute("SELECT * FROM users WHERE id = %s", (user_id, ))
    if not cur.fetchone():
        return jsonify({'error': 'User does not exist.'}), 400
    
    try:
        cur.execute('''
                    SELECT raw_entry, cleaned_entry
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