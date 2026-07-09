from __future__ import annotations

import secrets
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore_store import (
    add_audit,
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from services.security import (
    decode_token,
    hash_password,
    mint_access_token,
    mint_refresh_token,
    verify_password,
)
from routers.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    GoogleAuthRequest,
)
from routers.helpers import _resolve_customer_id_for_user, _assert_same_user

router = APIRouter(tags=["Auth"])


@router.post("/auth/register")
async def auth_register(payload: RegisterRequest) -> dict:
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = create_user(str(uuid4()), payload.email, hash_password(payload.password), payload.company_name, payload.full_name)
    add_audit("auth_register", user["user_id"])
    return {"user_id": user["user_id"], "email": user["email"], "company_name": user["company_name"], "full_name": user.get("full_name", "")}


@router.post("/auth/login")
async def auth_login(payload: LoginRequest) -> dict:
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        tenant_id = _resolve_customer_id_for_user(user["user_id"])
    except Exception:
        tenant_id = user["user_id"]
    return {
        "user_id": user["user_id"],
        "access_token": mint_access_token(user["user_id"], user["email"], tenant_id=tenant_id, role="admin"),
        "refresh_token": mint_refresh_token(user["user_id"]),
    }


@router.post("/auth/refresh")
async def auth_refresh(payload: RefreshTokenRequest) -> dict:
    claims = decode_token(payload.refresh_token)
    if str(claims.get("type") or "").strip().lower() != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = str(claims.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token subject")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        tenant_id = _resolve_customer_id_for_user(user["user_id"])
    except Exception:
        tenant_id = user["user_id"]

    return {
        "user_id": user["user_id"],
        "access_token": mint_access_token(user["user_id"], user["email"], tenant_id=tenant_id, role="admin"),
        "refresh_token": payload.refresh_token,
    }


# ── Frontend compatibility endpoints ──

@router.post("/api/auth/register")
async def api_auth_register(payload: RegisterRequest) -> dict:
    return await auth_register(payload)


@router.get("/api/auth/profile/{user_id}")
async def api_auth_profile(user_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    """Return registration-time profile data so onboarding can auto-populate fields."""
    _assert_same_user(user, user_id)
    db_user = get_user_by_id(user_id)
    if not db_user:
        return {
            "user_id": user_id,
            "email": str(user.get("email") or ""),
            "full_name": str(user.get("name") or ""),
            "company_name": "",
        }
    return {
        "user_id": db_user["user_id"],
        "email": db_user["email"],
        "full_name": db_user.get("full_name", ""),
        "company_name": db_user.get("company_name", ""),
    }


@router.post("/api/auth/login")
async def api_auth_login(payload: LoginRequest) -> dict:
    return await auth_login(payload)


@router.post("/api/auth/refresh")
async def api_auth_refresh(payload: RefreshTokenRequest) -> dict:
    return await auth_refresh(payload)


@router.post("/auth/google")
async def auth_google(payload: GoogleAuthRequest) -> dict:
    email = payload.email or f"google_user_{secrets.token_hex(4)}@example.com"
    user = get_user_by_email(email) or create_user(str(uuid4()), email, hash_password(payload.id_token), "Google User")
    try:
        tenant_id = _resolve_customer_id_for_user(user["user_id"])
    except Exception:
        tenant_id = user["user_id"]
    return {
        "user_id": user["user_id"],
        "access_token": mint_access_token(user["user_id"], user["email"], tenant_id=tenant_id, role="admin"),
        "provider": "google",
    }
