from app.db.cockroach import get_connection
from app.schema.branch import BranchCreate, BranchUpdate
from uuid import UUID
from psycopg.rows import dict_row

def create_branch(branch):
    with get_connection() as conn:
        # THÊM row_factory=dict_row để trả về Dict ngay lập tức
        with conn.cursor(row_factory=dict_row) as cur:
            data = branch.model_dump() if hasattr(branch, 'model_dump') else branch.__dict__
            cur.execute("""
                INSERT INTO branches (name, address, phone, created_user)
                VALUES (%s, %s, %s, %s)
                RETURNING *;
            """, (data.get('name'), data.get('address'), data.get('phone'), data.get('created_user')))
            return cur.fetchone()

def get_branch_by_id(branch_id: UUID):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur: # THÊM row_factory
            cur.execute("SELECT * FROM branches WHERE branch_id = %s AND del_flg = 0;", (branch_id,))
            return cur.fetchone()

def update_branch(branch_id: UUID, branch_data: BranchUpdate):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur: # THÊM row_factory
            update_dict = branch_data.model_dump(exclude_unset=True)
            if "branch_id" in update_dict: del update_dict["branch_id"]
            if not update_dict: return None
            
            query = f"UPDATE branches SET {', '.join([f'{k} = %s' for k in update_dict.keys()])}, " \
                    f"updated_date = CURRENT_DATE, updated_time = CURRENT_TIME WHERE branch_id = %s RETURNING *;"
            
            params = list(update_dict.values()) + [branch_id]
            cur.execute(query, params)
            return cur.fetchone()

def delete_branch(branch_id: UUID, user_id: UUID):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur: # THÊM row_factory
            cur.execute("""
                UPDATE branches SET del_flg = 1, updated_user = %s, 
                updated_date = CURRENT_DATE, updated_time = CURRENT_TIME
                WHERE branch_id = %s RETURNING *;
            """, (user_id, branch_id))
            return cur.fetchone()

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
    offset = (page - 1) * page_size

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Đếm tổng số bản ghi
            cur.execute("SELECT COUNT(*) AS total FROM branches;")
            total = int(cur.fetchone()["total"] or 0)

            # 2. Lấy danh sách (Bổ sung đủ các cột để map vào BranchResponse)
            cur.execute("""
                SELECT 
                    b.branch_id, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON r.branch_id = b.branch_id AND r.del_flg = 0
                GROUP BY 
                    b.branch_id, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg
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

#def get_all_active_branches():
#    with get_connection() as conn:
#        with conn.cursor() as cur:
#            cur.execute("SELECT * FROM branches WHERE del_flg = 0 ORDER BY created_date DESC;")
#            
#            columns = [desc[0] for desc in cur.description]
#           
#            rows = cur.fetchall()
#            
#            result = [dict(zip(columns, row)) for row in rows]
#            
#            return result
def get_all_active_branches(page: int = 1, page_size: int = 10) -> dict:
    offset = (page - 1) * page_size
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Đếm tổng (Cần thêm b. vào WHERE)
            cur.execute("SELECT COUNT(*) AS total FROM branches b WHERE b.del_flg = 0;")
            total = int(cur.fetchone()["total"] or 0)
            
            # 2. Lấy danh sách
            cur.execute("""
                SELECT 
                    b.branch_id, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON r.branch_id = b.branch_id AND r.del_flg = 0
                WHERE b.del_flg = 0 -- SỬA Ở ĐÂY: Thêm b. vào trước del_flg
                GROUP BY 
                    b.branch_id, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg
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

import math

def search_branches(keyword: str, page: int = 1, page_size: int = 10) -> dict:
    offset = (page - 1) * page_size
    search_term = f"%{keyword}%"

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Đếm tổng số bản ghi (Sửa tham số: truyền đúng 2 cái cho 2 dấu %s)
            count_query = """
                SELECT COUNT(*) AS total 
                FROM branches b 
                WHERE b.del_flg = 0 
                AND (b.name ILIKE %s OR b.address ILIKE %s);
            """
            cur.execute(count_query, (search_term, search_term))
            total = int(cur.fetchone()["total"] or 0)

            # 2. Lấy danh sách kết quả
            # Lưu ý: %s xuất hiện 2 lần cho tìm kiếm, sau đó là LIMIT và OFFSET
            items_query = """
                SELECT 
                    b.branch_id, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON r.branch_id = b.branch_id AND r.del_flg = 0
                WHERE b.del_flg = 0 
                AND (b.name ILIKE %s OR b.address ILIKE %s)
                GROUP BY 
                    b.branch_id, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg
                ORDER BY b.name
                LIMIT %s OFFSET %s;
            """
            cur.execute(items_query, (search_term, search_term, page_size, offset))
            items = cur.fetchall()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 1,
    }


def get_active_branch_detail(branch_id: str) -> dict | None:
    """Trả về chi tiết 1 chi nhánh hoạt động, kèm danh sách loại phòng và giá từ bảng rooms."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    b.branch_id, b.name, b.address, b.phone,
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON r.branch_id = b.branch_id AND r.del_flg = 0
                WHERE b.branch_id = %s AND b.del_flg = 0
                GROUP BY
                    b.branch_id, b.name, b.address, b.phone,
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg;
                """,
                (branch_id,),
            )
            branch = cur.fetchone()

            if not branch:
                return None

            cur.execute(
                """
                SELECT
                    rt.room_type_id,
                    rt.name,
                    rt.description,
                    MIN(r.price) AS price
                FROM rooms r
                JOIN room_types rt ON rt.room_type_id = r.room_type_id
                WHERE r.branch_id = %s
                  AND r.del_flg = 0
                  AND rt.del_flg = 0
                GROUP BY rt.room_type_id, rt.name, rt.description
                ORDER BY rt.name;
                """,
                (branch_id,),
            )
            room_types = cur.fetchall()

    result = dict(branch)
    result["room_types"] = [dict(rt) for rt in room_types]
    return result