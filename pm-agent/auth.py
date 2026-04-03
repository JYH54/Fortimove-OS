"""
Fortimove 인증/인가 모듈
- JWT 기반 access/refresh token
- 사용자 + 조직(tenant) 모델
- RBAC (admin / operator / viewer)
"""

import os
import hashlib
import secrets
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from enum import Enum

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================

JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", secrets.token_hex(32)))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
AUTH_DB_PATH = os.getenv("AUTH_DB_PATH", "data/auth.db")

# Lazy import to avoid hard dependency
try:
    import jwt as pyjwt
except ImportError:
    pyjwt = None


def _ensure_pyjwt():
    if pyjwt is None:
        raise RuntimeError("PyJWT is required. Install with: pip install PyJWT")


# ============================================================
# Enums & Schemas
# ============================================================

class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class TokenPayload(BaseModel):
    sub: str               # user_id
    org_id: str            # tenant/organization id
    role: str              # admin/operator/viewer
    exp: float             # expiration timestamp
    type: str = "access"   # access or refresh


class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str = Role.VIEWER
    org_name: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    org_id: str
    org_name: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


# ============================================================
# Password Hashing (PBKDF2 - no external dependency)
# ============================================================

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{hashed.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt, expected_hash = stored_hash.split(":")
    actual_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return actual_hash.hex() == expected_hash


# ============================================================
# JWT Token Management
# ============================================================

def create_access_token(user_id: str, org_id: str, role: str) -> str:
    _ensure_pyjwt()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "exp": expire.timestamp(),
        "type": "access"
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, org_id: str, role: str) -> str:
    _ensure_pyjwt()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "exp": expire.timestamp(),
        "type": "refresh"
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    _ensure_pyjwt()
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenPayload(**payload)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


# ============================================================
# Auth Database (SQLite for auth, will migrate to PostgreSQL in Phase 1-4)
# ============================================================

class AuthDB:
    def __init__(self, db_path: str = AUTH_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS organizations (
                    org_id TEXT PRIMARY KEY,
                    org_name TEXT NOT NULL,
                    plan TEXT DEFAULT 'free',
                    api_quota_monthly INTEGER DEFAULT 1000,
                    api_usage_current INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    org_id TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    last_login TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id)
                );

                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    token_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);
                CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
            """)

    def create_organization(self, org_name: str, plan: str = "free") -> str:
        org_id = secrets.token_hex(8)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO organizations (org_id, org_name, plan) VALUES (?, ?, ?)",
                (org_id, org_name, plan)
            )
        return org_id

    def create_user(self, email: str, password: str, name: str, role: str, org_id: str) -> Dict[str, Any]:
        user_id = secrets.token_hex(8)
        password_hash = hash_password(password)

        with self._get_conn() as conn:
            # Check email uniqueness
            existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Email already registered")

            conn.execute(
                "INSERT INTO users (user_id, email, name, password_hash, role, org_id) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, email, name, password_hash, role, org_id)
            )

        return {"user_id": user_id, "email": email, "name": name, "role": role, "org_id": org_id}

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT u.*, o.org_name FROM users u
                   JOIN organizations o ON u.org_id = o.org_id
                   WHERE u.email = ? AND u.is_active = 1""",
                (email,)
            ).fetchone()

        if not row or not verify_password(password, row["password_hash"]):
            return None

        # Update last_login
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET last_login = datetime('now') WHERE user_id = ?",
                (row["user_id"],)
            )

        return dict(row)

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT u.*, o.org_name FROM users u
                   JOIN organizations o ON u.org_id = o.org_id
                   WHERE u.user_id = ? AND u.is_active = 1""",
                (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_org_users(self, org_id: str) -> list:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT user_id, email, name, role, created_at FROM users WHERE org_id = ? AND is_active = 1",
                (org_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def increment_api_usage(self, org_id: str) -> bool:
        """Increment API usage. Returns False if quota exceeded."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT api_quota_monthly, api_usage_current FROM organizations WHERE org_id = ?",
                (org_id,)
            ).fetchone()
            if not row:
                return False
            if row["api_usage_current"] >= row["api_quota_monthly"]:
                return False
            conn.execute(
                "UPDATE organizations SET api_usage_current = api_usage_current + 1, updated_at = datetime('now') WHERE org_id = ?",
                (org_id,)
            )
        return True


# ============================================================
# FastAPI Dependencies
# ============================================================

security = HTTPBearer(auto_error=False)
_auth_db: Optional[AuthDB] = None


def get_auth_db() -> AuthDB:
    global _auth_db
    if _auth_db is None:
        _auth_db = AuthDB()
    return _auth_db


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TokenPayload:
    """Extract and validate JWT token from request."""
    # Legacy support: allow ADMIN_TOKEN for backward compatibility
    if credentials is None:
        admin_token = os.getenv("ADMIN_TOKEN")
        allow_noauth = os.getenv("ALLOW_LOCAL_NOAUTH") == "true"
        if allow_noauth:
            return TokenPayload(
                sub="local-admin",
                org_id="local",
                role=Role.ADMIN,
                exp=(datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
                type="access"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    # Legacy: check if it's the old ADMIN_TOKEN
    admin_token = os.getenv("ADMIN_TOKEN")
    if admin_token and token == admin_token:
        return TokenPayload(
            sub="legacy-admin",
            org_id="default",
            role=Role.ADMIN,
            exp=(datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
            type="access"
        )

    return decode_token(token)


def require_role(*roles: Role):
    """Dependency factory for role-based access control."""
    def check_role(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if user.role not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {[r.value for r in roles]}"
            )
        return user
    return check_role


def require_admin(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_operator_or_admin(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if user.role not in [Role.ADMIN, Role.OPERATOR]:
        raise HTTPException(status_code=403, detail="Operator or Admin access required")
    return user
