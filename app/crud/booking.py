from app.db.cockroach import get_connection
from app.schema.booking import BookingAdminCreate, BookingAdminUpdate, BookingCreate, BookingStatus, PaymentStatus
from datetime import datetime
from enum import Enum 
from psycopg.rows import dict_row


def _generate_booking_code(branch_code: str, now: datetime) -> str:
    branch_suffix = str(branch_code).replace("-", "")[-4:].upper()
    timestamp = now.strftime("%Y%m%d%H%M%S") + f"{int(now.microsecond / 1000):03d}"
    return f"{branch_suffix}-{timestamp}"


def _normalize_booking_status(value: str | Enum | None) -> str:
    raw_value = value.value if isinstance(value, Enum) else value
    normalized = (raw_value or "").strip().lower()
    mapping = {
        "pending": BookingStatus.PENDING.value,
        "confirmed": BookingStatus.CONFIRMED.value,
        "checked-in": BookingStatus.CHECKED_IN.value,
        "checkedin": BookingStatus.CHECKED_IN.value,
        "checked-out": BookingStatus.COMPLETED.value,
        "checkedout": BookingStatus.COMPLETED.value,
        "completed": BookingStatus.COMPLETED.value,
        "cancelled": BookingStatus.CANCELLED.value,
        "canceled": BookingStatus.CANCELLED.value,
    }

    if normalized not in mapping:
        raise ValueError("Trạng thái booking không hợp lệ")

    return mapping[normalized]


def _normalize_payment_status(value: str | Enum | None) -> str | None:
    if value is None:
        return None

    raw_value = value.value if isinstance(value, Enum) else value
    normalized = (raw_value or "").strip().lower()

    if normalized in {"unpaid", "pending"}:
        return PaymentStatus.UNPAID.value
    if normalized in {"paid", "completed"}:
        return PaymentStatus.PAID.value

    raise ValueError("Trạng thái thanh toán không hợp lệ")


def _get_latest_payment_status(cur, booking_id: str) -> str:
    cur.execute(
        """
        SELECT
            CASE
                WHEN LOWER(status) IN ('completed', 'paid') THEN 'paid'
                WHEN LOWER(status) = 'refunded' THEN 'paid'
                ELSE 'unpaid'
            END AS payment_status
        FROM payments
        WHERE booking_id = %s
          AND del_flg = 0
        ORDER BY created_date DESC, created_time DESC, payment_id DESC
        LIMIT 1;
        """,
        (booking_id,),
    )
    payment = cur.fetchone()
    return payment["payment_status"] if payment else PaymentStatus.UNPAID.value


def _create_completed_payment(cur, branch_code: str, booking_id: str, amount: float, actor_id: str | None) -> None:
    now = datetime.now()
    cur.execute(
        """
        INSERT INTO payments (
            branch_code,
            booking_id,
            amount,
            status,
            created_date,
            created_time,
            created_user,
            del_flg
        )
        VALUES (%s, %s, %s, 'Completed', %s, %s, %s, 0);
        """,
        (branch_code, booking_id, amount, now.date(), now.time(), actor_id),
    )


def _sync_paid_payment(cur, branch_code: str, booking_id: str, total_price: float, requested_payment_status: str | None, actor_id: str | None) -> str:
    current_payment_status = _get_latest_payment_status(cur, booking_id)
    if requested_payment_status is None:
        return current_payment_status

    if current_payment_status == PaymentStatus.PAID.value and requested_payment_status != PaymentStatus.PAID.value:
        raise ValueError("Không thể chuyển trạng thái thanh toán từ đã thanh toán về chưa thanh toán")

    if requested_payment_status == PaymentStatus.PAID.value and current_payment_status != PaymentStatus.PAID.value:
        _create_completed_payment(cur, branch_code, booking_id, total_price, actor_id)
        return PaymentStatus.PAID.value

    return current_payment_status


def _resolve_booking_room(cur, branch_code: str | None, room_id: str | None, branch_room_id: str | None) -> tuple[str, str, str, float]:
    if branch_room_id:
        cur.execute(
            """
            SELECT
                br.room_id::text AS room_id,
                br.branch_room_id::text AS branch_room_id,
                br.branch_code::text AS branch_code,
                r.price
            FROM branch_rooms br
            JOIN rooms r ON r.room_id = br.room_id
            WHERE br.branch_room_id = %s
              AND br.del_flg = 0
              AND r.del_flg = 0;
            """,
            (branch_room_id,),
        )
        room = cur.fetchone()
        if not room:
            raise ValueError("Không tìm thấy phòng chi nhánh để đặt")

        return room["room_id"], room["branch_room_id"], room["branch_code"], float(room["price"] or 0)

    if room_id:
        cur.execute(
            """
            SELECT room_id::text AS room_id, branch_code::text AS branch_code, price
            FROM rooms
            WHERE room_id = %s AND del_flg = 0;
            """,
            (room_id,),
        )
        room = cur.fetchone()
        if not room:
            raise ValueError("Không tìm thấy phòng để đặt")

        resolved_branch_code = branch_code or room["branch_code"]

        cur.execute(
            """
            SELECT
                br.branch_room_id::text AS branch_room_id,
                br.room_id::text AS room_id,
                br.branch_code::text AS branch_code,
                r.price
            FROM branch_rooms br
            JOIN rooms r ON r.room_id = br.room_id
            WHERE br.branch_code = %s
              AND br.room_id = %s
              AND br.del_flg = 0
              AND r.del_flg = 0
            ORDER BY br.room_number, br.branch_room_id
            LIMIT 1;
            """,
            (resolved_branch_code, room_id),
        )
        available_branch_room = cur.fetchone()
        if not available_branch_room:
            raise ValueError("Không còn phòng trống cho hạng phòng này tại chi nhánh đã chọn")

        return (
            available_branch_room["room_id"],
            available_branch_room["branch_room_id"],
            available_branch_room["branch_code"],
            float(available_branch_room["price"] or 0),
        )

    raise ValueError("Booking phải có room_id hoặc branch_room_id")


def create_booking(booking: BookingCreate | BookingAdminCreate, total_price: float = 0.0, current_user_id: str = None):
    nights = (booking.to_date - booking.from_date).days
    if nights <= 0:
        raise ValueError("Ngày trả phòng phải sau ngày nhận phòng")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            resolved_room_id, resolved_branch_room_id, resolved_branch_code, nightly_price = _resolve_booking_room(
                cur,
                str(booking.branch_code) if booking.branch_code else None,
                str(booking.room_id) if booking.room_id else None,
                str(booking.branch_room_id) if booking.branch_room_id else None,
            )

            total_price = nightly_price * nights
            now = datetime.now()
            booking_code = _generate_booking_code(resolved_branch_code, now)
            booking_status = _normalize_booking_status(getattr(booking, "status", BookingStatus.PENDING.value))
            requested_payment_status = _normalize_payment_status(getattr(booking, "payment_status", None))
            cur.execute(
                """
                SELECT
                    b.name AS branch_name,
                    rt.name AS room_type_name,
                    br.room_number
                FROM rooms r
                JOIN branches b ON b.branch_code = r.branch_code
                LEFT JOIN room_types rt ON rt.room_type_id = r.room_type_id
                LEFT JOIN branch_rooms br ON br.branch_room_id = %s
                WHERE r.room_id = %s;
                """,
                (resolved_branch_room_id, resolved_room_id),
            )
            room_detail = cur.fetchone() or {}
            cur.execute("""
                INSERT INTO bookings (
                    branch_code, user_id, branch_room_id, booking_code, voucher_code, customer_name, customer_email,
                    customer_phonenumber, note, from_date, to_date, total_price, status,
                    created_date, created_time, created_user, del_flg, room_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
                RETURNING *;
            """, (
                resolved_branch_code,
                str(booking.user_id) if booking.user_id else None,
                resolved_branch_room_id,
                booking_code,
                booking.voucher_code,
                booking.customer_name.strip(),
                booking.customer_email.strip(),
                booking.customer_phonenumber.strip(),
                booking.note.strip() if booking.note else None,
                booking.from_date,
                booking.to_date,
                total_price,
                booking_status,
                now.date(),
                now.time(),
                current_user_id if current_user_id else (str(booking.user_id) if booking.user_id else None),
                resolved_room_id,
            ))

            new_booking = cur.fetchone()
            payment_status = _sync_paid_payment(
                cur,
                resolved_branch_code,
                str(new_booking["booking_id"]),
                total_price,
                requested_payment_status,
                current_user_id if current_user_id else (str(booking.user_id) if booking.user_id else None),
            )

            new_booking["branch_name"] = room_detail.get("branch_name")
            new_booking["room_type_name"] = room_detail.get("room_type_name")
            new_booking["room_number"] = room_detail.get("room_number")
            new_booking["payment_status"] = payment_status
            new_booking["formatted_total_price"] = f"{int(total_price):,} VND".replace(",", ".")

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


def get_all_bookings_with_details():
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    b.*,
                    branch.name AS branch_name,
                    rt.name AS room_type_name,
                    br.room_number,
                    COALESCE(
                        CASE
                            WHEN LOWER(pay.status) IN ('completed', 'paid') THEN 'paid'
                            WHEN LOWER(pay.status) = 'refunded' THEN 'refunded'
                            ELSE 'unpaid'
                        END,
                        'unpaid'
                    ) AS payment_status
                FROM bookings b
                LEFT JOIN branch_rooms br ON br.branch_room_id = b.branch_room_id
                LEFT JOIN rooms r ON r.room_id = b.room_id
                LEFT JOIN branches branch ON branch.branch_code = COALESCE(br.branch_code, r.branch_code)
                LEFT JOIN room_types rt ON rt.room_type_id = r.room_type_id
                LEFT JOIN LATERAL (
                    SELECT p.status
                    FROM payments p
                    WHERE p.booking_id = b.booking_id
                      AND p.del_flg = 0
                    ORDER BY p.created_date DESC, p.created_time DESC, p.payment_id DESC
                    LIMIT 1
                ) pay ON TRUE
                WHERE b.del_flg = 0
                ORDER BY b.created_date DESC, b.created_time DESC, b.booking_id DESC;
                """
            )
            return cur.fetchall()

def update_booking_by_admin(booking_id: str, booking_update: BookingAdminUpdate, admin_id: str = None):
    update_data = booking_update.model_dump(exclude_unset=True)
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM bookings WHERE booking_id = %s AND del_flg = 0;",
                (booking_id,),
            )
            current_booking = cur.fetchone()
            if not current_booking:
                return None

            requested_payment_status = _normalize_payment_status(update_data.pop("payment_status", None)) if "payment_status" in update_data else None

            if "status" in update_data:
                update_data["status"] = _normalize_booking_status(update_data["status"])

            if not update_data and requested_payment_status is None:
                return None

            updated_booking = current_booking

            if update_data:
                set_clauses = []
                values = []

                for key, value in update_data.items():
                    set_clauses.append(f"{key} = %s")
                    if isinstance(value, Enum):
                        values.append(value.value)
                    elif hasattr(value, "hex"):
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
                cur.execute(query, tuple(values))
                updated_booking = cur.fetchone()

            _sync_paid_payment(
                cur,
                (updated_booking or current_booking)["branch_code"],
                booking_id,
                float((updated_booking or current_booking).get("total_price") or 0),
                requested_payment_status,
                str(admin_id) if admin_id else None,
            )
                
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