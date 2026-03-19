import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from decimal import Decimal
from bson import Decimal128
import asyncio
load_dotenv()

MONGO_MODE = os.getenv("MONGO_MODE", "single").lower()

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_DB = os.getenv("MONGO_DB", "hotel_booking")
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")

MONGO_CLUSTER_URL = os.getenv("MONGO_CLUSTER_URL")

mongo_client: AsyncIOMotorClient | None = None


def build_mongo_url() -> str:
    if MONGO_MODE == "cluster":
        if not MONGO_CLUSTER_URL:
            raise RuntimeError("MONGO_CLUSTER_URL is missing in .env")
        return MONGO_CLUSTER_URL

    if MONGO_USER and MONGO_PASSWORD:
        return (
            f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
            f"@{MONGO_HOST}:{MONGO_PORT}/"
            f"{MONGO_DB}?authSource={MONGO_AUTH_DB}"
        )

    return f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"


def get_mongo_db() -> AsyncIOMotorDatabase:
    if mongo_client is None:
        raise RuntimeError("Mongo client not initialized")
    return mongo_client[MONGO_DB]


async def connect_mongo() -> None:
    global mongo_client

    if mongo_client is not None:
        return

    mongo_url = build_mongo_url()
    print(f"Mongo mode: {MONGO_MODE}")
    print(f"Mongo URL: {mongo_url}")

    mongo_client = AsyncIOMotorClient(mongo_url)

    await mongo_client.admin.command("ping")
    print("✅ MongoDB connected")


async def close_mongo() -> None:
    global mongo_client

    if mongo_client is not None:
        mongo_client.close()
        mongo_client = None
        print("🔌 MongoDB closed")


async def test_mongo_connection() -> None:
    global mongo_client

    if mongo_client is None:
        raise RuntimeError("Mongo client not initialized. Call connect_mongo() first.")

    try:
        result = await mongo_client.admin.command("ping")
        print("✅ MongoDB ping:", result)
    except Exception as e:
        print("❌ MongoDB connection error:", e)


async def insert_room(room_data: dict) -> str:
    """
    Chèn một document vào collection 'room' của db 'hotel_booking'.
    Tự động convert price thành Decimal128 nếu cần.
    """
    db = get_mongo_db()
    room_collection = db['room']

    # Bảo đảm 'price' là kiểu Decimal128 nếu có trong room_data
    if 'price' in room_data:
        price_val = room_data["price"]
        # Nếu price là dict có keys kiểu {"$numberDecimal": ...}
        if isinstance(price_val, dict) and "$numberDecimal" in price_val:
            room_data["price"] = Decimal128(price_val["$numberDecimal"])
        elif not isinstance(price_val, Decimal128):
            room_data["price"] = Decimal128(str(price_val))

    result = await room_collection.insert_one(room_data)
    return str(result.inserted_id)

async def insert_sample_room_data():
    sample_room = {
        "_id": "uuid-room-001",
        "branch_id": "uuid-branch-001",
        "branch_name": "Chi nhánh Hà Nội",
        "room_type_name": "Deluxe",
        "room_number": "101",
        "price": {"$numberDecimal": "1200000"},
        "people_number": 2,
        "amenities": ["Wifi", "Hồ bơi", "TV", "Ban công"],
        "images": ["url1", "url2"],
        "reviews": [
            {
                "review_id": "uuid-review-001",
                "rating": 5,
                "comment": "Phòng rất sạch sẽ!"
            }
        ],
        "created_date": "2026-03-19",
        "created_time": "10:30:00",
        "updated_date": "2026-03-19",
        "updated_time": "10:30:00",
        "del_flg": 0
    }
    await connect_mongo()
    inserted_id = await insert_room(sample_room)
    print(f"Inserted room with _id: {inserted_id}")