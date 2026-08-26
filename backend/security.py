"""
Authentication & RBAC (Phase 3 — "secure" Law Enforcement Interface).

* bcrypt password hashing (passlib) against the `users` table.
* JWT access tokens (short TTL) + refresh tokens (long TTL) via python-jose.
* Roles: POLICE_STATE / POLICE_DISTRICT / BANK / I4C_ADMIN, each with a SCOPE
  (state | district | bank_name | national). Row-level scoping is enforced in
  the repository layer (never in the frontend).
* Every protected access is recorded to the tamper-evident ledger
  (event_type="access") — immutable audit trail.

PRODUCTION NOTE: replace with OAuth2.0/OIDC + organisational SSO (NIC/MHA
identity federation). The dependency-based structure maps 1:1, so routes do
not change.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

# bcrypt used directly (passlib 1.7.4 is incompatible with bcrypt>=4.1 on Python 3.12)
import bcrypt

from . import repositories as repo
from .config import JWT_ALGORITHM, JWT_REFRESH_TTL_HOURS, JWT_SECRET, JWT_TTL_MINUTES
from .database import get_db

ROLES = ("POLICE_STATE", "POLICE_DISTRICT", "BANK", "I4C_ADMIN")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user) -> str:
    claims = {
        "sub": user.user_id,
        "role": user.role,
        "scope": user.scope,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_TTL_MINUTES),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user) -> str:
    claims = {
        "sub": user.user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_REFRESH_TTL_HOURS),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid or expired token: {exc}")


def require_auth(*roles: str):
    """
    FastAPI dependency: authenticated user whose role is in `roles`.
    Every access is appended to the tamper-evident ledger (chain-of-custody).
    Usage: user = Depends(require_auth("POLICE_DISTRICT", "POLICE_STATE"))
    """

    def dependency(
        request: Request,
        authorization: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        claims = decode_token(authorization.split(" ", 1)[1].strip())
        if claims.get("type") != "access":
            raise HTTPException(status_code=401, detail="Not an access token")
        user = repo.get_user_by_id(db, claims.get("sub", ""))
        if user is None:
            raise HTTPException(status_code=401, detail="Unknown user")
        if roles and user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Role '{user.role}' not allowed here")
        # immutable access audit -> tamper-evident ledger
        repo.append_ledger(db, actor=f"{user.user_id} ({user.role})", event_type="access",
                           entity_id=request.url.path)
        return user

    return dependency