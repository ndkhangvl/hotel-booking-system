from app.db.cockroach import get_connection
from app.schema.branch import BranchCreate, BranchUpdate
from uuid import UUID
from psycopg.rows import dict_row
import unicodedata
import re


def _remove_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt, trả về chuỗi ASCII."""
    # Xử lý riêng chữ đ/Đ (không có dạng decomposed chuẩn)
    text = text.replace('đ', 'd').replace('Đ', 'D')
    # NFD decompose: tách dấu ra khỏi ký tự → loại combining marks
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def generate_branch_code(name: str) -> str:
    """
    Sinh branch_code tự động từ tên chi nhánh.
    - Bỏ tiền tố "Aurora" (không phân biệt hoa thường).
    - Lấy chữ cái đầu tiên của mỗi từ còn lại, bỏ dấu, viết hoa.
    - Nếu trùng với branch_code đã có trong DB thì thêm số 2, 3, ...
    VD: "Aurora Hồ Đông" → "HD"; nếu đã có "HD" → "HD2".
    """
    # 1. Bỏ tiền tố Aurora (case-insensitive)
    cleaned = re.sub(r'^aurora\s*', '', name.strip(), flags=re.IGNORECASE)

    # 2. Lấy chữ đầu mỗi từ, bỏ dấu, viết hoa
    words = cleaned.split()
    if not words:
        # Trường hợp tên chỉ là "Aurora" – dùng AUR
        base_code = "AUR"
    else:
        initials = "".join(w[0] for w in words if w)
        base_code = _remove_accents(initials).upper()
        # Loại bỏ ký tự không phải chữ cái
        base_code = re.sub(r'[^A-Z]', '', base_code) or "BR"

    # 3. Kiểm tra trùng trong DB, thêm số nếu cần
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT branch_code FROM branches WHERE branch_code LIKE %s;",
                (base_code + '%',)
            )
            existing = {row[0] for row in cur.fetchall()}

    if base_code not in existing:
        return base_code

    counter = 2
    while f"{base_code}{counter}" in existing:
        counter += 1
    return f"{base_code}{counter}"

def create_branch(branch):
    with get_connection() as conn:
        # THÊM row_factory=dict_row để trả về Dict ngay lập tức
        with conn.cursor(row_factory=dict_row) as cur:
            data = branch.model_dump() if hasattr(branch, 'model_dump') else branch.__dict__

            # Tự động sinh branch_code từ tên chi nhánh
            branch_code = generate_branch_code(data.get('name', ''))

            cur.execute("""
                INSERT INTO branches (branch_code, name, address, phone, created_user)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
            """, (branch_code, data.get('name'), data.get('address'), data.get('phone'), data.get('created_user')))
            return cur.fetchone()

def get_branch_by_id(branch_code: UUID, active_only: bool = False):
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
                LEFT JOIN rooms r ON b.branch_code = r.branch_code {room_filter}
                WHERE b.branch_code = %s {branch_filter}
                GROUP BY b.branch_code;
            """
            
            cur.execute(query, (branch_code,))
            return cur.fetchone()
        
def update_branch(branch_code: UUID, branch_data: BranchUpdate):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Lấy dữ liệu cần update từ schema
            update_dict = branch_data.model_dump(exclude_unset=True)
            if "branch_code" in update_dict: 
                del update_dict["branch_code"]
            
            if not update_dict: 
                return None
            
            # 2. Xây dựng và thực thi lệnh UPDATE cho Chi nhánh
            query = f"UPDATE branches SET {', '.join([f'{k} = %s' for k in update_dict.keys()])}, " \
                    f"updated_date = CURRENT_DATE, updated_time = CURRENT_TIME " \
                    f"WHERE branch_code = %s RETURNING *;"
            
            params = list(update_dict.values()) + [branch_code]
            cur.execute(query, params)
            updated_branch = cur.fetchone()

            # 3. Logic Xóa mềm phòng quy ước del_flg = 3
            # Chỉ thực hiện nếu bản ghi trả về có del_flg = 1
            if updated_branch and updated_branch.get("del_flg") == 1:
                cur.execute("""
                    UPDATE rooms 
                    SET del_flg = 3, 
                        updated_date = CURRENT_DATE 
                    WHERE branch_code = %s;
                """, (branch_code,))
            
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
                JOIN branches b ON r.branch_code = b.branch_code
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
                    b.branch_code, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON r.branch_code = b.branch_code AND r.del_flg = 0
                GROUP BY 
                    b.branch_code, b.name, b.address, b.phone, 
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
                    b.branch_code, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON r.branch_code = b.branch_code AND r.del_flg = 0
                WHERE b.del_flg = 0 -- SỬA Ở ĐÂY: Thêm b. vào trước del_flg
                GROUP BY 
                    b.branch_code, b.name, b.address, b.phone, 
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
                    b.branch_code, b.name, b.address, b.phone, 
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON r.branch_code = b.branch_code AND r.del_flg = 0
                WHERE b.del_flg = 0 
                AND (b.name ILIKE %s OR b.address ILIKE %s)
                GROUP BY 
                    b.branch_code, b.name, b.address, b.phone, 
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


def get_active_branch_detail(branch_code: str) -> dict | None:
    """Trả về chi tiết 1 chi nhánh hoạt động, kèm danh sách rooms theo branch_code."""
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    b.branch_code, b.name, b.address, b.phone,
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg,
                    COUNT(r.room_id) AS total_rooms
                FROM branches b
                LEFT JOIN rooms r ON r.branch_code = b.branch_code AND r.del_flg = 0
                WHERE b.branch_code = %s AND b.del_flg = 0
                GROUP BY
                    b.branch_code, b.name, b.address, b.phone,
                    b.created_date, b.created_time, b.created_user,
                    b.updated_date, b.updated_time, b.updated_user,
                    b.del_flg;
                """,
                (branch_code,),
            )
            branch = cur.fetchone()

            if not branch:
                return None

            cur.execute(
                """
                SELECT
                    r.room_id,
                    r.branch_code,
                    r.room_type_id,
                    rt.name AS room_type_name,
                    rt.description,
                    r.price,
                    r.people_number,
                    r.del_flg
                FROM rooms r
                LEFT JOIN room_types rt ON rt.room_type_id = r.room_type_id
                WHERE r.branch_code = %s
                  AND r.del_flg = 0
                  AND rt.del_flg = 0
                ORDER BY rt.name, r.created_date, r.room_id;
                """,
                (branch_code,),
            )
            rooms = cur.fetchall()

            room_ids = [str(room["room_id"]) for room in rooms]
            amenities_map = {}

            if room_ids:
                cur.execute(
                    """
                    SELECT
                        ra.room_id::text AS room_id,
                        a.name,
                        a.icon_url
                    FROM room_amenities ra
                    JOIN amenities a ON a.amenity_id = ra.amenity_id
                    WHERE ra.room_id::text = ANY(%s)
                      AND a.del_flg = 0
                    ORDER BY a.name;
                    """,
                    (room_ids,),
                )
                amenity_rows = cur.fetchall()

                for amenity in amenity_rows:
                    amenities_map.setdefault(amenity["room_id"], []).append(
                        {
                            "name": amenity["name"],
                            "icon_url": amenity["icon_url"],
                        }
                    )

    result = dict(branch)
    result["rooms"] = [
        {
            **dict(room),
            "room_amenities": amenities_map.get(str(room["room_id"]), []),
        }
        for room in rooms
    ]
    return result