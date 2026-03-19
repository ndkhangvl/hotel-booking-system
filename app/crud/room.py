from psycopg.rows import dict_row
from app.db.cockroach import get_connection
from datetime import date
import math


def upsert_room(data: dict) -> str:
    """
    Insert hoặc Update một phòng.
    - Nếu data["room_id"] là None => INSERT mới.
    - Nếu data["room_id"] có giá trị => UPDATE bảng ghi đó.
    Cập nhật cả bảng room_amenities.
    Trả về room_id dạng str.
    """
    room_id   = data.get("room_id")
    branch_id = str(data["branch_id"])
    room_type_id  = str(data["room_type_id"]) if data.get("room_type_id") else None
    room_number   = data["room_number"]
    price         = data.get("price")
    people_number = data.get("people_number") or 1
    del_flg       = int(data.get("del_flg", 0))
    amenity_ids   = [str(a) for a in (data.get("amenity_ids") or [])]
    today         = date.today()

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if room_id is None:
                # INSERT
                cur.execute("""
                    INSERT INTO rooms
                        (branch_id, room_type_id, room_number, price, people_number,
                         created_date, del_flg)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING room_id;
                """, (branch_id, room_type_id, room_number, price, people_number, today, del_flg))
                row = cur.fetchone()
                result_id = str(row["room_id"])
            else:
                result_id = str(room_id)
                # UPDATE
                cur.execute("""
                    UPDATE rooms
                    SET room_type_id  = %s,
                        room_number   = %s,
                        price         = %s,
                        people_number = %s,
                        del_flg       = %s,
                        updated_date  = %s
                    WHERE room_id = %s;
                """, (room_type_id, room_number, price, people_number, del_flg, today, result_id))

            # Sync amenities: xóa hết rồi insert lại
            cur.execute("DELETE FROM room_amenities WHERE room_id = %s;", (result_id,))
            if amenity_ids:
                cur.executemany(
                    "INSERT INTO room_amenities (room_id, amenity_id) VALUES (%s, %s);",
                    [(result_id, aid) for aid in amenity_ids],
                )

        conn.commit()

    return result_id


def get_initialize_stats(branch_id: str) -> dict:
    """Trả về thống kê phòng của một chi nhánh: tổng, đang hoạt động, đã xóa."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                                              AS total_rooms,
                    SUM(CASE WHEN del_flg = 0 THEN 1 ELSE 0 END)         AS available_rooms,
                    SUM(CASE WHEN del_flg != 0 THEN 1 ELSE 0 END)        AS occupied_rooms
                FROM rooms
                WHERE branch_id = %s;
            """, (branch_id,))
            stats = cur.fetchone()

    return {
        "total_rooms":     int(stats["total_rooms"]     or 0),
        "available_rooms": int(stats["available_rooms"] or 0),
        "occupied_rooms":  int(stats["occupied_rooms"]  or 0),
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


def get_rooms_by_branch(branch_id: str, page: int = 1, page_size: int = 10, active_only: bool = False) -> dict:
    """
    Lấy danh sách phòng của một chi nhánh có phân trang và kèm tiện ích.
    - active_only = True: Chỉ lấy phòng đang hoạt động (dành cho User).
    - active_only = False: Lấy tất cả các phòng (dành cho Admin).
    """
    offset = (page - 1) * page_size
    
    # Xây dựng điều kiện lọc động
    where_clause = "WHERE r.branch_id = %s"
    if active_only:
        where_clause += " AND r.del_flg = 0"

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Đếm tổng số bản ghi (Cần áp dụng cùng điều kiện lọc)
            count_query = f"SELECT COUNT(*) AS total FROM rooms r {where_clause}"
            cur.execute(count_query, (branch_id,))
            total = int(cur.fetchone()["total"] or 0)

            # 2. Lấy danh sách phòng
            select_query = f"""
                SELECT
                    r.room_id,
                    r.branch_id,
                    r.room_type_id,
                    rt.name AS room_type_name,
                    r.room_number,
                    r.price,
                    r.people_number,
                    r.created_date,
                    r.del_flg
                FROM rooms r
                LEFT JOIN room_types rt ON rt.room_type_id = r.room_type_id
                {where_clause}
                ORDER BY r.room_number
                LIMIT %s OFFSET %s;
            """
            cur.execute(select_query, (branch_id, page_size, offset))
            rows = cur.fetchall()

        # Chuyển thành list dict để có thể chỉnh sửa (thêm key amenities)
        rooms = [dict(r) for r in rows]

        # 3. Đính kèm tiện ích (Amenities) cho các phòng trong trang hiện tại
        if rooms:
            room_ids_str = [str(r["room_id"]) for r in rooms]
            with conn.cursor(row_factory=dict_row) as cur2:
                cur2.execute("""
                    SELECT ra.room_id::text AS room_id, a.amenity_id, a.name, a.icon_url
                    FROM room_amenities ra
                    JOIN amenities a ON a.amenity_id = ra.amenity_id
                    WHERE ra.room_id::text = ANY(%s)
                    ORDER BY a.name;
                """, (room_ids_str,))
                amenity_rows = cur2.fetchall()

            # Tạo bản đồ tiện ích theo room_id để map nhanh hơn
            amenities_map = {}
            for ar in amenity_rows:
                rid = ar["room_id"]
                if rid not in amenities_map:
                    amenities_map[rid] = []
                amenities_map[rid].append({
                    "amenity_id": ar["amenity_id"],
                    "name":       ar["name"],
                    "icon_url":   ar["icon_url"],
                })

            # Gán tiện ích vào từng phòng
            for room in rooms:
                room["amenities"] = amenities_map.get(str(room["room_id"]), [])
        else:
            rooms = []

    total_pages = max(1, math.ceil(total / page_size))

    return {
        "items":       rooms,
        "total":       total,
        "page":        page,
        "page_size":   page_size,
        "total_pages": total_pages,
    }


def get_user_rooms(limit: int = 4) -> list:
    """Trả về danh sách phòng hoạt động cho trang người dùng, giới hạn theo limit."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    r.room_id,
                    r.branch_id,
                    r.room_type_id,
                    rt.name AS room_type_name,
                    r.room_number,
                    r.price,
                    r.people_number,
                    r.created_date,
                    r.del_flg
                FROM rooms r
                LEFT JOIN room_types rt ON rt.room_type_id = r.room_type_id
                WHERE r.del_flg = 0
                ORDER BY r.created_date DESC, r.room_number
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

        rooms = [dict(r) for r in rows]

        if rooms:
            room_ids_str = [str(r["room_id"]) for r in rooms]
            with conn.cursor(row_factory=dict_row) as cur2:
                cur2.execute(
                    """
                    SELECT ra.room_id::text AS room_id, a.amenity_id, a.name, a.icon_url
                    FROM room_amenities ra
                    JOIN amenities a ON a.amenity_id = ra.amenity_id
                    WHERE ra.room_id::text = ANY(%s)
                    ORDER BY a.name;
                    """,
                    (room_ids_str,),
                )
                amenity_rows = cur2.fetchall()

            amenities_map = {}
            for ar in amenity_rows:
                rid = ar["room_id"]
                if rid not in amenities_map:
                    amenities_map[rid] = []
                amenities_map[rid].append(
                    {
                        "amenity_id": ar["amenity_id"],
                        "name": ar["name"],
                        "icon_url": ar["icon_url"],
                    }
                )

            for room in rooms:
                room["amenities"] = amenities_map.get(str(room["room_id"]), [])
        else:
            rooms = []

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
            # 1. Lấy thông tin cơ bản của phòng và loại phòng
            query = """
                SELECT 
                    r.room_id, 
                    r.branch_id, 
                    r.room_type_id, 
                    rt.name AS room_type_name, 
                    r.room_number, 
                    r.price, 
                    r.people_number, 
                    r.created_date, 
                    r.del_flg
                FROM rooms r
                LEFT JOIN room_types rt ON r.room_type_id = rt.room_type_id
                WHERE r.room_id = %s
            """
            # Nếu là User gọi, chỉ lấy phòng chưa bị xóa
            if active_only:
                query += " AND r.del_flg = 0"
            
            cur.execute(query, (room_id,))
            room = cur.fetchone()

            if not room:
                return None

            # 2. Lấy danh sách tiện ích của phòng này
            cur.execute("""
                SELECT 
                    a.amenity_id, 
                    a.name, 
                    a.icon_url
                FROM room_amenities ra
                JOIN amenities a ON a.amenity_id = ra.amenity_id
                WHERE ra.room_id = %s
                ORDER BY a.name;
            """, (room_id,))
            
            # Gán danh sách tiện ích vào object room
            room["amenities"] = cur.fetchall()

    return room