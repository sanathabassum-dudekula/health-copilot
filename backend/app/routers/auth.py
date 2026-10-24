import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..models import AuthSession
from ..auth import token_digest

from ..auth import (
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    get_session_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from ..db import get_db
from ..models import Profile, User, Visit

router = APIRouter(prefix="/auth", tags=["authentication"])


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="My Profile", min_length=1, max_length=100)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.profile.name if user.profile else "",
        "preferred_language": user.preferred_language,
    }


@router.post("/register")
def register(
    body: RegisterBody,
    request: Request,
    response: Response,
    x_visit: str | None = Header(default=None, min_length=32, max_length=64),
    db: Session = Depends(get_db),
):
    email = str(body.email).strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = db.get(Visit, x_visit).user if x_visit and db.get(Visit, x_visit) else None

    if user and user.email:
        raise HTTPException(status_code=409, detail="This guest session is already linked to an account.")

    if user is None:
        user = User()
        db.add(user)

    # Every registered account must have its own profile.
    # This also repairs guest accounts that do not yet have one.
    if user.profile is None:
        user.profile = Profile(name=body.name.strip() or "My Profile")
    elif not user.profile.name or user.profile.name == "Guest":
        user.profile.name = body.name.strip() or "My Profile"

    user.email = email
    user.password_hash = hash_password(body.password)

    try:
        db.commit()
        db.refresh(user)
        token = create_session(user, db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email may already exist.")

    set_session_cookie(response, request, token)
    return {"user": public_user(user)}


@router.post("/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(body.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_session(user, db)
    set_session_cookie(response, request, token)
    return {"user": public_user(user)}


@router.get("/me")
def me(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_session_user(request.cookies.get(SESSION_COOKIE), db)
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return {"user": public_user(user)}



@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
):
    token = request.cookies.get(SESSION_COOKIE)

    if token:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_digest(token)
            )
        )

        if session:
            db.delete(session)
            db.commit()

    response = JSONResponse(
        content={"message": "Logged out successfully"}
    )
    clear_session_cookie(response)
    return response