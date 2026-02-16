"""
JWT авторизация для дашборда
"""
from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_HOURS, ADMIN_PASSWORD

security = HTTPBearer()


def create_access_token(data: dict) -> str:
    """Создать JWT токен"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Проверить JWT токен"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def verify_password(password: str) -> bool:
    """Проверить пароль админа"""
    return password == ADMIN_PASSWORD


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """Получить текущего пользователя из токена"""
    token = credentials.credentials
    payload = verify_token(token)
    return payload
