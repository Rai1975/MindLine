from flask import jsonify, request, Blueprint
from src.backend.entry_analysis.text_operations import textCleaner as textPipeline
from src.backend.entry_analysis.pipeline import final_pipeline as finalPipeline
from src.backend.controllers.stim_controller import new_stim, new_dropped_stim
from src.backend.db_config import connect_sql_db, run_neo4j_query, run_psql_query
from werkzeug.security import generate_password_hash, check_password_hash
from src.backend.auth import login_required, generate_token
from src.backend.classes.entry import Entry
from src.backend.classes.stimulus import Stimulus
import threading

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
            'UPDATE journal_entries SET cleaned_entry = %s, search_vector=to_tsvector(\'english\', %s) WHERE id = %s',
            (cleaned_entry, cleaned_entry, entry_id)
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
def read_entries():
    cur, conn = connect_sql_db()
    includeRawEntry = request.args.get('includeRawEntry', 0)
    user_id = request.args.get('user_id', '')
    entry_id = request.args.get('entry_id', '')
    fromDate = request.args.get('from_date', '')
    toDate = request.args.get('to_date', '')
    entity = request.args.get('entity', '')
    emotion = request.args.get('emotion', '')
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(int(request.args.get("page_size", 20)), 100)

    if user_id == '':
        return jsonify({'error': 'User ID not provided'}), 400

    cur.execute("SELECT * FROM \"Users\" WHERE id = %s", (user_id, ))
    if not cur.fetchone():
        return jsonify({'error': 'User does not exist.'}), 400

    conditions = ["je.user_id = %s"]
    params = [int(user_id)]

    query = '''
        SELECT
            je.id,
            je.cleaned_entry,
            je.reframe,

    '''

    if int(includeRawEntry):
        query += "je.raw_entry,"
    

    query += '''
            jsonb_agg(DISTINCT jsonb_build_object('id', s.id, 'entity', s.entity)) AS entities,
            COUNT(*) OVER() AS total_records
        FROM journal_entries je
        JOIN stimuli_emotions se ON se.entry_id = je.id AND se.user_id = je.user_id
        JOIN stimuli s ON s.user_id = je.user_id AND se.entity_id = s.id
    '''

    try:
        if entry_id:
            conditions.append('je.id = %s')
            params.append(entry_id)

        if fromDate:
            fromDate += ' 00:00:00'
            conditions.append('je.created_at >= %s')
            params.append(fromDate)

        if toDate:
            toDate += ' 23:59:59'
            conditions.append('je.created_at <= %s')
            params.append(toDate)

        # Use EXISTS so filtering by entity doesn't strip other entities
        # off the same entry's aggregated `entities` array.
        if entity:
            conditions.append('''
                EXISTS (
                    SELECT 1
                    FROM stimuli_emotions se2
                    JOIN stimuli s2 ON s2.user_id = se2.user_id AND s2.id = se2.entity_id
                    WHERE se2.entry_id = je.id
                      AND se2.user_id = je.user_id
                      AND s2.entity = %s
                )
            ''')
            params.append(entity)

        # Fixed: OR across e1/e2/e3, not AND — and also wrapped in EXISTS
        # for the same reason as above.
        if emotion:
            conditions.append('''
                EXISTS (
                    SELECT 1
                    FROM stimuli_emotions se3
                    WHERE se3.entry_id = je.id
                      AND se3.user_id = je.user_id
                      AND (se3.e1 = %s OR se3.e2 = %s OR se3.e3 = %s)
                )
            ''')
            params.extend([emotion, emotion, emotion])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # GROUP BY goes here — after WHERE, before ORDER BY/LIMIT.
        # je.id alone is enough (Postgres functional dependency on PK).
        query += " GROUP BY je.id "

        offset = (page - 1) * page_size
        query += """
            ORDER BY je.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        cur.execute(query, tuple(params))

    except Exception as e:
        return jsonify({"message": f"Database transaction error: {e}"})

    rows = cur.fetchall()
    totalCount = rows[0].get('total_records') if rows else 0

    return jsonify({
        "entries": rows,
        "page": page,
        "pageSize": page_size,
        "total_count": totalCount
        }), 200


@entries_bp.route('/readCount', methods=['GET'])
def read_entry_stim_count():
    cur, conn = connect_sql_db()
    fromDate = request.args.get('fromDate', '')
    toDate = request.args.get('toDate', '')
    user_id = request.args.get('user_id', '')
    limit = min(int(request.args.get('limit', 10)), 100)

    if user_id == '':
        return jsonify({"message": "User ID needs to be provided"}), 400

    conditions = ["je.user_id = %s"]
    params = [int(user_id)]

    if fromDate:
        fromDate += ' 00:00:00'
        conditions.append('je.created_at >= %s')
        params.append(fromDate)
    if toDate:
        toDate += ' 23:59:59'
        conditions.append('je.created_at <= %s')
        params.append(toDate)

    query = '''
        SELECT
            s.id,
            s.entity,
            COUNT(*) AS occurrence_count
        FROM stimuli_emotions se
        JOIN stimuli s ON s.user_id = se.user_id AND s.id = se.entity_id
        JOIN journal_entries je ON je.id = se.entry_id AND je.user_id = se.user_id
    '''

    try:
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += '''
            GROUP BY s.id, s.entity
            ORDER BY occurrence_count DESC
            LIMIT %s
        '''
        params.append(limit)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

    except Exception as e:
        return jsonify({"message": f"Database transaction error: {e}"}), 500

    finally:
        cur.close()
        conn.close()

    return jsonify({
        "top_stims": rows,
        "count": len(rows)
    }), 200

@entries_bp.route('/update', methods=['POST'])
def update_entry():
    data = request.get_json()
    user_id = data.get('user_id')
    entry_id = data.get('entry_id')
    updated_text = data.get('updated_text')
    cur, conn = connect_sql_db()

    # TODO: Test this more pls
    try:
        cur.execute(
                '''
                UPDATE journal_entries
                SET raw_entry = %s
                WHERE user_id = %s AND id = %s
                ''',
                (updated_text, user_id, entry_id)
        )
        conn.commit()

        cleaned_entry = textPipeline(text=updated_text)


        cur.execute(
            'UPDATE journal_entries SET cleaned_entry = %s WHERE id = %s',
            (cleaned_entry, entry_id)
        )
        conn.commit()

        # Now clean up existing stims for the entry
        cur.execute(
            'DELETE FROM stimuli_emotions WHERE entry_id = %s',
            (entry_id,)
        )

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


        return jsonify({"message": "Success! Entry updated"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"message": f"Error updating entry: {e}"}), 500

    finally:
        cur.close()
        conn.close()

@entries_bp.route('/keywordSearch', methods=["POST"])
def keyword_search():
    data = request.get_json()
    user_id = data.get('user_id')
    keyword = data.get('keyword')
    try:
        entry_query = '''
        SELECT je.cleaned_entry, je.id
        FROM journal_entries je
        WHERE user_id = %s
        AND search_vector @@ plainto_tsquery('english', %s);
        '''
        results = run_psql_query(entry_query, (user_id, keyword))
        if not results:
            return jsonify([])

        entry_ids = [entry.get('id') for entry in results]

        entity_query = '''
        SELECT se.entry_id, s.entity, se.sentence
        FROM stimuli_emotions se
        JOIN stimuli s ON se.entity_id = s.id
        WHERE se.entry_id = ANY(%s)
        '''
        stim_results = run_psql_query(entity_query, (entry_ids,))

        # Group stims by entry_id
        stims_by_entry = {}
        for stim in stim_results:
            eid = stim.get('entry_id')
            stims_by_entry.setdefault(eid, []).append({
                "entity": stim.get('entity'),
                "sentence": stim.get('sentence')
            })

        output = [
            {
                "entry": entry.get('cleaned_entry'),
                "stims": stims_by_entry.get(entry.get('id'), [])
            }
            for entry in results
        ]
        return jsonify(output)

    except Exception as e:
        return jsonify({"error": str(e)}), 500