from app.db.cockroach import get_connection
from app.schema.branch import BranchCreate, BranchUpdate
from uuid import UUID

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