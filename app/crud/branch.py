from app.db.cockroach import get_connection
from app.schema.branch import BranchCreate, BranchUpdate
from uuid import UUID
from psycopg.rows import dict_row

def create_branch(branch: BranchCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO branches (name, address, phone, created_user)
                VALUES (%s, %s, %s, %s)
                RETURNING *;
            """, (branch.name, branch.address, branch.phone, branch.created_user))
            new_branch = cur.fetchone()
        conn.commit()
        return new_branch

def get_all_branches():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM branches WHERE del_flg = 0 ORDER BY created_date DESC;")
            
            columns = [desc[0] for desc in cur.description]
            
            rows = cur.fetchall()
            
            result = [dict(zip(columns, row)) for row in rows]
            
            return result

def get_branch_by_id(branch_id: UUID):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM branches WHERE branch_id = %s AND del_flg = 0;", (branch_id,))
            return cur.fetchone()

def update_branch(branch_id: UUID, branch_data: BranchUpdate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Lấy các trường cần update (loại bỏ các trường None)
            update_data = branch_data.model_dump(exclude_unset=True)
            if not update_data:
                return None
            
            # Xây dựng câu lệnh SQL động
            query = "UPDATE branches SET "
            query += ", ".join([f"{key} = %s" for key in update_data.keys()])
            query += ", updated_date = CURRENT_DATE, updated_time = CURRENT_TIME"
            query += " WHERE branch_id = %s RETURNING *;"
            
            params = list(update_data.values())
            params.append(branch_id)
            
            cur.execute(query, tuple(params))
            updated_branch = cur.fetchone()
        conn.commit()
        return updated_branch

def delete_branch(branch_id: UUID, user_id: UUID):
    """Thực hiện Soft Delete bằng cách chuyển del_flg = 1"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE branches 
                SET del_flg = 1, updated_user = %s, updated_date = CURRENT_DATE, updated_time = CURRENT_TIME
                WHERE branch_id = %s 
                RETURNING *;
            """, (user_id, branch_id))
            deleted_branch = cur.fetchone()
        conn.commit()
        return deleted_branch

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
            cur.execute("SELECT COUNT(*) AS total FROM branches WHERE del_flg = 0;")
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
                WHERE b.del_flg = 0
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