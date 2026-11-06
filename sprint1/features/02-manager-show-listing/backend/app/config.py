import os
from functools import lru_cache
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.PROJECT_NAME: str = "Show Ticket Booking System — Manager API"
        self.VERSION: str = "1.0.0"
        self.API_V1_STR: str = "/api/manager"

        # Database
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "")
        self.DB_POOL_MIN_SIZE: int = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
        self.DB_POOL_MAX_SIZE: int = int(os.getenv("DB_POOL_MAX_SIZE", "10"))

        # Firebase Authentication
        self.FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
        self.DEV_BYPASS_AUTH: bool = os.getenv("DEV_BYPASS_AUTH", "false").lower() in ("true", "1", "yes")

        # Cloudinary Image Hosting
        self.CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
        self.CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
        self.CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")

        # CORS
        self.CORS_ORIGINS: List[str] = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

@lru_cache()
def get_settings() -> Settings:
    return Settings()
