from src.backend.db_config import connect_sql_db
import bcrypt

class User:
    firstName = ""
    lastName = ""
    id = ""
    userName = ""
    email = ""

    def __init__(self, firstName, lastName, email, userName, password):
        self.firstName = firstName
        self.lastName = lastName
        self.email = email
        self.userName = userName
        self.password_hash = self._hash_password(password)

    def _hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def save(self):
        cur, conn = connect_sql_db()
        cur.execute(
            """
            INSERT INTO "Users" ("firstName", "lastName", "email", "userName", "password")
            VALUES (%s, %s, %s, %s, %s)
            RETURNING "id"
            """,
            (self.firstName, self.lastName, self.email, self.userName, self.password_hash)
        )
        self.id = cur.fetchone().get('id')
        conn.commit()
        cur.close()
        conn.close()

    def get(self, id=None, username=None, email=None):
        if not any([id, username, email]):
            raise ValueError("Must provide at least one of: id, username, or email")

        cur, conn = connect_sql_db()

        if id:
            cur.execute("SELECT * FROM users WHERE id = %s", (id,))
        elif username:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        elif email:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return None

        self.id, self.firstName, self.lastName, self.email, self.userName, self.password_hash = row
        return self

    @staticmethod
    def verify_password(plain_password: str, stored_hash: str) -> bool:
        return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8"))