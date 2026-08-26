"""
Authentication endpoints (Phase 3 — bcrypt + JWT access/refresh).

POST /auth/login    {username, password} -> {access_token, refresh_token, user}
POST /auth/refresh  {refresh_token}      -> new access token
GET  /auth/me       (bearer)             -> current user profile + scope

Four seeded demo users (see README):
  officer.statea / PoliceStateA!1   POLICE_STATE    (State-A)
  officer.district1 / District1!1   POLICE_DISTRICT (Northsagar)
  bank.hdfc / HdfcBank!1            BANK            (HDFC Bank)
  i4c.admin / I4cAdmin!1            I4C_ADMIN       (national)

Production: replace with OAuth2.0/OIDC + org SSO (integration point marked).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ... import repositories as repo
from ...database import get_db
from ...security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    require_auth,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    user_id: str
    username: str
    role: str
    scope: str
    display_name: str


class LoginOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = repo.get_user_by_username(db, payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return LoginOut(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        user=UserOut(user_id=user.user_id, username=user.username, role=user.role,
                     scope=user.scope, display_name=user.display_name),
    )


@router.post("/refresh")
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    claims = decode_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    user = repo.get_user_by_id(db, claims.get("sub", ""))
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return {"access_token": create_access_token(user), "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(user=Depends(require_auth())):
    return UserOut(user_id=user.user_id, username=user.username, role=user.role,
                   scope=user.scope, display_name=user.display_name)