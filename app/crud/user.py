from app.db.cockroach import get_connection
from app.schema.user import UserCreate

def create_user(user: UserCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (name, email, phone, password, role)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
            """, (user.name, user.email, user.phone, user.password, user.role))
            new_user = cur.fetchone()
        conn.commit()
        return new_user

def get_all_users():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE del_flg = 0;")
            return cur.fetchall()

def get_user_by_id(user_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s AND del_flg = 0;", (user_id,))
            return cur.fetchone()