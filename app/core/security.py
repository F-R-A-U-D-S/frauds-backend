from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from core.config import settings
import bcrypt
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    # Pre-hash to handle passwords longer than 72 bytes
    password_hashed = hashlib.sha256(password.encode("utf-8")).digest()
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_hashed, salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    password_hashed = hashlib.sha256(password.encode("utf-8")).digest()
    return bcrypt.checkpw(password_hashed, hashed.encode('utf-8'))

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=30))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
