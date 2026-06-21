from flask import jsonify, request, Blueprint
from src.backend.db_config import connect_sql_db
from src.backend.controllers.users_controller import new_user

stims_bp = Blueprint('strimuli', __name__, url_prefix='/api/stims')

def new_stim(
        entity,
        adjective,
        sentence,
        sentence_sentiment,
        adjective_sentiment,
        e1,
        e2,
        e3,
        user_id,
        entry_id
    ):

    query = '''
        INSERT INTO "stimuli" (entity, adjective, sentence, sentence_sentiment, adjective_sentiment, e1, e2, e3, user_id, entry_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    '''
    cur, conn = connect_sql_db()
    try:
        cur.execute(query, (entity, adjective, sentence, sentence_sentiment, adjective_sentiment, e1, e2, e3, user_id, entry_id))
        result = cur.fetchall()
        stim_id = result[0].get('id')
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"{e}"
    finally:
        cur.close()
        conn.close()

    return stim_id


