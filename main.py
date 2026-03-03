from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.db.mongo import connect_mongo, close_mongo

app = FastAPI(title="FastAPI + CockroachDB + MongoDB")

@app.on_event("startup")
async def on_startup():
    await connect_mongo()

@app.on_event("shutdown")
async def on_shutdown():
    await close_mongo()

app.include_router(health_router, prefix="/health", tags=["health"])