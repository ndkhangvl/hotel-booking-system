from psycopg.rows import dict_row
from app.db.cockroach import get_connection


def get_initialize_stats() -> dict:
    """Trả về tổng chi nhánh, số chi nhánh hoạt động, tổng số phòng (join branches + rooms)."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                                              AS total_branches,
                    SUM(CASE WHEN del_flg = 0 THEN 1 ELSE 0 END)         AS active_branches
                FROM branches;
            """)
            branch_stats = cur.fetchone()

            cur.execute("""
                SELECT COUNT(r.room_id) AS total_rooms
                FROM rooms r
                JOIN branches b ON r.branch_id = b.branch_id
                WHERE r.del_flg = 0 AND b.del_flg = 0;
            """)
            room_stats = cur.fetchone()

    return {
        "total_branches": int(branch_stats["total_branches"] or 0),
        "active_branches": int(branch_stats["active_branches"] or 0),
        "total_rooms": int(room_stats["total_rooms"] or 0),
    }


def get_branches_list(page: int = 1, page_size: int = 10) -> dict:
    """Trả về danh sách chi nhánh có phân trang, kèm tổng số phòng của mỗi chi nhánh."""
    offset = (page - 1) * page_size

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Đếm tổng để tính phân trang
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM branches
                WHERE del_flg = 0;
            """)
            total = int(cur.fetchone()["total"] or 0)

            # Lấy danh sách chi nhánh kèm tổng phòng
            cur.execute("""
                SELECT
                    b.branch_id,
                    b.name,
                    b.address,
                    b.phone,
                    b.created_date,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r
                    ON r.branch_id = b.branch_id AND r.del_flg = 0
                WHERE b.del_flg = 0
                GROUP BY b.branch_id, b.name, b.address, b.phone, b.created_date, b.del_flg
                ORDER BY b.name
                LIMIT %s OFFSET %s;
            """, (page_size, offset))
            items = cur.fetchall()

    import math
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 1,
    }
