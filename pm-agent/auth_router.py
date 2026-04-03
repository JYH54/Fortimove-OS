"""
인증 API 라우터
- POST /auth/register: 회원가입 (첫 사용자는 admin + 새 조직 생성)
- POST /auth/login: 로그인 → access + refresh token
- POST /auth/refresh: access token 갱신
- GET  /auth/me: 현재 사용자 정보
- GET  /auth/org/users: 같은 조직 사용자 목록 (admin only)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from auth import (
    AuthDB, get_auth_db, get_current_user, require_admin,
    create_access_token, create_refresh_token, decode_token,
    TokenPayload, UserCreate, UserResponse, TokenResponse,
    Role, ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class InviteRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str = Role.OPERATOR


@router.post("/register", response_model=TokenResponse)
def register(req: UserCreate, db: AuthDB = Depends(get_auth_db)):
    """
    회원가입.
    - org_name이 제공되면 새 조직을 생성하고 admin으로 등록.
    - org_name이 없으면 기본 조직(default)에 viewer로 등록.
    """
    org_name = req.org_name or "Default Organization"
    org_id = db.create_organization(org_name, plan="free")
    role = Role.ADMIN  # 조직 생성자는 항상 admin

    user = db.create_user(
        email=req.email,
        password=req.password,
        name=req.name,
        role=role,
        org_id=org_id
    )

    access = create_access_token(user["user_id"], org_id, role)
    refresh = create_refresh_token(user["user_id"], org_id, role)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            name=user["name"],
            role=role,
            org_id=org_id,
            org_name=org_name,
            created_at=""
        )
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: AuthDB = Depends(get_auth_db)):
    """로그인 → JWT 토큰 발급"""
    user = db.authenticate(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access = create_access_token(user["user_id"], user["org_id"], user["role"])
    refresh = create_refresh_token(user["user_id"], user["org_id"], user["role"])

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            org_id=user["org_id"],
            org_name=user.get("org_name", ""),
            created_at=user.get("created_at", "")
        )
    )


@router.post("/refresh", response_model=dict)
def refresh_token(req: RefreshRequest):
    """Refresh token으로 새 access token 발급"""
    payload = decode_token(req.refresh_token)
    if payload.type != "refresh":
        raise HTTPException(status_code=400, detail="Invalid token type")

    access = create_access_token(payload.sub, payload.org_id, payload.role)
    return {
        "access_token": access,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.get("/me", response_model=UserResponse)
def get_me(
    user: TokenPayload = Depends(get_current_user),
    db: AuthDB = Depends(get_auth_db)
):
    """현재 인증된 사용자 정보"""
    user_data = db.get_user(user.sub)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        user_id=user_data["user_id"],
        email=user_data["email"],
        name=user_data["name"],
        role=user_data["role"],
        org_id=user_data["org_id"],
        org_name=user_data.get("org_name", ""),
        created_at=user_data.get("created_at", "")
    )


@router.get("/org/users")
def list_org_users(
    user: TokenPayload = Depends(require_admin),
    db: AuthDB = Depends(get_auth_db)
):
    """같은 조직의 사용자 목록 (admin only)"""
    return db.get_org_users(user.org_id)


@router.post("/org/invite")
def invite_user(
    req: InviteRequest,
    user: TokenPayload = Depends(require_admin),
    db: AuthDB = Depends(get_auth_db)
):
    """조직에 새 사용자 초대 (admin only)"""
    new_user = db.create_user(
        email=req.email,
        password=req.password,
        name=req.name,
        role=req.role,
        org_id=user.org_id
    )
    return {"message": f"User {req.email} invited as {req.role}", "user_id": new_user["user_id"]}
