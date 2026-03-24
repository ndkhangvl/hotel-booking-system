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
                        branch_code VARCHAR(20) NOT NULL,
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
                            FOREIGN KEY (branch_code) REFERENCES branches(branch_code),
                        CONSTRAINT fk_branch_rooms_room
                            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                        CONSTRAINT uq_branch_room_number
                            UNIQUE (branch_code, room_number)
                    );
                    """
                )

                if _column_exists(cur, "rooms", "room_number"):
                    cur.execute("ALTER TABLE rooms DROP COLUMN room_number;")

                cur.execute(
                    """
                    INSERT INTO branch_rooms (
                        branch_code,
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
                        src.branch_code,
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
                            r.branch_code,
                            r.room_id,
                            r.created_date,
                            r.created_time,
                            r.created_user,
                            r.updated_date,
                            r.updated_time,
                            r.updated_user,
                            r.del_flg,
                            ROW_NUMBER() OVER (
                                PARTITION BY r.branch_code
                                ORDER BY r.created_date, r.room_id
                            ) AS seq
                        FROM rooms r
                    ) AS src
                    LEFT JOIN branch_rooms br ON br.room_id = src.room_id
                    WHERE br.branch_room_id IS NULL;
                    """
                )

                booking_columns = {
                    "branch_room_id": "UUID",
                    "booking_code": "VARCHAR(32)",
                    "voucher_code": "VARCHAR(20)",
                    "customer_name": "VARCHAR(100)",
                    "customer_email": "VARCHAR(150)",
                    "customer_phonenumber": "VARCHAR(15)",
                    "note": "STRING",
                    "room_id": "UUID",
                }

                for column_name, column_type in booking_columns.items():
                    if not _column_exists(cur, "bookings", column_name):
                        cur.execute(f"ALTER TABLE bookings ADD COLUMN {column_name} {column_type};")

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
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
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
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
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
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
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
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0
        );
        """),

        ("branches", """
        CREATE TABLE IF NOT EXISTS branches (
            branch_code VARCHAR(20) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            address VARCHAR(255) NOT NULL,
            phone VARCHAR(15),
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0,
            room_id UUID
        );
        """),

        ("rooms", """
        CREATE TABLE IF NOT EXISTS rooms (
            branch_code VARCHAR(20) NOT NULL,
            room_id UUID DEFAULT gen_random_uuid(),
            room_type_id UUID,
            price DECIMAL(10, 2) NOT NULL,
            people_number INT NOT NULL,
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0,
            PRIMARY KEY (branch_code, room_id)
        );
        """),

        ("branch_rooms", """
        CREATE TABLE IF NOT EXISTS branch_rooms (
            branch_code VARCHAR(20) NOT NULL,
            branch_room_id UUID DEFAULT gen_random_uuid(),
            room_id UUID NOT NULL,
            room_number VARCHAR(20) NOT NULL,
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0,
            PRIMARY KEY (branch_code, branch_room_id),
            CONSTRAINT uq_branch_room_number UNIQUE (branch_code, room_number)
        );
        """),

        ("room_amenities", """
        CREATE TABLE IF NOT EXISTS room_amenities (
            branch_code VARCHAR(20) NOT NULL,
            room_id UUID,
            amenity_id UUID,
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0,
            PRIMARY KEY (branch_code, room_id, amenity_id)
        );
        """),

        ("bookings", """
        CREATE TABLE IF NOT EXISTS bookings (
            branch_code VARCHAR(20) NOT NULL,
            booking_id UUID NOT NULL DEFAULT gen_random_uuid(),
            booking_code VARCHAR(22) NOT NULL,
            user_id UUID NULL,
            branch_room_id UUID NULL,
            voucher_code VARCHAR(20) NULL,
            customer_name VARCHAR(100) NOT NULL,
            customer_email VARCHAR(150) NULL,
            customer_phonenumber VARCHAR(15) NOT NULL,
            note TEXT NULL,
            from_date DATE NOT NULL,
            to_date DATE NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'Pending',
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
            created_user UUID NULL,
            updated_date DATE NULL,
            updated_time TIME NULL,
            updated_user UUID NULL,
            del_flg SMALLINT DEFAULT 0,
            room_id UUID NULL,
            CONSTRAINT bookings_pkey PRIMARY KEY (branch_code, booking_id),
            CONSTRAINT bookings_booking_code_key UNIQUE (booking_code)
        );
        """),

        ("payments", """
        CREATE TABLE IF NOT EXISTS payments (
            branch_code VARCHAR(20) NOT NULL,
            payment_id UUID DEFAULT gen_random_uuid(),
            booking_id UUID,
            amount DECIMAL(10, 2) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'Pending',
            created_date DATE DEFAULT CURRENT_DATE,
            created_time TIME DEFAULT CURRENT_TIME,
            created_user UUID,
            updated_date DATE,
            updated_time TIME,
            updated_user UUID,
            del_flg SMALLINT DEFAULT 0,
            PRIMARY KEY (branch_code, payment_id)
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
        print("🎉 Tạo toàn bộ bảng thành công")
    except Exception as e:
        print("❌ Lỗi tạo bảng:", e)

def configure_partitions_and_zones():
    """
    Hàm này tự động tạo partition cho các bảng có chứa dữ liệu theo chi nhánh 
    và ép các partition đó vào đúng máy chủ (node) dựa trên thẻ locality của 4 tỉnh.
    """
    
    partitioned_tables = [
        "rooms",
        "branch_rooms",
        "room_amenities",
        "bookings",
        "payments"
    ]

    setup_queries = []

    for table in partitioned_tables:
        partition_sql = f"""
        ALTER TABLE {table} PARTITION BY LIST (branch_code) (
            PARTITION p_ct_{table} VALUES IN ('CT'),
            PARTITION p_vl_{table} VALUES IN ('VL'),
            PARTITION p_ag_{table} VALUES IN ('AG'),
            PARTITION p_cm_{table} VALUES IN ('CM')
        );
        """
        setup_queries.append(partition_sql)

        zone_configs = [
            f"ALTER PARTITION p_ct_{table} OF INDEX {table}@primary CONFIGURE ZONE USING constraints = '[+branch=CT]';",
            f"ALTER PARTITION p_vl_{table} OF INDEX {table}@primary CONFIGURE ZONE USING constraints = '[+branch=VL]';",
            f"ALTER PARTITION p_ag_{table} OF INDEX {table}@primary CONFIGURE ZONE USING constraints = '[+branch=AG]';",
            f"ALTER PARTITION p_cm_{table} OF INDEX {table}@primary CONFIGURE ZONE USING constraints = '[+branch=CM]';"
        ]
        setup_queries.extend(zone_configs)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for query in setup_queries:
                    cur.execute(query)
                    log_text = query.strip().split('\n')[0][:50]
                    print(f"✅ Đã thực thi: {log_text}...")
            conn.commit()
        print("🎉 Cấu hình toàn bộ phân vùng cho CT, VL, AG, CM thành công!")
    except Exception as e:
        print("❌ Lỗi khi cấu hình phân vùng:", e)

def seed_basic_hotel_data():
    sql_statements = [
        # 1. branches - chỉ 4 chi nhánh
        """
        INSERT INTO branches (
            branch_code, name, address, phone,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        ) VALUES
            ('CT', 'Aurora Cần Thơ', '25 Hai Bà Trưng, Quận Ninh Kiều, Cần Thơ', '02923883333',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('VL', 'Aurora Vĩnh Long', '12 Nguyễn Huệ, Phường 1, TP. Vĩnh Long, Vĩnh Long', '02703881111',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('AG', 'Aurora An Giang', '88 Trần Hưng Đạo, TP. Châu Đốc, An Giang', '02963882222',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('CM', 'Aurora Cà Mau', '66 Phan Ngọc Hiển, TP. Cà Mau, Cà Mau', '02903886666',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0)
        ON CONFLICT (branch_code) DO NOTHING;
        """,

        # 2. room_types
        """
        INSERT INTO room_types (
            room_type_id, name, description,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        ) VALUES
            ('b2000000-0000-0000-0000-000000000001', 'Phòng Tiêu chuẩn',
             'Phòng cơ bản dành cho 2 khách, đầy đủ tiện nghi thiết yếu.',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('b2000000-0000-0000-0000-000000000002', 'Phòng Cao cấp',
             'Phòng rộng rãi hơn, nội thất hiện đại, phù hợp cho cặp đôi.',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('b2000000-0000-0000-0000-000000000003', 'Phòng Deluxe',
             'Phòng có cửa sổ lớn, không gian thoáng, phù hợp nghỉ dưỡng.',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('b2000000-0000-0000-0000-000000000004', 'Phòng Gia đình',
             'Phòng lớn dành cho 3-4 khách, phù hợp gia đình nhỏ.',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('b2000000-0000-0000-0000-000000000005', 'Phòng Suite',
             'Phòng hạng sang, có khu tiếp khách riêng và tiện nghi cao cấp.',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0)
        ON CONFLICT (room_type_id) DO NOTHING;
        """,

        # 3. amenities
        """
        INSERT INTO amenities (
            amenity_id, name, icon_url,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        ) VALUES
            ('c3000000-0000-0000-0000-000000000001', 'Wifi miễn phí', '/icons/wifi.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000002', 'Máy lạnh', '/icons/ac.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000003', 'TV màn hình phẳng', '/icons/tv.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000004', 'Minibar', '/icons/minibar.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000005', 'Máy sấy tóc', '/icons/hairdryer.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000006', 'Bồn tắm', '/icons/bathtub.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000007', 'Ban công', '/icons/balcony.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000008', 'Ăn sáng miễn phí', '/icons/breakfast.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000009', 'Hồ bơi', '/icons/pool.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),
            ('c3000000-0000-0000-0000-000000000010', 'Phòng tập gym', '/icons/gym.png',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0)
        ON CONFLICT (amenity_id) DO NOTHING;
        """,

        # 4. users
        """
        INSERT INTO users (
            user_id, name, email, phone, password, role,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        ) VALUES
            ('e5000000-0000-0000-0000-000000000001', 'Khang Admin', 'admin@aurora.com', '0901234567',
             'hashed_password_admin', 'Admin',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('e5000000-0000-0000-0000-000000000002', 'Lễ tân Cần Thơ', 'receptionist.ct@aurora.com', '0902345678',
             'hashed_password_recep', 'Receptionist',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('e5000000-0000-0000-0000-000000000003', 'Nguyễn Văn A', 'nguyenvana@gmail.com', '0903456789',
             'hashed_password_cus1', 'Customer',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('e5000000-0000-0000-0000-000000000004', 'Trần Thị B', 'tranthib@gmail.com', '0904567890',
             'hashed_password_cus2', 'Customer',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('e5000000-0000-0000-0000-000000000005', 'Khách Vãng Lai', 'guest1@gmail.com', '0905678901',
             'hashed_password_guest', 'Guest',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0)
        ON CONFLICT (user_id) DO NOTHING;
        """,

        # 5. vouchers
        """
        INSERT INTO vouchers (
            voucher_code, discount_value, valid_from, valid_to,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        ) VALUES
            ('WELCOME2026', 150000.00, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '30 days',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0),

            ('SUMMER2026', 200000.00, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '90 days',
             CURRENT_DATE, CURRENT_TIME, NULL, NULL, NULL, NULL, 0)
        ON CONFLICT (voucher_code) DO NOTHING;
        """,

        # 6. rooms + branch_rooms
        """
        WITH room_seed AS (
            SELECT *
            FROM (VALUES
                ('b2000000-0000-0000-0000-000000000001'::UUID, 450000.00::DECIMAL(10,2), 2, 2),
                ('b2000000-0000-0000-0000-000000000002'::UUID, 620000.00::DECIMAL(10,2), 2, 3),
                ('b2000000-0000-0000-0000-000000000003'::UUID, 820000.00::DECIMAL(10,2), 2, 2),
                ('b2000000-0000-0000-0000-000000000004'::UUID, 1000000.00::DECIMAL(10,2), 4, 2),
                ('b2000000-0000-0000-0000-000000000005'::UUID, 1450000.00::DECIMAL(10,2), 2, 1)
            ) AS s(room_type_id, price, people_number, copies)
        ),
        inserted_rooms AS (
            INSERT INTO rooms (
                branch_code, room_id, room_type_id, price, people_number,
                created_date, created_time, created_user,
                updated_date, updated_time, updated_user, del_flg
            )
            SELECT
                b.branch_code,
                gen_random_uuid(),
                s.room_type_id,
                s.price,
                s.people_number,
                CURRENT_DATE, CURRENT_TIME, NULL,
                NULL, NULL, NULL, 0
            FROM branches b
            CROSS JOIN room_seed s
            CROSS JOIN generate_series(1, s.copies)
            RETURNING branch_code, room_id, created_date, created_time, created_user,
                      updated_date, updated_time, updated_user, del_flg
        ),
        numbered_rooms AS (
            SELECT
                branch_code, room_id, created_date, created_time, created_user,
                updated_date, updated_time, updated_user, del_flg,
                ROW_NUMBER() OVER (PARTITION BY branch_code ORDER BY room_id) AS seq
            FROM inserted_rooms
        )
        INSERT INTO branch_rooms (
            branch_code, branch_room_id, room_id, room_number,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        )
        SELECT
            branch_code,
            gen_random_uuid(),
            room_id,
            CAST(100 + seq AS VARCHAR),
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        FROM numbered_rooms;
        """,

        # 7. room_amenities
        """
        INSERT INTO room_amenities (
            branch_code, room_id, amenity_id,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        )
        SELECT
            r.branch_code,
            r.room_id,
            a.amenity_id,
            CURRENT_DATE,
            CURRENT_TIME,
            NULL,
            NULL,
            NULL,
            NULL,
            0
        FROM rooms r
        CROSS JOIN amenities a
        WHERE a.name IN ('Wifi miễn phí', 'Máy lạnh', 'TV màn hình phẳng');
        """,

        # 8. bookings
        """
        WITH sample_rooms AS (
            SELECT
                br.branch_code,
                br.branch_room_id,
                br.room_id,
                ROW_NUMBER() OVER (ORDER BY br.branch_code, br.room_number) AS rn
            FROM branch_rooms br
            WHERE br.del_flg = 0
            LIMIT 4
        )
        INSERT INTO bookings (
            branch_code, booking_id, booking_code,
            user_id, branch_room_id, voucher_code,
            customer_name, customer_email, customer_phonenumber,
            note, from_date, to_date, total_price, status,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg, room_id
        )
        SELECT
            sr.branch_code,
            gen_random_uuid(),
            'BK' || TO_CHAR(CURRENT_DATE, 'YYMMDD') || LPAD(sr.rn::STRING, 4, '0'),
            'e5000000-0000-0000-0000-000000000003'::UUID,
            sr.branch_room_id,
            'WELCOME2026',
            'Nguyễn Văn A',
            'nguyenvana@gmail.com',
            '0903456789',
            'Đặt phòng online',
            CURRENT_DATE + 1,
            CURRENT_DATE + 3,
            CASE
                WHEN sr.branch_code = 'CT' THEN 1240000.00
                WHEN sr.branch_code = 'VL' THEN 900000.00
                WHEN sr.branch_code = 'AG' THEN 1640000.00
                ELSE 2000000.00
            END,
            'Confirmed',
            CURRENT_DATE, CURRENT_TIME, NULL,
            NULL, NULL, NULL, 0,
            sr.room_id
        FROM sample_rooms sr;
        """,

        # 9. payments
        """
        INSERT INTO payments (
            branch_code, payment_id, booking_id, amount, status,
            created_date, created_time, created_user,
            updated_date, updated_time, updated_user, del_flg
        )
        SELECT
            b.branch_code,
            gen_random_uuid(),
            b.booking_id,
            b.total_price,
            'Completed',
            CURRENT_DATE,
            CURRENT_TIME,
            NULL,
            NULL,
            NULL,
            NULL,
            0
        FROM bookings b
        WHERE b.del_flg = 0;
        """
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