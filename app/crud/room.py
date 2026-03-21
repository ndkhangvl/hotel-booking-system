from psycopg.rows import dict_row
from app.db.cockroach import get_connection
from datetime import date
import math


def _attach_amenities(conn, rooms: list[dict]) -> list[dict]:
    if not rooms:
        return []

    room_ids = [str(room["room_id"]) for room in rooms if room.get("room_id")]
    amenities_map = {}

    if room_ids:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT ra.room_id::text AS room_id, a.amenity_id, a.name, a.icon_url
                FROM room_amenities ra
                JOIN amenities a ON a.amenity_id = ra.amenity_id
                WHERE ra.room_id::text = ANY(%s)
                ORDER BY a.name;
                """,
                (room_ids,),
            )
            amenity_rows = cur.fetchall()

        for amenity in amenity_rows:
            amenities_map.setdefault(amenity["room_id"], []).append(
                {
                    "amenity_id": amenity["amenity_id"],
                    "name": amenity["name"],
                    "icon_url": amenity["icon_url"],
                }
            )

    for room in rooms:
        room["amenities"] = amenities_map.get(str(room.get("room_id")), [])

    return rooms


def upsert_room(data: dict) -> str:
    """
    Insert hoặc Update một phòng.
    - Nếu data["room_id"] là None => INSERT mới.
    - Nếu data["room_id"] có giá trị => UPDATE bảng ghi đó.
    Cập nhật cả bảng room_amenities.
    Trả về room_id dạng str.
    """
    room_id   = data.get("room_id")
    branch_code = str(data["branch_code"])
    room_type_id  = str(data["room_type_id"]) if data.get("room_type_id") else None
    price         = data.get("price")
    people_number = data.get("people_number") or 1
    del_flg       = int(data.get("del_flg", 0))
    amenity_ids   = [str(a) for a in (data.get("amenity_ids") or [])]
    today         = date.today()

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if room_id is None:
                cur.execute("""
                    INSERT INTO rooms
                        (branch_code, room_type_id, price, people_number,
                         created_date, del_flg)
                    VALUES (%s, %s, %s, %s, %s, 0)
                    RETURNING room_id;
                """, (branch_code, room_type_id, price, people_number, today))
                row = cur.fetchone()
                result_id = str(row["room_id"])
            else:
                result_id = str(room_id)
                cur.execute("""
                    UPDATE rooms
                    SET branch_code     = %s,
                        room_type_id  = %s,
                        price         = %s,
                        people_number = %s,
                        del_flg       = %s,
                        updated_date  = %s
                    WHERE room_id = %s;
                """, (branch_code, room_type_id, price, people_number, del_flg, today, result_id))

            cur.execute("DELETE FROM room_amenities WHERE room_id = %s;", (result_id,))
            if amenity_ids:
                cur.executemany(
                    "INSERT INTO room_amenities (room_id, amenity_id) VALUES (%s, %s);",
                    [(result_id, aid) for aid in amenity_ids],
                )

        conn.commit()

    return result_id


def get_initialize_stats(branch_code: str) -> dict:
    """Trả về thống kê branch rooms của một chi nhánh: tổng, còn trống, không còn trống."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                                              AS total_rooms,
                    SUM(CASE WHEN del_flg = 0 THEN 1 ELSE 0 END)         AS available_rooms,
                    SUM(CASE WHEN del_flg = 1 THEN 1 ELSE 0 END)         AS booked_rooms,
                    SUM(CASE WHEN del_flg = 2 THEN 1 ELSE 0 END)         AS in_use_rooms,
                    SUM(CASE WHEN del_flg = 3 THEN 1 ELSE 0 END)         AS unavailable_rooms
                FROM branch_rooms
                WHERE branch_code = %s;
            """, (branch_code,))
            stats = cur.fetchone()

    return {
        "total_rooms":       int(stats["total_rooms"] or 0),
        "available_rooms":   int(stats["available_rooms"] or 0),
        "booked_rooms":      int(stats["booked_rooms"] or 0),
        "in_use_rooms":      int(stats["in_use_rooms"] or 0),
        "unavailable_rooms": int(stats["unavailable_rooms"] or 0),
    }


def get_room_types() -> list:
    """Trả về danh sách tất cả loại phòng (del_flg = 0)."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT room_type_id, name, description
                FROM room_types
                WHERE del_flg = 0
                ORDER BY name;
            """)
            return cur.fetchall()


def get_amenities() -> list:
    """Trả về danh sách tất cả tiện ích (del_flg = 0)."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT amenity_id, name, icon_url
                FROM amenities
                WHERE del_flg = 0
                ORDER BY name;
            """)
            return cur.fetchall()


def get_rooms_by_branch(branch_code: str, page: int = 1, page_size: int = 10, active_only: bool = False) -> dict:
    """
    Lấy danh sách phòng của một chi nhánh có phân trang và kèm tiện ích.
    - active_only = True: Chỉ lấy phòng đang hoạt động (dành cho User).
    - active_only = False: Lấy tất cả các phòng (dành cho Admin).
    """
    offset = (page - 1) * page_size
    
    # Xây dựng điều kiện lọc động
    where_clause = "WHERE r.branch_code = %s"
    if active_only:
        where_clause += " AND r.del_flg = 0"

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            count_query = f"SELECT COUNT(*) AS total FROM rooms r {where_clause}"
            cur.execute(count_query, (branch_code,))
            total = int(cur.fetchone()["total"] or 0)

            select_query = f"""
                SELECT
                    r.room_id,
                    r.branch_code,
                    r.room_type_id,
                    rt.name AS room_type_name,
                    r.price,
                    r.people_number,
                    r.created_date,
                    r.del_flg,
                    COALESCE(br_stats.available_rooms, 0) AS available_rooms,
                    COALESCE(br_stats.booked_rooms, 0) AS booked_rooms,
                    COALESCE(br_stats.in_use_rooms, 0) AS in_use_rooms,
                    COALESCE(br_stats.unavailable_rooms, 0) AS unavailable_rooms
                FROM rooms r
                LEFT JOIN room_types rt ON rt.room_type_id = r.room_type_id
                LEFT JOIN (
                    SELECT
                        branch_code,
                        room_id,
                        SUM(CASE WHEN del_flg = 0 THEN 1 ELSE 0 END) AS available_rooms,
                        SUM(CASE WHEN del_flg = 1 THEN 1 ELSE 0 END) AS booked_rooms,
                        SUM(CASE WHEN del_flg = 2 THEN 1 ELSE 0 END) AS in_use_rooms,
                        SUM(CASE WHEN del_flg = 3 THEN 1 ELSE 0 END) AS unavailable_rooms
                    FROM branch_rooms
                    GROUP BY branch_code, room_id
                ) br_stats ON br_stats.branch_code = r.branch_code AND br_stats.room_id = r.room_id
                {where_clause}
                ORDER BY r.created_date, r.room_id
                LIMIT %s OFFSET %s;
            """
            cur.execute(select_query, (branch_code, page_size, offset))
            rows = cur.fetchall()

        rooms = [dict(r) for r in rows]

        rooms = _attach_amenities(conn, rooms)

    total_pages = max(1, math.ceil(total / page_size))

    return {
        "items":       rooms,
        "total":       total,
        "page":        page,
        "page_size":   page_size,
        "total_pages": total_pages,
    }


def get_branch_rooms_by_branch(branch_code: str, page: int = 1, page_size: int = 10) -> dict:
    offset = (page - 1) * page_size

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM branch_rooms br
                WHERE br.branch_code = %s;
                """,
                (branch_code,),
            )
            total = int(cur.fetchone()["total"] or 0)

            cur.execute(
                """
                SELECT
                    br.branch_room_id,
                    br.branch_code,
                    br.room_id,
                    br.room_number,
                    r.room_type_id,
                    rt.name AS room_type_name,
                    br.del_flg
                FROM branch_rooms br
                JOIN rooms r ON r.room_id = br.room_id
                LEFT JOIN room_types rt ON rt.room_type_id = r.room_type_id
                WHERE br.branch_code = %s
                ORDER BY br.room_number, br.branch_room_id
                LIMIT %s OFFSET %s;
                """,
                (branch_code, page_size, offset),
            )
            items = cur.fetchall()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


def upsert_branch_room(data: dict) -> str:
    branch_room_id = data.get("branch_room_id")
    branch_code = str(data["branch_code"])
    room_id = str(data["room_id"])
    room_number = str(data["room_number"]).strip()
    del_flg = int(data.get("del_flg", 0))
    today = date.today()

    if not room_number:
        raise ValueError("Số phòng không được để trống")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT room_id FROM rooms WHERE room_id = %s AND branch_code = %s;",
                (room_id, branch_code),
            )
            room = cur.fetchone()
            if not room:
                raise ValueError("Loại phòng không thuộc chi nhánh này")

            if branch_room_id is None:
                cur.execute(
                    """
                    INSERT INTO branch_rooms (
                        branch_code, room_id, room_number, created_date, del_flg
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING branch_room_id;
                    """,
                    (branch_code, room_id, room_number, today, del_flg),
                )
                row = cur.fetchone()
                result_id = str(row["branch_room_id"])
            else:
                result_id = str(branch_room_id)
                cur.execute(
                    """
                    UPDATE branch_rooms
                    SET room_id = %s,
                        room_number = %s,
                        del_flg = %s,
                        updated_date = %s
                    WHERE branch_room_id = %s AND branch_code = %s
                    RETURNING branch_room_id;
                    """,
                    (room_id, room_number, del_flg, today, result_id, branch_code),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Không tìm thấy phòng để cập nhật")

        conn.commit()

    return result_id


def delete_branch_room(branch_room_id: str, branch_code: str | None = None) -> bool:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if branch_code:
                cur.execute(
                    "DELETE FROM branch_rooms WHERE branch_room_id = %s AND branch_code = %s RETURNING branch_room_id;",
                    (branch_room_id, branch_code),
                )
            else:
                cur.execute(
                    "DELETE FROM branch_rooms WHERE branch_room_id = %s RETURNING branch_room_id;",
                    (branch_room_id,),
                )
            deleted = cur.fetchone()

        conn.commit()

    return deleted is not None


def get_user_rooms(limit: int = 4) -> list:
    """Trả về danh sách phòng hoạt động cho trang người dùng, giới hạn theo limit."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    r.room_id,
                    r.branch_code,
                    r.room_type_id,
                    rt.name AS room_type_name,
                    r.price,
                    r.people_number,
                    r.created_date,
                    r.del_flg
                FROM rooms r
                LEFT JOIN room_types rt ON rt.room_type_id = r.room_type_id
                WHERE r.del_flg = 0
                ORDER BY r.created_date DESC, r.room_id DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

        rooms = [dict(r) for r in rows]

        rooms = _attach_amenities(conn, rooms)

    return rooms

def get_room_detail(room_id: str, active_only: bool = False) -> dict:
    """
    Lấy thông tin chi tiết của 1 phòng bao gồm:
    - Thông tin cơ bản (số phòng, giá,...)
    - Tên loại phòng (JOIN room_types)
    - Danh sách tiện ích (JOIN amenities)
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            query = """
                SELECT 
                    r.room_id,
                    r.branch_code,
                    r.room_type_id, 
                    rt.name AS room_type_name, 
                    r.price, 
                    r.people_number, 
                    r.created_date,
                    r.del_flg
                FROM rooms r
                LEFT JOIN room_types rt ON r.room_type_id = rt.room_type_id
                WHERE r.room_id = %s
            """
            if active_only:
                query += " AND r.del_flg = 0"
            
            cur.execute(query, (room_id,))
            room = cur.fetchone()

            if not room:
                return None

            cur.execute("""
                SELECT 
                    a.amenity_id, 
                    a.name, 
                    a.icon_url
                FROM room_amenities ra
                JOIN amenities a ON a.amenity_id = ra.amenity_id
                WHERE ra.room_id = %s
                ORDER BY a.name;
            """, (room["room_id"],))
            
            room["amenities"] = cur.fetchall()

    return room