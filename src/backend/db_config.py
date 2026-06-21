from src.backend.config import DB_PORT, DB_NAME, DB_HOST, DB_PASSWORD, DB_USER, NEO4J_PASSWORD, NEO4J_AUTH, NEO4J_URI
import psycopg2
from psycopg2.extras import RealDictCursor
from neo4j import GraphDatabase

# Database Connection
def connect_sql_db():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            cursor_factory=RealDictCursor
        )
        cur = conn.cursor()
        return cur, conn

    except Exception as e:
        return("Connection Failed: ", e)

def run_psql_query(query, values = (), insert=False):
    cur, conn = connect_sql_db()
    results = []

    if (len(values)):
        try:
            cur.execute(query, values)
            results = cur.fetchall()
            if insert:
                conn.commit()
        except Exception as e:
            if insert:
                conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()
    else:
        try:
            cur.execute(query)
            results = cur.fetchall()
            if insert:
                conn.commit()
        except Exception as e:
            if insert:
                conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    return results

def run_neo4j_query(query):
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_AUTH, NEO4J_PASSWORD)) as driver:
        try:
            driver.verify_connectivity()
        except Exception as e:
            return {"message": f"Error: {e}"}

        try:
            records, summary, keys = driver.execute_query(query)

            return {"records": records, "summary": summary, "keys": keys, "message": "Success"}

        except Exception as e:
            return {"message": f"Error: {e}"}