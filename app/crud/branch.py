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

def get_branch_by_id(branch_id: UUID, active_only: bool = False):
    """
    Lấy thông tin chi nhánh kèm theo số lượng phòng (total_rooms).
    - active_only = True: Chỉ lấy chi nhánh del_flg=0 và CHỈ ĐẾM các phòng del_flg=0.
    - active_only = False: Lấy chi nhánh bất kể trạng thái và ĐẾM toàn bộ phòng thuộc về nó.
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Định nghĩa điều kiện lọc cho chi nhánh và phòng
            branch_filter = "AND b.del_flg = 0" if active_only else ""
            room_filter = "AND r.del_flg = 0" if active_only else ""

            # 2. Câu lệnh SQL sử dụng LEFT JOIN và COUNT
            query = f"""
                SELECT 
                    b.*, 
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON b.branch_id = r.branch_id {room_filter}
                WHERE b.branch_id = %s {branch_filter}
                GROUP BY b.branch_id;
            """
            
            cur.execute(query, (branch_id,))
            return cur.fetchone()
        
def get_branch_detail_with_rooms(branch_id: UUID, active_only: bool = False):
    """
    Lấy thông tin chi tiết 1 chi nhánh, 
    bao gồm danh sách toàn bộ phòng và tiện ích của từng phòng.
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Lấy thông tin Chi nhánh
            branch_query = "SELECT * FROM branches WHERE branch_id = %s"
            if active_only:
                branch_query += " AND del_flg = 0"
            
            cur.execute(branch_query, (branch_id,))
            branch = cur.fetchone()

            if not branch:
                return None

            # 2. Lấy danh sách các Phòng thuộc chi nhánh này
            room_query = """
                SELECT r.*, rt.name AS room_type_name
                FROM rooms r
                LEFT JOIN room_types rt ON r.room_type_id = rt.room_type_id
                WHERE r.branch_id = %s
            """
            if active_only:
                room_query += " AND r.del_flg = 0"
            
            room_query += " ORDER BY r.room_number ASC"
            cur.execute(room_query, (branch_id,))
            rooms = cur.fetchall()

            # Chuyển sang list để có thể gán thêm key 'amenities'
            branch["rooms"] = [dict(r) for r in rooms]
            branch["total_rooms"] = len(branch["rooms"])

            # 3. Đính kèm tiện ích (Amenities) cho từng phòng (nếu có phòng)
            if branch["rooms"]:
                room_ids = [str(r["room_id"]) for r in branch["rooms"]]
                cur.execute("""
                    SELECT ra.room_id::text, a.amenity_id, a.name, a.icon_url
                    FROM room_amenities ra
                    JOIN amenities a ON a.amenity_id = ra.amenity_id
                    WHERE ra.room_id::text = ANY(%s)
                """, (room_ids,))
                all_amenities = cur.fetchall()

                # Map tiện ích vào từng phòng tương ứng
                for room in branch["rooms"]:
                    room["amenities"] = [
                        {
                            "amenity_id": am["amenity_id"],
                            "name": am["name"],
                            "icon_url": am["icon_url"]
                        } 
                        for am in all_amenities if am["room_id"] == str(room["room_id"])
                    ]

    return branch
        
def update_branch(branch_id: UUID, branch_data: BranchUpdate):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Lấy dữ liệu cần update từ schema
            update_dict = branch_data.model_dump(exclude_unset=True)
            if "branch_id" in update_dict: 
                del update_dict["branch_id"]
            
            if not update_dict: 
                return None
            
            # 2. Xây dựng và thực thi lệnh UPDATE cho Chi nhánh
            query = f"UPDATE branches SET {', '.join([f'{k} = %s' for k in update_dict.keys()])}, " \
                    f"updated_date = CURRENT_DATE, updated_time = CURRENT_TIME " \
                    f"WHERE branch_id = %s RETURNING *;"
            
            params = list(update_dict.values()) + [branch_id]
            cur.execute(query, params)
            updated_branch = cur.fetchone()

            # 3. Logic Xóa mềm phòng quy ước del_flg = 3
            # Chỉ thực hiện nếu bản ghi trả về có del_flg = 1
            if updated_branch and updated_branch.get("del_flg") == 1:
                cur.execute("""
                    UPDATE rooms 
                    SET del_flg = 3, 
                        updated_date = CURRENT_DATE 
                    WHERE branch_id = %s;
                """, (branch_id,))
            
        # Commit cả 2 thao tác cùng lúc để đảm bảo tính toàn vẹn
        conn.commit()
        
    return updated_branch
        

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