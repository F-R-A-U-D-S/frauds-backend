from fastapi import APIRouter, Depends, HTTPException
from app.core.security import hash_password, verify_password, create_access_token
from app.db.session import SessionLocal
from app.db.models import User

router = APIRouter()

@router.post("/register")
def register(username: str, password: str):
    db = SessionLocal()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="User already exists")
    hashed = hash_password(password)
    db.add(User(username=username, hashed_password=hashed))
    db.commit()
    return {"message": "User created"}

@router.post("/login")
def login(username: str, password: str):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token}
