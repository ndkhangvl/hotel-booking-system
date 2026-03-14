from app.db.cockroach import get_connection
from psycopg.rows import dict_row
from uuid import UUID
import math

def get_rooms_by_branch(branch_id: UUID, page: int = 1, page_size: int = 10) -> dict:
    """
    Lấy danh sách phòng của một chi nhánh kèm tên loại phòng và phân trang.
    """
    offset = (page - 1) * page_size
    
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Đếm tổng số phòng của chi nhánh này
            cur.execute("""
                SELECT COUNT(*) AS total 
                FROM rooms 
                WHERE branch_id = %s AND del_flg = 0;
            """, (branch_id,))
            total = int(cur.fetchone()["total"] or 0)

            # 2. Lấy danh sách chi tiết phòng
            cur.execute("""
                SELECT 
                    r.room_id, 
                    r.room_number, 
                    r.price, 
                    r.people_number, 
                    rt.name AS room_type_name,
                    r.branch_id,
                    r.del_flg,
                    r.created_date
                FROM rooms r
                JOIN room_types rt ON r.room_type_id = rt.room_type_id
                WHERE r.branch_id = %s AND r.del_flg = 0
                ORDER BY r.room_number ASC
                LIMIT %s OFFSET %s;
            """, (branch_id, page_size, offset))
            items = cur.fetchall()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 1,
    }

def get_room_detail(room_id: UUID):
    """
    Lấy thông tin chi tiết của một phòng cụ thể.
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT r.*, rt.name AS room_type_name 
                FROM rooms r
                JOIN room_types rt ON r.room_type_id = rt.room_type_id
                WHERE r.room_id = %s AND r.del_flg = 0;
            """, (room_id,))
            return cur.fetchone()