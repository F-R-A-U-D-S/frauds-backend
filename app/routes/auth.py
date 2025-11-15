from fastapi import APIRouter, Depends, HTTPException
from core.security import hash_password, verify_password, create_access_token
from db.session import SessionLocal
from db.models import User 
from db.session import get_db
from sqlalchemy.orm import Session
from schemas.user import UserCreate, UserLogin



router = APIRouter()

@router.post("/register")

def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="User already exists")

    # hashed = hash_password(user.password)
    hashed = "<hashed_password_from_db>"
    verify_password("test123", hashed) 
    new_user = User(email=user.email, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created", "user_id": new_user.id}


@router.post("/login")

def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}
