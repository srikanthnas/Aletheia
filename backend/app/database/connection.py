"""
MongoDB async connection management using Motor.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# Module-level client and database references
_client: AsyncIOMotorClient | None = None


async def connect_to_mongo():
    global _client
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    print(f"[Aletheia] Connected to MongoDB at {settings.MONGODB_URL}")


async def close_mongo_connection():
    global _client
    if _client:
        _client.close()
        print("[Aletheia] MongoDB connection closed.")


def get_database():
    """Return the Motor database instance. Used as a FastAPI dependency."""
    return _client[settings.DATABASE_NAME]
