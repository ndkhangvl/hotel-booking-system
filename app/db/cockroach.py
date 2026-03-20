import psycopg
import os
from dotenv import load_dotenv

load_dotenv()

COCKROACH_MODE = os.getenv("COCKROACH_MODE", "single")

DB_HOST = os.getenv("COCKROACH_DB_HOST", "localhost")
DB_PORT = os.getenv("COCKROACH_DB_PORT", "26257")
DB_USER = os.getenv("COCKROACH_DB_USER", "root")
DB_NAME = os.getenv("COCKROACH_DB_NAME", "hotel_booking")

if COCKROACH_MODE == "cluster":
    _cluster_url = os.getenv("COCKROACH_CLUSTER_URL", "")
    DEFAULT_DB_URL = _cluster_url.rsplit("/", 1)[0] + "/defaultdb?sslmode=disable" if _cluster_url else ""
    TARGET_DB_URL = _cluster_url
    print(f"🌐 CockroachDB mode: cluster → {TARGET_DB_URL}")
else:
    DEFAULT_DB_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/defaultdb?sslmode=disable"
    TARGET_DB_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=disable"
    print(f"🖥️  CockroachDB mode: single → {TARGET_DB_URL}")


def get_default_connection():
    return psycopg.connect(DEFAULT_DB_URL)


def get_connection():
    return psycopg.connect(TARGET_DB_URL)


def test_cockroach_connection():
    try:
        with get_default_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT now();")
                result = cur.fetchone()
                print("✅ Kết nối CockroachDB thành công:", result)
    except Exception as e:
        print("❌ Lỗi kết nối CockroachDB:", e)


def create_database_if_not_exists():
    try:
        with get_default_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME};")
                conn.commit()
                print(f"✅ Tạo database '{DB_NAME}' thành công hoặc đã tồn tại")
    except Exception as e:
        print("❌ Lỗi tạo database:", e)


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1;
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def migrate_legacy_schema():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS branch_rooms (
                        branch_room_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        branch_id UUID NOT NULL,
                        room_id UUID NOT NULL,
                        room_number VARCHAR(20) NOT NULL,
                        created_date DATE DEFAULT CURRENT_DATE,
                        created_time TIME DEFAULT CURRENT_TIME,
                        created_user UUID,
                        updated_date DATE,
                        updated_time TIME,
                        updated_user UUID,
                        del_flg SMALLINT DEFAULT 0,

                        CONSTRAINT fk_branch_rooms_branch
                            FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
                        CONSTRAINT fk_branch_rooms_room
                            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                        CONSTRAINT uq_branch_room_number
                            UNIQUE (branch_id, room_number)
                    );
                    """
                )

                if _column_exists(cur, "rooms", "room_number"):
                    cur.execute("ALTER TABLE rooms DROP COLUMN room_number;")

                cur.execute(
                    """
                    INSERT INTO branch_rooms (
                        branch_id,
                        room_id,
                        room_number,
                        created_date,
                        created_time,
                        created_user,
                        updated_date,
                        updated_time,
                        updated_user,
                        del_flg
                    )
                    SELECT
                        src.branch_id,
                        src.room_id,
                        CAST(100 + src.seq AS STRING),
                        src.created_date,
                        src.created_time,
                        src.created_user,
                        src.updated_date,
                        src.updated_time,
                        src.updated_user,
                        src.del_flg
                    FROM (
                        SELECT
                            r.branch_id,
                            r.room_id,
                            r.created_date,
                            r.created_time,
                            r.created_user,
                            r.updated_date,
                            r.updated_time,
                            r.updated_user,
                            r.del_flg,
                            ROW_NUMBER() OVER (
                                PARTITION BY r.branch_id
                                ORDER BY r.created_date, r.room_id
                            ) AS seq
                        FROM rooms r
                    ) AS src
                    LEFT JOIN branch_rooms br ON br.room_id = src.room_id
                    WHERE br.branch_room_id IS NULL;
                    """
                )

                has_booking_room_id = _column_exists(cur, "bookings", "room_id")

                if not has_booking_room_id:
                    cur.execute("ALTER TABLE bookings ADD COLUMN room_id UUID;")

                cur.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS fk_bookings_room;")
                cur.execute(
                    """
                    ALTER TABLE bookings
                    ADD CONSTRAINT fk_bookings_room
                    FOREIGN KEY (room_id) REFERENCES rooms(room_id);
                    """
                )

            conn.commit()
        print("✅ Đồng bộ schema cũ sang schema mới thành công")
    except Exception as e:
        print("❌ Lỗi migrate schema:", e)


def create_all_tables():
    tables = [
        ("users", """
        CREATE TABLE IF NOT EXISTS users (
            user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            phone VARCHAR(15),
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('Guest', 'Customer', 'Receptionist', 'Admin')),
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("branches", """
        CREATE TABLE IF NOT EXISTS branches (
            branch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            address VARCHAR(255) NOT NULL,
            phone VARCHAR(15),
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("room_types", """
        CREATE TABLE IF NOT EXISTS room_types (
            room_type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(50) NOT NULL,
            description TEXT,
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("amenities", """
        CREATE TABLE IF NOT EXISTS amenities (
            amenity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            icon_url VARCHAR(255),
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("rooms", """
        CREATE TABLE IF NOT EXISTS rooms (
            room_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            branch_id UUID,
            room_type_id UUID,
            price DECIMAL(10, 2) NOT NULL,
            people_number INT NOT NULL,
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("branch_rooms", """
        CREATE TABLE IF NOT EXISTS branch_rooms (
            branch_room_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            branch_id UUID NOT NULL,
            room_id UUID NOT NULL,
            room_number VARCHAR(20) NOT NULL,
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0,
            CONSTRAINT uq_branch_room_number UNIQUE (branch_id, room_number)
        );
        """),

        ("room_amenities", """
        CREATE TABLE IF NOT EXISTS room_amenities (
            room_id UUID,
            amenity_id UUID,
            PRIMARY KEY (room_id, amenity_id),
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("vouchers", """
        CREATE TABLE IF NOT EXISTS vouchers (
            voucher_code VARCHAR(20) PRIMARY KEY,
            discount_value DECIMAL(10, 2) NOT NULL,
            valid_from TIMESTAMP NOT NULL,
            valid_to TIMESTAMP NOT NULL,
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("bookings", """
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID,
            branch_room_id UUID,
            voucher_code VARCHAR(20),
            from_date DATE NOT NULL,
            to_date DATE NOT NULL,
            total_price DECIMAL(10, 2) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'Pending',
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("reviews", """
        CREATE TABLE IF NOT EXISTS reviews (
            review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            booking_id UUID,
            rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("payments", """
        CREATE TABLE IF NOT EXISTS payments (
            payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            booking_id UUID,
            amount DECIMAL(10, 2) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'Pending',
            created_date DATE DEFAULT current_date(),
            created_time TIME DEFAULT current_time(),
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """)
    ]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for table_name, ddl in tables:
                    cur.execute(ddl)
                    print(f"✅ Tạo bảng {table_name} thành công")
            conn.commit()
        migrate_legacy_schema()
        print("🎉 Tạo toàn bộ bảng thành công")
    except Exception as e:
        print("❌ Lỗi tạo bảng:", e)

def seed_basic_hotel_data():
    sql_statements = [
        # 1. Bảng branches
        """INSERT INTO branches (
            branch_id, name, address, phone,
            created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg
        ) VALUES
        ('a1000000-0000-0000-0000-000000000001', 'Aurora Vĩnh Long', '12 Nguyễn Huệ, Phường 1, TP. Vĩnh Long, Vĩnh Long', '02703881111', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('a1000000-0000-0000-0000-000000000002', 'Aurora An Giang', '88 Trần Hưng Đạo, TP. Châu Đốc, An Giang', '02963882222', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('a1000000-0000-0000-0000-000000000003', 'Aurora Cần Thơ', '25 Hai Bà Trưng, Quận Ninh Kiều, Cần Thơ', '02923883333', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('a1000000-0000-0000-0000-000000000004', 'Aurora Sóc Trăng', '40 Phú Lợi, TP. Sóc Trăng, Sóc Trăng', '02993884444', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('a1000000-0000-0000-0000-000000000005', 'Aurora Bạc Liêu', '18 Hòa Bình, TP. Bạc Liêu, Bạc Liêu', '02913885555', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('a1000000-0000-0000-0000-000000000006', 'Aurora Cà Mau', '66 Phan Ngọc Hiển, TP. Cà Mau, Cà Mau', '02903886666', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('a1000000-0000-0000-0000-000000000007', 'Aurora Trà Vinh', '09 Điện Biên Phủ, TP. Trà Vinh, Trà Vinh', '02943887777', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0);""",

        # 2. Bảng room_types
        """INSERT INTO room_types (
            room_type_id, name, description,
            created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg
        ) VALUES
        ('b2000000-0000-0000-0000-000000000001', 'Phòng Tiêu chuẩn', 'Phòng cơ bản dành cho 2 khách, đầy đủ tiện nghi thiết yếu.', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('b2000000-0000-0000-0000-000000000002', 'Phòng Cao cấp', 'Phòng rộng rãi hơn, nội thất hiện đại, phù hợp cho cặp đôi.', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('b2000000-0000-0000-0000-000000000003', 'Phòng Deluxe', 'Phòng có cửa sổ lớn, không gian thoáng, phù hợp nghỉ dưỡng.', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('b2000000-0000-0000-0000-000000000004', 'Phòng Gia đình', 'Phòng lớn dành cho 3-4 khách, phù hợp gia đình nhỏ.', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('b2000000-0000-0000-0000-000000000005', 'Phòng Suite', 'Phòng hạng sang, có khu tiếp khách riêng và tiện nghi cao cấp.', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0);""",

        # 3. Bảng amenities
        """INSERT INTO amenities (
            amenity_id, name, icon_url,
            created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg
        ) VALUES
        ('c3000000-0000-0000-0000-000000000001', 'Wifi miễn phí', '/icons/wifi.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000002', 'Máy lạnh', '/icons/ac.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000003', 'TV màn hình phẳng', '/icons/tv.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000004', 'Minibar', '/icons/minibar.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000005', 'Máy sấy tóc', '/icons/hairdryer.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000006', 'Bồn tắm', '/icons/bathtub.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000007', 'Ban công', '/icons/balcony.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000008', 'Ăn sáng miễn phí', '/icons/breakfast.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000009', 'Hồ bơi', '/icons/pool.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('c3000000-0000-0000-0000-000000000010', 'Phòng tập gym', '/icons/gym.png', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0);""",

        # 4. Bảng users
        """INSERT INTO users (
            user_id, name, email, phone, password, role,
            created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg
        ) VALUES
        ('e5000000-0000-0000-0000-000000000001', 'Khang Admin', 'admin@aurora.com', '0901234567', 'hashed_password_admin', 'Admin', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('e5000000-0000-0000-0000-000000000002', 'Lễ tân Cần Thơ', 'receptionist.ct@aurora.com', '0902345678', 'hashed_password_recep', 'Receptionist', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        -- Tài khoản Khách hàng
        ('e5000000-0000-0000-0000-000000000003', 'Nguyễn Văn A', 'nguyenvana@gmail.com', '0903456789', 'hashed_password_cus1', 'Customer', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        ('e5000000-0000-0000-0000-000000000004', 'Trần Thị B', 'tranthib@gmail.com', '0904567890', 'hashed_password_cus2', 'Customer', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
        -- Tài khoản Khách vãng lai (Guest)
        ('e5000000-0000-0000-0000-000000000005', 'Khách Vãng Lai', 'guest1@gmail.com', '0905678901', 'hashed_password_guest', 'Guest', CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0);""",

        # 5. Bảng rooms và branch_rooms (Dùng CTE)
        """WITH room_seed AS (
            SELECT *
            FROM (VALUES
                ('b2000000-0000-0000-0000-000000000001'::UUID, 450000.00::DECIMAL(10, 2), 2, 2),
                ('b2000000-0000-0000-0000-000000000002'::UUID, 620000.00::DECIMAL(10, 2), 2, 3),
                ('b2000000-0000-0000-0000-000000000003'::UUID, 820000.00::DECIMAL(10, 2), 2, 2),
                ('b2000000-0000-0000-0000-000000000004'::UUID, 1000000.00::DECIMAL(10, 2), 4, 2),
                ('b2000000-0000-0000-0000-000000000005'::UUID, 1450000.00::DECIMAL(10, 2), 2, 1)
            ) AS s(room_type_id, price, people_number, copies)
        ),
        inserted_rooms AS (
            INSERT INTO rooms (
                room_id, branch_id, room_type_id, price, people_number,
                created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg
            )
            SELECT
                gen_random_uuid(), b.branch_id, s.room_type_id, s.price, s.people_number,
                CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0
            FROM branches b
            CROSS JOIN room_seed s
            CROSS JOIN generate_series(1, s.copies)
            RETURNING room_id, branch_id, created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg
        ),
        numbered_rooms AS (
            SELECT
                room_id, branch_id, created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg,
                ROW_NUMBER() OVER (PARTITION BY branch_id ORDER BY room_id) AS seq
            FROM inserted_rooms
        )
        INSERT INTO branch_rooms (
            branch_id, room_id, room_number,
            created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg
        )
        SELECT
            branch_id, room_id, CAST(100 + seq AS VARCHAR),
            created_date, created_time, created_user, updated_date, updated_time, updated_user, del_flg
        FROM numbered_rooms;""",

        # 6. Bảng room_amenities (Gán Wifi và Máy lạnh cho tất cả các phòng làm dữ liệu mẫu)
        """INSERT INTO room_amenities (room_id, amenity_id, created_date, created_time, del_flg)
        SELECT r.room_id, a.amenity_id, CURRENT_DATE, CURRENT_TIME, 0
        FROM rooms r
        CROSS JOIN amenities a
        WHERE a.name IN ('Wifi miễn phí', 'Máy lạnh', 'TV màn hình phẳng');""",

        # 7. Bảng vouchers
        """INSERT INTO vouchers (voucher_code, discount_value, valid_from, valid_to, created_date, created_time, del_flg)
        VALUES 
        ('WELCOME2026', 150000.00, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '30 days', CURRENT_DATE, CURRENT_TIME, 0),
        ('SUMMER2026', 200000.00, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '90 days', CURRENT_DATE, CURRENT_TIME, 0);""",

        # 8. Bảng bookings (Lấy ngẫu nhiên 2 phòng từ branch_rooms để tạo booking cho khách Nguyễn Văn A)
        """WITH sample_rooms AS (
            SELECT branch_room_id FROM branch_rooms LIMIT 2
        )
        INSERT INTO bookings (booking_id, user_id, branch_room_id, voucher_code, from_date, to_date, total_price, status, created_date, created_time, del_flg)
        SELECT 
            gen_random_uuid(),
            'e5000000-0000-0000-0000-000000000003'::UUID, -- Nguyễn Văn A
            branch_room_id,
            'WELCOME2026',
            CURRENT_DATE + INTERVAL '1 day',
            CURRENT_DATE + INTERVAL '3 days',
            1200000.00, -- Giá mô phỏng
            'Confirmed',
            CURRENT_DATE, CURRENT_TIME, 0
        FROM sample_rooms;""",

        # 9. Bảng payments (Tạo thanh toán thành công cho các booking vừa tạo)
        """INSERT INTO payments (payment_id, booking_id, amount, status, created_date, created_time, del_flg)
        SELECT 
            gen_random_uuid(),
            booking_id,
            total_price,
            'Completed',
            CURRENT_DATE, CURRENT_TIME, 0
        FROM bookings;""",

        # 10. Bảng reviews (Đánh giá cho các booking)
        """INSERT INTO reviews (review_id, booking_id, rating, comment, created_date, created_time, del_flg)
        SELECT 
            gen_random_uuid(),
            booking_id,
            5,
            'Khách sạn sạch sẽ, nhân viên thân thiện, vị trí thuận lợi!',
            CURRENT_DATE, CURRENT_TIME, 0
        FROM bookings;"""
    ]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for sql in sql_statements:
                    cur.execute(sql)
            conn.commit()
        print("✅ Seed toàn bộ dữ liệu mẫu Aurora thành công")
    except Exception as e:
        print("❌ Lỗi seed dữ liệu:", e)