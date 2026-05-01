from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

import database as db


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{hashed.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    salt, hashed = stored.split(":")
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return check.hex() == hashed


async def register_user(username: str, password: str, nickname: str = "") -> dict:
    existing = await db.fetch_user_by_username(username)
    if existing:
        return {"error": "用户名已存在"}

    user_id = str(uuid.uuid4())
    password_hash = _hash_password(password)
    nickname = nickname or username

    await db.insert_user_with_auth(user_id, username, password_hash, nickname)

    return {
        "user_id": user_id,
        "username": username,
        "nickname": nickname,
    }


async def login_user(username: str, password: str) -> dict | None:
    user = await db.fetch_user_by_username(username)
    if not user:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None

    token = secrets.token_urlsafe(32)
    await db.update_user_token(user["id"], token)

    return {
        "user_id": user["id"],
        "username": user["username"],
        "nickname": user["nickname"],
        "token": token,
        "coins": user["coins"],
    }


async def verify_token(token: str) -> dict | None:
    user = await db.fetch_user_by_token(token)
    if not user:
        return None
    await db.update_last_active(user["id"])
    return user
