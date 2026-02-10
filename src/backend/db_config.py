from src.backend.config import DB_PORT, DB_NAME, DB_HOST, DB_PASSWORD, DB_USER
import psycopg2
from psycopg2.extras import RealDictCursor

print("Touched")

# Database Connection
try:
    def connect_db():
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
    print("Connection Failed: ", e)