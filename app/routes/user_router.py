import json
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password, require_admin
from app.db.session import get_db
from app.db.models import User, UserCreate, UserPublic, UserUpdate
from sqlmodel import select

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.post("", response_model=UserPublic)
def create_user(
    user: UserCreate,
    session: Session = Depends(get_db)
):
    # Map UserCreate to SQLAlchemy ORM User
    db_user = User(
        employee_number=user.employee_number,
        name=user.name,
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password_hash),
        title=user.title
    )

    # Save to DB
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return db_user

@router.get("", response_model=list[UserPublic])
def read_users(
    response: Response,
    session: Session = Depends(get_db),
    sort: str = Query(default='["id","ASC"]'),
    range: str = Query(default='[0,9]'),
    filter: str = Query(default='{}'),
):

    sort_field, sort_order = json.loads(sort)
    range_start, range_end = json.loads(range)
    filters = json.loads(filter)


    query = select(User)


    for field, value in filters.items():
        if hasattr(User, field):
            query = query.where(getattr(User, field) == value)


    if hasattr(User, sort_field):
        if sort_order.upper() == "ASC":
            query = query.order_by(getattr(User, sort_field).asc())
        else:
            query = query.order_by(getattr(User, sort_field).desc())


    limit = range_end - range_start + 1
    query = query.offset(range_start).limit(limit)

    results = session.execute(query).scalars().all()
    total = session.execute(select(func.count(User.id))).scalar_one()
  #  results = session.exec(query).all()

   # total = session.exec(select(func.count(User.id))).one()

    response.headers["Content-Range"] = (
        f"users {range_start}-{range_start + len(results) - 1}/{total}"
    )
    response.headers["Access-Control-Expose-Headers"] = "Content-Range"

    return results



@router.get("/{user_id}", response_model=UserPublic)
def read_user(
    user_id: str,
    session: Session = Depends(get_db)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: str,
    user: UserUpdate,
    session: Session = Depends(get_db)
):
    # Fetch existing user
    user_db = session.get(User, user_id)
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    # Only update fields that are provided
    user_data = user.model_dump(exclude_unset=True)

    if "password_hash" in user_data:
        user_data["password_hash"] = hash_password(user_data["password_hash"])

    for field, value in user_data.items():
        setattr(user_db, field, value)

    # Commit changes
    session.add(user_db)
    session.commit()
    session.refresh(user_db)

    return user_db



@router.delete("/{user_id}", response_model=UserPublic)
def delete_user(
    user_id: str,
    session: Session = Depends(get_db)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Keep a copy to return
    deleted = UserPublic.model_validate(user)

    session.delete(user)
    session.commit()

    return deleted