# from motor.motor_asyncio import AsyncIOMotorClient
# from app.core.config import settings

# mongo_client: AsyncIOMotorClient | None = None

# def get_mongo_db():
#     if mongo_client is None:
#         raise RuntimeError("Mongo client not initialized")
#     return mongo_client[settings.MONGO_DB]

# async def connect_mongo():
#     global mongo_client
#     mongo_client = AsyncIOMotorClient(settings.MONGO_URL)

# async def close_mongo():
#     global mongo_client
#     if mongo_client is not None:
#         mongo_client.close()
#         mongo_client = None