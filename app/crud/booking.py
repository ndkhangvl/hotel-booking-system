from app.db.cockroach import get_connection
from app.schema.booking import BookingCreate, BookingAdminUpdate
from datetime import date, datetime
from enum import Enum 
from psycopg.rows import dict_row


def create_booking(booking: BookingCreate, total_price: float = 0.0, current_user_id: str = None):
    nights = (booking.to_date - booking.from_date).days
    if nights <= 0:
        raise ValueError("Ngày trả phòng phải sau ngày nhận phòng")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT price
                FROM rooms
                WHERE room_id = %s AND del_flg = 0;
                """,
                (str(booking.room_id),),
            )
            room = cur.fetchone()
            if not room:
                raise ValueError("Không tìm thấy phòng để đặt")

            total_price = float(room["price"] or 0) * nights
            now = datetime.now()
            cur.execute("""
                INSERT INTO bookings (
                    user_id, room_id, voucher_code, from_date, to_date, 
                    total_price, status, created_date, created_time, created_user, del_flg
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s, %s, %s, 0)
                RETURNING *;
            """, (
                str(booking.user_id),
                str(booking.room_id),
                booking.voucher_code,
                booking.from_date,
                booking.to_date,
                total_price,
                now.date(),
                now.time(),
                current_user_id if current_user_id else str(booking.user_id)
            ))

            new_booking = cur.fetchone()

        conn.commit()

    return new_booking

def get_all_bookings():
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM bookings WHERE del_flg = 0 ORDER BY created_date DESC, created_time DESC;")
            rows = cur.fetchall()
            
            if not rows:
                return []

            return rows

def update_booking_by_admin(booking_id: str, booking_update: BookingAdminUpdate, admin_id: str = None):
    update_data = booking_update.model_dump(exclude_unset=True)
    
    # Nếu không có dữ liệu cập nhật, trả về None hoặc xử lý lỗi ở tầng API
    if not update_data:
        return None

    set_clauses = []
    values = []
    
    for key, value in update_data.items():
        set_clauses.append(f"{key} = %s")
        if isinstance(value, Enum):
            values.append(value.value)
        elif hasattr(value, 'hex'):
            values.append(str(value))
        else:
            values.append(value)

    now = datetime.now()
    set_clauses.append("updated_date = %s")
    values.append(now.date())
    set_clauses.append("updated_time = %s")
    values.append(now.time())
    
    if admin_id:
        set_clauses.append("updated_user = %s")
        values.append(str(admin_id))

    set_query = ", ".join(set_clauses)
    values.append(booking_id)

    query = f"UPDATE bookings SET {set_query} WHERE booking_id = %s AND del_flg = 0 RETURNING *;"

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, tuple(values))
            updated_booking = cur.fetchone()
                
        conn.commit()
        return updated_booking

def delete_booking(booking_id: str, admin_id: str = None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            now = datetime.now()
            cur.execute("""
                UPDATE bookings 
                SET del_flg = 1, updated_date = %s, updated_time = %s, updated_user = %s
                WHERE booking_id = %s
                RETURNING *;
            """, (now.date(), now.time(), str(admin_id) if admin_id else None, booking_id))
            deleted_booking = cur.fetchone()
                
        conn.commit()
        return deleted_booking

def confirm_booking(booking_id: str, receptionist_id: str = None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            now = datetime.now()
            cur.execute("""
                UPDATE bookings 
                SET status = 'Confirmed', updated_date = %s, updated_time = %s, updated_user = %s
                WHERE booking_id = %s AND status = 'Pending' AND del_flg = 0
                RETURNING *;
            """, (now.date(), now.time(), str(receptionist_id) if receptionist_id else None, booking_id))
            updated_booking = cur.fetchone()
                
        conn.commit()
        return updated_booking

def cancel_booking(booking_id: str, receptionist_id: str = None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            now = datetime.now()
            cur.execute("""
                UPDATE bookings 
                SET status = 'Cancelled', updated_date = %s, updated_time = %s, updated_user = %s
                WHERE booking_id = %s AND status IN ('Pending', 'Confirmed') AND del_flg = 0
                RETURNING *;
            """, (now.date(), now.time(), str(receptionist_id) if receptionist_id else None, booking_id))
            updated_booking = cur.fetchone()
                
        conn.commit()
        return updated_booking
    
def process_check_in(booking_id: str, receptionist_id: str = None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            now = datetime.now()
            cur.execute("""
                UPDATE bookings 
                SET status = 'Checked-in', updated_date = %s, updated_time = %s, updated_user = %s
                WHERE booking_id = %s AND status = 'Confirmed' AND del_flg = 0
                RETURNING *;
            """, (now.date(), now.time(), str(receptionist_id) if receptionist_id else None, booking_id))
            updated_booking = cur.fetchone()
                
        conn.commit()
        return updated_booking

def process_check_out(booking_id: str, receptionist_id: str = None):
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            now = datetime.now()
            cur.execute("""
                UPDATE bookings 
                SET status = 'Completed', updated_date = %s, updated_time = %s, updated_user = %s
                WHERE booking_id = %s AND status = 'Checked-in' AND del_flg = 0
                RETURNING *;
            """, (now.date(), now.time(), str(receptionist_id) if receptionist_id else None, booking_id))
            updated_booking = cur.fetchone()
        conn.commit()
        return updated_booking