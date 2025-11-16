from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import User
from core.security import hash_password, verify_password, create_token
from schemas.user import UserCreate, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    # create user using JSON body (username/password hidden from URL)
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="username already exists")

    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "user created", "id": user.id}


@router.post("/login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid login")

    token = create_token(user)
    return {"access_token": token}
