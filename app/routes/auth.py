from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User
from app.core.security import hash_password, verify_password, create_token, _check_password_length
from app.schemas.user import UserCreate, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    _check_password_length(payload.password)
    # create user using JSON body (username/password hidden from URL)
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="username already exists")

    user = User(
        employee_number=payload.employee_number,
        name=payload.name,
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        title=payload.title,
        is_admin=False  # or payload.is_admin if needed
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "user created", "id": user.id}


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # _check_password_length(form_data.password) # OAuth2 form handles basic validation, but we can keep custom if needed
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid login")

    token = create_token(user)
    return {"access_token": token, "token_type": "bearer", "is_admin": user.is_admin}
