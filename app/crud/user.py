from app.db.cockroach import get_connection
from app.schema.user import UserCreate, UserUpdate
from app.core.security import get_password_hash
from typing import List, Dict, Any, Optional


def _row_to_dict(cur, row):
    """Chuyển row (tuple) từ cursor thành dict theo tên cột."""
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def create_user(user: UserCreate):
    password = get_password_hash(user.password)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (name, email, phone, password, role)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
            """, (user.name, user.email, user.phone, password, user.role))
            row = cur.fetchone()
            new_user = _row_to_dict(cur, row)
        conn.commit()
        return new_user


def get_user_by_email(email: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s AND del_flg = 0;", (email,))
            row = cur.fetchone()
            return _row_to_dict(cur, row)


def get_all_users(page: int = 1, page_size: int = 128):
    offset = (page - 1) * page_size
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(user_id) FROM users WHERE del_flg = 0;")
            total = cur.fetchone()[0]

            cur.execute("SELECT * FROM users WHERE del_flg = 0 ORDER BY created_date DESC, created_time DESC LIMIT %s OFFSET %s;", (page_size, offset))
            rows = cur.fetchall()
            items = [_row_to_dict(cur, r) for r in rows]
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size
            }


def get_user_by_id(user_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s AND del_flg = 0;", (user_id,))
            row = cur.fetchone()
            return _row_to_dict(cur, row)


def update_user(user_id: str, user_update: UserUpdate):
    """Cập nhật user. Chỉ cập nhật các field được gửi lên (khác None)."""
    updates = []
    params = []
    if user_update.name is not None:
        updates.append("name = %s")
        params.append(user_update.name)
    if user_update.email is not None:
        updates.append("email = %s")
        params.append(user_update.email)
    if user_update.phone is not None:
        updates.append("phone = %s")
        params.append(user_update.phone)
    if user_update.role is not None:
        updates.append("role = %s")
        params.append(user_update.role)
    if user_update.password is not None and user_update.password != "":
        updates.append("password = %s")
        params.append(get_password_hash(user_update.password))
    if not updates:
        return get_user_by_id(user_id)
    params.append(user_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE users
                SET updated_date = CURRENT_DATE, updated_time = CURRENT_TIME, {", ".join(updates)}
                WHERE user_id = %s AND del_flg = 0
                RETURNING *;
                """,
                params,
            )
            row = cur.fetchone()
            updated = _row_to_dict(cur, row)
        conn.commit()
        return updated


def delete_user(user_id: str):
    """Xóa user (soft delete: set del_flg = 1)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET del_flg = 1, updated_date = CURRENT_DATE, updated_time = CURRENT_TIME
                WHERE user_id = %s AND del_flg = 0
                RETURNING user_id;
                """,
                (user_id,),
            )
            row = cur.fetchone()
        conn.commit()
        return row is not None


def create_users_bulk(users: List[UserCreate]):
    if not users:
        return []

    results = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for user in users:
                password = get_password_hash(user.password)
                cur.execute("""
                    INSERT INTO users (name, email, phone, password, role)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *;
                """, (user.name, user.email, user.phone, password, user.role))
                row = cur.fetchone()
                results.append(_row_to_dict(cur, row))
        conn.commit()
    return results