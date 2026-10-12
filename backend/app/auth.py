import hashlib
import hmac
import secrets
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import AuthSession, Profile, User, Visit

SESSION_COOKIE = "curamind_session"
SESSION_TTL = timedelta(days=30)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algorithm, salt_hex, hash_hex = stored.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 310_000
        ).hex()
        return hmac.compare_digest(actual, hash_hex)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_session_user(token: str | None, db: Session) -> User | None:
    if not token or len(token) > 200:
        return None
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(token))
    )
    if not session:
        return None
    if session.expires_at <= datetime.utcnow():
        db.delete(session)
        db.commit()
        return None
    return db.get(User, session.user_id)


def create_session(user: User, db: Session) -> str:
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(
            token_hash=token_digest(token),
            user_id=user.id,
            expires_at=datetime.utcnow() + SESSION_TTL,
        )
    )
    db.commit()
    return token


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    secure = request.url.scheme == "https" or forwarded_proto == "https"
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE, httponly=True, samesite="lax", path="/"
    )


def delete_profile_data(db: Session, p: Profile):
    for document in p.documents:
        shutil.rmtree(Path(settings.STORAGE_DIR) / str(document.id), ignore_errors=True)
    db.delete(p.user)
    db.commit()


def current_profile(
    request: Request,
    x_visit: str | None = Header(default=None, min_length=32, max_length=64),
    db: Session = Depends(get_db),
) -> Profile:
    # An authenticated account takes priority over the browser's guest identity.
    account_user = get_session_user(request.cookies.get(SESSION_COOKIE), db)
    if account_user and account_user.profile:
        return account_user.profile

    # Keep the existing guest flow working for visitors who have not logged in.
    if not x_visit:
        raise HTTPException(status_code=401, detail="Please sign in or start a guest session.")

    if visit := db.get(Visit, x_visit):
        if visit.user.profile:
            return visit.user.profile

    user = User()
    user.profile = Profile(name="Guest")
    user.visit = Visit(token=x_visit)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        visit = db.get(Visit, x_visit)
        if visit and visit.user.profile:
            return visit.user.profile
        raise HTTPException(status_code=409, detail="Could not create guest profile.")
    return user.profile
