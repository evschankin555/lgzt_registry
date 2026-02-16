"""
Конфигурация Registry Dashboard
"""
import os
from pathlib import Path

# Пути
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# База данных (используем существующую БД бота)
DATABASE_URL = f"sqlite+aiosqlite:///{PROJECT_ROOT}/app.db"

# Безопасность
SECRET_KEY = os.getenv("REGISTRY_SECRET_KEY", "your-secret-key-change-in-production")
ADMIN_PASSWORD = os.getenv("REGISTRY_ADMIN_PASSWORD", "admin2026")

# JWT
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# API
API_PREFIX = "/api"
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://lgzt.developing-site.ru",
]
