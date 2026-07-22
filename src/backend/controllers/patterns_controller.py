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
@patterns_bp.route('/create_pattern', methods=['POST'])
def create_pattern():
    data = request.get_json()
    user_id = data.get('user_id', '')
    pattern_title = data.get('pattern_title', '')
    pattern_summary = data.get('pattern_summary', '')
    entries = data.get('entries', [])  # [{ "entry_id": 11, "date": "...", "rationale": "..." }, ...]
    entities = data.get('entities', [])

    if user_id == '' or pattern_title == '' or pattern_summary == '' or entries == [] or entities == []:
        return jsonify({"message": "Required params not provided"}), 403

    # Validate entry shape up front so bad data doesn't silently create half-populated nodes
    for entry in entries:
        if not all(k in entry for k in ('entry_id', 'date', 'rationale')):
            return jsonify({"message": "Each entry requires entry_id, date, and rationale"}), 403

    query = '''
        MERGE (p:Pattern {
            pattern_title: $pattern_title,
            user_id: $user_id
        })
        ON CREATE SET
            p.pattern_summary = $pattern_summary
        ON MATCH SET
            p.pattern_summary = $pattern_summary
        WITH p
        UNWIND $entries AS entry
        MERGE (en:Entry {
            entry_id: entry.entry_id,
            user_id: $user_id
        })
        ON CREATE SET
            en.date = entry.date
        MERGE (p)-[r:HAS_ENTRY]->(en)
        SET r.rationale = entry.rationale,
            r.date = entry.date
        WITH p, collect(DISTINCT en) AS entries
        UNWIND $entities AS entity
        MERGE (e:Entity {
            entity_id: entity.entity_id,
            user_id: $user_id
        })
        SET e.entity_name = entity.entity_name
        MERGE (p)-[:CONNECTS]->(e)
        RETURN p, entries, collect(DISTINCT e) AS entities;
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
                pattern_summary=pattern_summary,
                user_id=user_id,
                entries=entries,
                entities=entities
            )
            records = [record.data() for record in results.records]
            return jsonify({
                "records": records,
                "summary": results.summary.counters.__dict__,
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

    # entries now live as Entry nodes off HAS_ENTRY, not a list property on
    # Pattern, so use EXISTS the same way entity filtering already does —
    # this also avoids stripping other entries off the aggregated `entries` array.
    if entry_id:
        conditions.append('''
            EXISTS {
                MATCH (p)-[:HAS_ENTRY]->(en2:Entry)
                WHERE en2.entry_id = $entry_id
            }
        ''')
        params["entry_id"] = int(entry_id)

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
    OPTIONAL MATCH (p)-[r:HAS_ENTRY]->(en:Entry)
    WITH
        p,
        collect(DISTINCT {{
            entry_id: en.entry_id,
            date: en.date,
            rationale: r.rationale
        }}) AS entries
    OPTIONAL MATCH (p)-[:CONNECTS]->(e:Entity)
    WITH
        p,
        entries,
        collect(DISTINCT {{
            entity_id: e.entity_id,
            entity_name: e.entity_name
        }}) AS entities

    RETURN {{
        pattern_title: p.pattern_title,
        pattern_summary: p.pattern_summary,
        user_id: p.user_id,
        entries: entries,
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


@patterns_bp.route('/keyword_search', methods=['GET'])
def keyword_search():
    user_id = request.args.get('user_id', '')
    keyword = request.args.get('keyword', '')
    page = max(int(request.args.get('page', 1)), 1)
    page_size = min(int(request.args.get('page_size', 20)), 100)
    if user_id == '' or keyword == '':
        return jsonify({"message": "Missing required params"})
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "user_id must be an integer"})

    keywords = [k for k in keyword.strip().split() if k]
    if not keywords:
        return jsonify({"message": "Missing required params"})

    skip = (page - 1) * page_size
    params = {
        "user_id": user_id,
        "keywords": keywords,
        "skip": skip,
        "limit": page_size,
    }

    query = '''
    MATCH (p:Pattern {user_id: $user_id})
    WHERE ALL(kw IN $keywords WHERE
        toLower(p.pattern_title) CONTAINS toLower(kw)
        OR toLower(coalesce(p.pattern_summary, '')) CONTAINS toLower(kw)
    )
    OPTIONAL MATCH (p)-[r:HAS_ENTRY]->(en:Entry)
    WITH
        p,
        collect(DISTINCT {
            entry_id: en.entry_id,
            date: en.date,
            rationale: r.rationale
        }) AS entries
    OPTIONAL MATCH (p)-[:CONNECTS]->(e:Entity)
    WITH
        p,
        entries,
        collect(DISTINCT {
            entity_id: e.entity_id,
            entity_name: e.entity_name
        }) AS entities
    RETURN {
        pattern_title: p.pattern_title,
        pattern_summary: p.pattern_summary,
        user_id: p.user_id,
        entries: entries,
        entities: entities
    } AS pattern
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
@patterns_bp.route('/add_entity', methods=['POST'])
def add_entity_to_pattern():
    body = request.get_json(silent=True) or {}
    user_id = body.get('user_id', '')
    pattern_name = body.get('pattern_name', '')
    pattern_summary = body.get('pattern_summary', '')
    entity_id = body.get('entity_id', '')
    entity_name = body.get('entity_name', '')
    if user_id == '' or pattern_name == '' or pattern_summary == '' or entity_id == '' or entity_name == '':
        return jsonify({"message": "Missing required params"})
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "user_id must be an integer"})
    params = {
        "user_id": user_id,
        "pattern_name": pattern_name,
        "pattern_summary": pattern_summary,
        "entity_id": entity_id,
        "entity_name": entity_name,
    }
    # MERGE on (user_id, entity_id) so an existing entity is reused/connected
    # instead of a duplicate being created. entity_name is refreshed either way
    # in case it changed (e.g. renamed) since the entity was first created.
    query = '''
    MATCH (p:Pattern {user_id: $user_id, pattern_title: $pattern_name})
    SET p.pattern_summary = $pattern_summary
    MERGE (e:Entity {user_id: $user_id, entity_id: $entity_id})
    ON CREATE SET e.entity_name = $entity_name
    ON MATCH SET e.entity_name = $entity_name
    MERGE (p)-[:CONNECTS]->(e)
    RETURN {
        pattern_title: p.pattern_title,
        pattern_summary: p.pattern_summary,
        entity_id: e.entity_id,
        entity_name: e.entity_name
    } AS result
    '''
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_AUTH, NEO4J_PASSWORD)) as driver:
        try:
            driver.verify_connectivity()
        except Exception as e:
            return jsonify({"message": f"Error: {e}"})
        try:
            records = driver.execute_query(query, **params)
            data = [record for record in records.records]
            if not data:
                return jsonify({
                    "message": f"No pattern found for user_id={user_id} with pattern_name='{pattern_name}'"
                }), 404
            return jsonify({"record": data[0], "message": "Success"})
        except Exception as e:
            return jsonify({"message": f"Database transaction error: {e}"})


@patterns_bp.route('/add_entry', methods=['POST'])
def add_entry_to_pattern():
    body = request.get_json(silent=True) or {}
    user_id = body.get('user_id', '')
    pattern_name = body.get('pattern_name', '')
    pattern_summary = body.get('pattern_summary', '')
    entry_id = body.get('entry_id', '')
    date = body.get('date', '')
    rationale = body.get('rationale', '')

    if user_id == '' or pattern_name == '' or pattern_summary == '' or entry_id == '' or date == '' or rationale == '':
        return jsonify({"message": "Missing required params"})

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "user_id must be an integer"})

    params = {
        "user_id": user_id,
        "pattern_name": pattern_name,
        "pattern_summary": pattern_summary,
        "entry_id": entry_id,
        "date": date,
        "rationale": rationale,
    }

    # Entry is now its own node, so MERGE handles dedup for us: re-adding the
    # same entry_id just matches the existing node/relationship instead of
    # duplicating anything, no CASE guard needed like the old list-property version.
    query = '''
    MATCH (p:Pattern {user_id: $user_id, pattern_title: $pattern_name})
    SET p.pattern_summary = $pattern_summary
    MERGE (en:Entry {entry_id: $entry_id, user_id: $user_id})
    ON CREATE SET en.date = $date
    MERGE (p)-[r:HAS_ENTRY]->(en)
    SET r.rationale = $rationale,
        r.date = $date
    RETURN {
        pattern_title: p.pattern_title,
        pattern_summary: p.pattern_summary,
        entry_id: en.entry_id,
        entry_date: en.date,
        rationale: r.rationale
    } AS result
    '''

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_AUTH, NEO4J_PASSWORD)) as driver:
        try:
            driver.verify_connectivity()
        except Exception as e:
            return jsonify({"message": f"Error: {e}"})
        try:
            records = driver.execute_query(query, **params)
            data = [record for record in records.records]
            if not data:
                return jsonify({
                    "message": f"No pattern found for user_id={user_id} with pattern_name='{pattern_name}'"
                }), 404
            return jsonify({"record": data[0], "message": "Success"})
        except Exception as e:
            return jsonify({"message": f"Database transaction error: {e}"})