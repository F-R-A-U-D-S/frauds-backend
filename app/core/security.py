from passlib.context import CryptContext
from jose import jwt
import time
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer

from app.db.session import SessionLocal
from app.db.models import User

pwd = CryptContext(schemes=["argon2"], deprecated="auto")
auth_scheme = HTTPBearer()

SECRET = "dev-secret"  # move to .env later


def _check_password_length(password: str):
    if not isinstance(password, str):
        raise HTTPException(status_code=400, detail="password must be a string")
    b = password.encode("utf-8")
    if len(b) > 72:
        # bcrypt has a 72-byte input limitation; ask the caller to truncate or choose a shorter password
        raise HTTPException(
            status_code=400,
            detail=(
                "password too long: bcrypt limits passwords to 72 bytes when UTF-8 encoded. "
                "Please truncate the password to 72 bytes (e.g. password[:72]) or choose a shorter password."
            ),
        )


def hash_password(password: str):
    return pwd.hash(password)


def verify_password(plain: str, hashed: str):
    return pwd.verify(plain, hashed)

def create_token(user):
    payload = {
        "sub": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "exp": int(time.time()) + 3600
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def get_current_user(credentials = Depends(auth_scheme)):
    token = credentials.credentials
    try:
        data = jwt.decode(token, SECRET, algorithms=["HS256"])
        return data
    except:
        raise HTTPException(401, "invalid token")

def require_admin(user = Depends(get_current_user)):
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="admin access required")
    return user