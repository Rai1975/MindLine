from flask import jsonify, request, Blueprint
from src.backend.db_config import connect_sql_db, run_psql_query
from src.backend.controllers.users_controller import new_user
from math import ceil

stims_bp = Blueprint('stimuli', __name__, url_prefix='/api/stims')

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

@stims_bp.route('/getEntityStims', methods=['GET'])
def get_entity_stims():
    entity_id = request.args.get('entity_id')
    user_id = request.args.get('user_id')
    page = int(request.args.get('page'))
    pageSize = int(request.args.get('pageSize'))

    offset = (page - 1) * pageSize

    query = '''
        SELECT
        s.entity,
        se.adjective,
        se.sentence,
        se.sentence_sentiment,
        se.adjective_sentiment,
        se.e1,
        se.e2,
        se.e3
    FROM stimuli s
    JOIN stimuli_emotions se
        ON se.entity_id = s.id
    WHERE s.id = %s
    AND se.user_id = %s
    ORDER BY se.id
    LIMIT %s
    OFFSET %s;
    '''

    values = (entity_id, user_id, pageSize, offset)

    result = run_psql_query(query, values, insert=False)

    res = {}
    data = []

    if len(result):
        for object in result:
            data.append(
                {
                    "entity": object.get('entity'),
                    "adjective": object.get('adjective'),
                    "sentence": object.get('sentence'),
                    "sentence_sentiment": object.get('sentence_sentiment'),
                    "adjective_sentiment": object.get('adjective_sentiment'),
                    "e1": object.get('e1'),
                    "e2": object.get('e2'),
                    "e3": object.get('e3')
                }
            )

        res = {
            "page": page,
            "pageSize": pageSize,
            "data": data
        }

    else:
        res = {
            "page": page,
            "pageSize": pageSize,
            "data": []
        }

    return res