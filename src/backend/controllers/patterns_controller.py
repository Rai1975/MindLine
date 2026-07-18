from flask import jsonify, request, Blueprint
from src.backend.db_config import run_neo4j_query, run_psql_query
from src.backend.config import NEO4J_AUTH, NEO4J_PASSWORD, NEO4J_URI
from neo4j import GraphDatabase

patterns_bp = Blueprint('patterns', __name__, url_prefix='/api/patterns')


"""
Schema:
pattern_title: string
user_id: integer
entry_ids: [integer]

pattern <-connects(?)-> entity 
"""
# Fix return error
@patterns_bp.route('/create_pattern', methods=['POST'])
def create_pattern():
    data = request.get_json()
    user_id = data.get('user_id', '')
    pattern_title = data.get('pattern_title', '')
    entry_ids = data.get('entry_ids', [])
    entities = data.get('entities', [])

    if user_id == '' or pattern_title == '' or entry_ids == [] or entities==[]:
        return jsonify({"message": "Required params not provided"}), 403
    
    query = '''
        MERGE (p:Pattern {
        pattern_title: $pattern_title,
        user_id: $user_id
    })
    ON CREATE SET
        p.entry_ids = $entry_ids
    ON MATCH SET
        p.entry_ids = REDUCE(
            ids = p.entry_ids,
            id IN $entry_ids |
            CASE
                WHEN id IN ids THEN ids
                ELSE ids + id
            END
        )

    WITH p

    UNWIND $entities AS entity

    MERGE (e:Entity {
        entity_id: entity.entity_id,
        user_id: $user_id
    })
    SET e.entity_name = entity.entity_name

    MERGE (p)-[:CONNECTS]->(e)

    RETURN p, collect(e) AS entities;
    '''

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_AUTH, NEO4J_PASSWORD)) as driver:
        try:
            driver.verify_connectivity()
        except Exception as e:
            return jsonify({"message": f"Error: {e}"})

        try:
            results = driver.execute_query(
                query,
                pattern_title=pattern_title,
                user_id=user_id,
                entry_ids=entry_ids,
                entities=entities
            )
            records = [record.data() for record in results.records]
            return jsonify({
                "records": records,
                "summary": results.summary.counters.__dict__,  # see note below
                "message": "Success"
            })

        except Exception as e:
            return jsonify({"message": f"Error: {e}"})
    

@patterns_bp.route('/find_patterns', methods=['GET'])
def read_patterns():
    user_id = request.args.get('user_id', '')
    pattern_name = request.args.get('pattern_name', '')
    entry_id = request.args.get('entry_id', '')
    entity = request.args.get('entity', '')
    page = max(int(request.args.get('page', 1)), 1)
    page_size = min(int(request.args.get('page_size', 20)), 100)

    if user_id == '':
        return jsonify({"message": "Missing required params"})

    user_id = int(user_id)

    conditions = []
    params = {"user_id": user_id}

    if pattern_name:
        conditions.append("p.pattern_title CONTAINS $pattern_name")
        params["pattern_name"] = pattern_name

    if entry_id:
        # entry_ids is a list property on Pattern; membership check
        conditions.append("$entry_id IN p.entry_ids")
        params["entry_id"] = int(entry_id)

    # Use EXISTS so filtering by entity doesn't strip other entities
    # off the same pattern's aggregated `entities` array.
    if entity:
        conditions.append('''
            EXISTS {
                MATCH (p)-[:CONNECTS]->(e2:Entity)
                WHERE e2.entity_name = $entity
            }
        ''')
        params["entity"] = entity

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    skip = (page - 1) * page_size
    params["skip"] = skip
    params["limit"] = page_size

    query = f'''
    MATCH (p:Pattern {{user_id: $user_id}})
    {where_clause}
    OPTIONAL MATCH (p)-[:CONNECTS]->(e:Entity)

    WITH
        p,
        collect({{
            entity_id: e.entity_id,
            entity_name: e.entity_name
        }}) AS entities

    RETURN {{
        pattern_title: p.pattern_title,
        user_id: p.user_id,
        entry_ids: p.entry_ids,
        entities: entities
    }} AS pattern
    ORDER BY p.pattern_title
    SKIP $skip
    LIMIT $limit
    '''

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_AUTH, NEO4J_PASSWORD)) as driver:
        try:
            driver.verify_connectivity()
        except Exception as e:
            return jsonify({"message": f"Error: {e}"})

        try:
            records = driver.execute_query(query, **params)
            data = [record for record in records.records]
            return jsonify({
                "records": data,
                "page": page,
                "pageSize": page_size,
                "message": "Success"
            })

        except Exception as e:
            return jsonify({"message": f"Error: {e}"})
                
"""
Schema
entity_name: string
entity_id: id
user_id: integer

entity <-connects(?)-> pattern
"""
@patterns_bp.route('/create_entity', methods=['POST'])
def create_object():
    data = request.get_json()
    user_id = data.get('user_id', '')
    pattern_id = data.get('pattern_id', '')
    entity_id = data.get('entity_id', '')
    entity_name = data.get('entity_name', '')

    if user_id == '':
        return jsonify({"message": "User ID is required"})