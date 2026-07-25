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

@patterns_bp.route('/search_by_entity', methods=['GET'])
def search_by_entity():
    user_id = request.args.get('user_id', '')
    entity_name = request.args.get('entity_name', '')
    page = max(int(request.args.get('page', 1)), 1)
    page_size = min(int(request.args.get('page_size', 20)), 100)

    if user_id == '' or entity_name == '':
        return jsonify({"message": "Missing required params"})

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "user_id must be an integer"})

    skip = (page - 1) * page_size
    params = {
        "user_id": user_id,
        "entity_name": entity_name,
        "skip": skip,
        "limit": page_size,
    }

    # Start at the Entity, walk CONNECTS back to each Pattern it's attached
    # to, then pull that Pattern's own HAS_ENTRY entries — entities don't
    # have entries, patterns do.
    query = '''
    MATCH (e:Entity {user_id: $user_id, entity_name: $entity_name})
    MATCH (e)<-[:CONNECTS]-(p:Pattern)
    OPTIONAL MATCH (p)-[r:HAS_ENTRY]->(en:Entry)
    WITH
        e,
        p,
        collect(DISTINCT {
            entry_id: en.entry_id,
            date: en.date,
            rationale: r.rationale
        }) AS entries
    RETURN {
        entity_id: e.entity_id,
        entity_name: e.entity_name,
        pattern_title: p.pattern_title,
        pattern_summary: p.pattern_summary,
        entries: entries
    } AS result
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
            if not data:
                return jsonify({
                    "message": f"No entity found for user_id={user_id} with entity_name='{entity_name}'"
                }), 404
            return jsonify({
                "records": data,
                "page": page,
                "pageSize": page_size,
                "message": "Success"
            })
        except Exception as e:
            return jsonify({"message": f"Database transaction error: {e}"})

# I am manually running the agent to insert data for this now. But eventually this will be automated haha.   
@patterns_bp.route('/entity_details', methods=['GET'])
def get_entity_details():
    user_id = request.args.get('user_id', '')
    entity_name = request.args.get('entity_name', '')
    if user_id == '' or entity_name == '':
        return jsonify({"message": "Missing required params"})
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "user_id must be an integer"})
    params = {"user_id": user_id, "entity_name": entity_name}

    # Pattern has no dedicated pattern_id field — pattern_title is the only
    # unique identifier (alongside user_id), so related_patterns is just a
    # flat list of titles rather than {pattern_id, pattern_name} objects.
    #
    # related_entities walks e -> patterns -> other entities on those same
    # patterns, excluding e itself and deduping across patterns (an entity
    # co-occurring in 3 shared patterns still shows up once).
    #
    # insight_1/2/3 are collected into a list and filtered of nulls so a
    # partially-filled or never-generated insight set doesn't leak None
    # entries into the response.
    query = '''
    MATCH (e:Entity {user_id: $user_id, entity_name: $entity_name})
    OPTIONAL MATCH (e)<-[:CONNECTS]-(p:Pattern)
    WITH e, collect(DISTINCT p.pattern_title) AS related_patterns,
    collect(DISTINCT p) AS patterns
    UNWIND (CASE WHEN patterns = [] THEN [null] ELSE patterns END) AS pat
    OPTIONAL MATCH (pat)-[:CONNECTS]->(e2:Entity)
    WHERE pat IS NOT NULL AND e2.entity_id <> e.entity_id
    WITH e, related_patterns, collect(DISTINCT {
        entity_id: e2.entity_id,
        entity_name: e2.entity_name
    }) AS related_entities_raw
    RETURN {
        entity_id: e.entity_id,
        entity_name: e.entity_name,
        related_patterns: related_patterns,
        related_entities: [x IN related_entities_raw WHERE x.entity_id IS NOT NULL],
        bullets: [b IN [e.insight_1, e.insight_2, e.insight_3] WHERE b IS NOT NULL]
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
                    "message": f"No entity found for user_id={user_id} with entity_name='{entity_name}'"
                }), 404
            return jsonify({"record": data[0], "message": "Success"})
        except Exception as e:
            return jsonify({"message": f"Database transaction error: {e}"})

@patterns_bp.route('/related_patterns', methods=['GET'])
def get_related_patterns():
    user_id = request.args.get('user_id', '')
    pattern_name = request.args.get('pattern_name', '')

    if user_id == '' or pattern_name == '':
        return jsonify({"message": "Missing required params"})

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "user_id must be an integer"})

    params = {"user_id": user_id, "pattern_name": pattern_name}

    # There's no direct Pattern-Pattern edge in the schema, so "related" is
    # inferred two ways:
    #   1. via_entity  — other patterns CONNECTS-ed to an entity this pattern
    #      is also CONNECTS-ed to (e.g. both patterns involve "Liam")
    #   2. via_entry   — other patterns HAS_ENTRY-linked to an entry this
    #      pattern is also linked to (e.g. the same journal entry evidences
    #      both patterns)
    # Both are gathered separately, then merged/deduped per related pattern
    # so a pattern related through both an entity AND an entry only shows up
    # once, with both shared_entities and shared_entries populated.
    query = '''
    MATCH (p:Pattern {user_id: $user_id, pattern_title: $pattern_name})

    OPTIONAL MATCH (p)-[:CONNECTS]->(e:Entity)<-[:CONNECTS]-(p2:Pattern)
    WHERE p2.user_id = $user_id AND p2.pattern_title <> $pattern_name
    WITH p, collect(DISTINCT {pattern: p2, entity_name: e.entity_name}) AS via_entity

    OPTIONAL MATCH (p)-[:HAS_ENTRY]->(en:Entry)<-[:HAS_ENTRY]-(p3:Pattern)
    WHERE p3.user_id = $user_id AND p3.pattern_title <> $pattern_name
    WITH p, via_entity, collect(DISTINCT {pattern: p3, entry_id: en.entry_id}) AS via_entry

    WITH p,
        [x IN via_entity WHERE x.pattern IS NOT NULL] AS via_entity,
        [x IN via_entry WHERE x.pattern IS NOT NULL] AS via_entry

    UNWIND (
        [x IN via_entity | x.pattern] + [x IN via_entry | x.pattern]
    ) AS related_pattern
    WITH p, via_entity, via_entry, related_pattern
    WHERE related_pattern IS NOT NULL

    WITH p, related_pattern,
        [x IN via_entity WHERE x.pattern = related_pattern | x.entity_name] AS shared_entities,
        [x IN via_entry WHERE x.pattern = related_pattern | x.entry_id] AS shared_entries

    RETURN {
        pattern_title: related_pattern.pattern_title,
        pattern_summary: related_pattern.pattern_summary,
        shared_entities: shared_entities,
        shared_entries: shared_entries
    } AS result
    ORDER BY related_pattern.pattern_title
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
                    "message": f"No related patterns found for pattern_name='{pattern_name}'"
                }), 404
            return jsonify({"records": data, "message": "Success"})
        except Exception as e:
            return jsonify({"message": f"Database transaction error: {e}"})

@patterns_bp.route('/connect_patterns', methods=['POST'])
def connect_patterns():
    user_id = request.args.get('user_id', '')
    pattern_name_1 = request.args.get('pattern_name_1', '')
    pattern_name_2 = request.args.get('pattern_name_2', '')
    rationale = request.args.get('rationale', '')
    if user_id == '' or pattern_name_1 == '' or pattern_name_2 == '':
        return jsonify({"message": "Missing required params"})
    if pattern_name_1 == pattern_name_2:
        return jsonify({"message": "pattern_name_1 and pattern_name_2 must be different patterns"})
    if rationale == '':
        return jsonify({"message": "Missing required param: rationale"})
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "user_id must be an integer"})
    params = {
        "user_id": user_id,
        "pattern_name_1": pattern_name_1,
        "pattern_name_2": pattern_name_2,
        "rationale": rationale
    }
    # Creates (or updates) a single, undirected RELATED_TO relationship
    # between the two Pattern nodes. MERGE on an undirected pattern
    # (p1)-[r]-(p2) will match an existing edge regardless of which
    # direction it was originally created in, so calling this with
    # (A, B) or (B, A) always resolves to the same relationship — no
    # duplicate edges, no need to track order. If no edge exists yet,
    # Neo4j creates one with an arbitrary internal direction, but since
    # every read in this codebase matches undirected, that internal
    # direction is never semantically meaningful.
    query = '''
    MATCH (p1:Pattern {user_id: $user_id, pattern_title: $pattern_name_1})
    MATCH (p2:Pattern {user_id: $user_id, pattern_title: $pattern_name_2})
    MERGE (p1)-[r:RELATED_TO]-(p2)
    ON CREATE SET r.rationale = $rationale, r.created_at = datetime()
    ON MATCH SET r.rationale = $rationale, r.updated_at = datetime()
    RETURN {
        pattern_1: p1.pattern_title,
        pattern_2: p2.pattern_title,
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
                    "message": f"Could not connect patterns — one or both patterns not found "
                               f"('{pattern_name_1}', '{pattern_name_2}')"
                }), 404
            return jsonify({"records": data, "message": "Success"})
        except Exception as e:
            return jsonify({"message": f"Database transaction error: {e}"})

@patterns_bp.route('/connected_patterns', methods=['GET'])
def get_connected_patterns():
    user_id = request.args.get('user_id', '')
    pattern_name = request.args.get('pattern_name', '')
    if user_id == '' or pattern_name == '':
        return jsonify({"message": "Missing required params"})
    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "user_id must be an integer"})
    params = {"user_id": user_id, "pattern_name": pattern_name}
    # RELATED_TO is created directionally (p1 -> p2) by connect_patterns, but
    # conceptually the relationship is symmetric — "A is related to B" implies
    # "B is related to A". So we match the relationship in either direction
    # here, rather than assuming this pattern is always the source.
    query = '''
    MATCH (p:Pattern {user_id: $user_id, pattern_title: $pattern_name})
    MATCH (p)-[r:RELATED_TO]-(p2:Pattern)
    WHERE p2.user_id = $user_id AND p2.pattern_title <> $pattern_name
    RETURN {
        pattern_title: p2.pattern_title,
        pattern_summary: p2.pattern_summary,
        rationale: r.rationale
    } AS result
    ORDER BY p2.pattern_title
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
                    "message": f"No connected patterns found for pattern_name='{pattern_name}'"
                }), 404
            return jsonify({"records": data, "message": "Success"})
        except Exception as e:
            return jsonify({"message": f"Database transaction error: {e}"})