from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.cockroach import test_cockroach_connection, create_all_tables, create_database_if_not_exists, seed_basic_hotel_data
from app.api import user
from app.api import booking
from app.api import branch
from app.api import room
app = FastAPI(title="FastAPI + CockroachDB + MongoDB")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    print("⏳ Đang kiểm tra kết nối CockroachDB...")
    test_cockroach_connection()

@app.post("/initialize-db")
async def initialize_db():
    """
    Tạo toàn bộ các bảng dữ liệu cần thiết trong CockroachDB.
    """
    create_all_tables()
    return {"status": "success", "message": "Tạo toàn bộ database thành công"}

@app.get("/check-db")
async def check_db():
    test_cockroach_connection()

@app.get("/create-db")
async def create_db():
    create_database_if_not_exists()

@app.get("/seed-db")
async def seed_db():
    seed_basic_hotel_data()

app.include_router(user.router)
app.include_router(booking.router)
app.include_router(branch.router)
app.include_router(branch.routerForUser)
app.include_router(room.router)
app.include_router(room.routerForUser)