from flask import jsonify, request, Blueprint
from src.backend.db_config import connect_sql_db, run_psql_query
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

    # Check for existing stim
    existing = find_existing_entity(entity)
    if len(existing):
        entity_id = existing[0].get('id')
    else:
        entity_id = new_entity(entity, user_id)[0].get('id')

    query = '''
        INSERT INTO "stimuli_emotions" (entity_id, adjective, sentence, sentence_sentiment, adjective_sentiment, e1, e2, e3, user_id, entry_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    '''
    cur, conn = connect_sql_db()
    try:
        cur.execute(query, (entity_id, adjective, sentence, sentence_sentiment, adjective_sentiment, e1, e2, e3, user_id, entry_id))
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

def new_dropped_stim(
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
        INSERT INTO "dropped_stimuli" (entity, adjective, sentence, sentence_sentiment, adjective_sentiment, e1, e2, e3, user_id, entry_id)
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

def find_existing_entity(token):
    query = '''
        SELECT id, entity, similarity(entity, %s) as score
        FROM "stimuli"
        WHERE similarity(entity, %s) > 0.7
    '''

    cur, conn = connect_sql_db()

    try:
        cur.execute(query, (token,token))
        results = cur.fetchall()
        returnList = []
        if len(results):
            for entity in results:
                returnList.append({"entity": entity.get('entity'), "score": entity.get('score'), "id": entity.get('id')})
    except Exception as e:
        print(f"{e}")
    finally:
        cur.close()
        conn.close()

    return returnList

def new_entity(entity, user_id):
    query = '''
        INSERT INTO "stimuli"
        (entity, user_id)
        VALUES (%s, %s)
        RETURNING ID
    '''

    values = (entity, user_id)

    result = run_psql_query(query, values, insert=True)

    return result