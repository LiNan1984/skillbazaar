"""
API Key Management Service — 开发者API密钥管理
用户可申请API Key，外部通过OpenAI兼容协议调用其Agent
"""
from __future__ import annotations

import os
import time
import uuid
import secrets
import aiosqlite

DB_PATH = os.environ.get("SKBZ_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "skillbazaar.db"))


async def _get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def _ensure_tables(db: aiosqlite.Connection) -> None:
    """Create api_keys and cli_download_tokens tables if missing."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            api_key TEXT NOT NULL UNIQUE,
            name TEXT DEFAULT 'default',
            permissions TEXT DEFAULT 'chat,execute',
            rate_limit INTEGER DEFAULT 100,
            usage_count INTEGER DEFAULT 0,
            last_used_at REAL,
            is_active INTEGER DEFAULT 1,
            created_at REAL NOT NULL
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS cli_download_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        )
        """
    )
    await db.commit()


def generate_api_key() -> str:
    """Generate sk-xxx format API key"""
    return f"sk-{secrets.token_urlsafe(32)}"


async def create_api_key(user_id: str, name: str = "default", permissions: str = "chat,execute", rate_limit: int = 100) -> dict:
    """为用户创建API Key"""
    api_key = generate_api_key()
    db = await _get_db()
    try:
        await _ensure_tables(db)
        # Limit 5 keys per user
        cursor = await db.execute("SELECT count(*) as cnt FROM api_keys WHERE user_id=? AND is_active=1", (user_id,))
        row = await cursor.fetchone()
        if row["cnt"] >= 5:
            return {"error": "最多创建5个API Key"}

        await db.execute(
            """INSERT INTO api_keys (user_id, api_key, name, permissions, created_at, rate_limit)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, api_key, name, permissions, time.time(), rate_limit)
        )
        await db.commit()
        return {
            "api_key": api_key,
            "name": name,
            "permissions": permissions,
            "rate_limit": rate_limit,
            "message": "🔑 API Key创建成功！请妥善保管，创建后仅显示一次"
        }
    finally:
        await db.close()


async def list_api_keys(user_id: str) -> list:
    """列出用户的所有API Key（脱敏显示）"""
    db = await _get_db()
    try:
        await _ensure_tables(db)
        cursor = await db.execute(
            "SELECT id, api_key, name, permissions, created_at, last_used_at, usage_count, rate_limit, is_active FROM api_keys WHERE user_id=? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Mask the key: sk-xxxx...xxxx (show first 6 and last 4)
            key = d["api_key"]
            if len(key) > 10:
                d["api_key_masked"] = f"{key[:6]}...{key[-4:]}"
            else:
                d["api_key_masked"] = key[:4] + "****"
            del d["api_key"]  # Never return full key in list
            result.append(d)
        return result
    finally:
        await db.close()


async def revoke_api_key(user_id: str, key_id: int) -> dict:
    """撤销API Key"""
    db = await _get_db()
    try:
        await _ensure_tables(db)
        await db.execute(
            "UPDATE api_keys SET is_active=0 WHERE id=? AND user_id=?",
            (key_id, user_id)
        )
        await db.commit()
        return {"message": "🔑 API Key已撤销"}
    finally:
        await db.close()


async def verify_api_key(api_key: str) -> dict | None:
    """验证API Key，返回用户信息+权限（用于OpenAI兼容接口鉴权）"""
    db = await _get_db()
    try:
        await _ensure_tables(db)
        cursor = await db.execute(
            "SELECT * FROM api_keys WHERE api_key=? AND is_active=1",
            (api_key,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        
        # Update usage stats
        await db.execute(
            "UPDATE api_keys SET usage_count=usage_count+1, last_used_at=? WHERE id=?",
            (time.time(), row["id"])
        )
        await db.commit()
        
        return {
            "user_id": row["user_id"],
            "permissions": row["permissions"].split(",") if row["permissions"] else [],
            "rate_limit": row["rate_limit"],
            "key_id": row["id"]
        }
    finally:
        await db.close()


async def generate_cli_download_token(user_id: str) -> dict:
    """生成CLI下载认证token"""
    token = str(uuid.uuid4())
    db = await _get_db()
    try:
        await _ensure_tables(db)
        await db.execute(
            "INSERT INTO cli_download_tokens (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, time.time())
        )
        await db.commit()
        return {
            "download_url": f"/api/sandbox/cli-download/{token}",
            "token": token,
            "message": "🦐 skbz CLI下载链接已生成（10分钟有效）"
        }
    finally:
        await db.close()


async def verify_cli_token(token: str) -> str | None:
    """验证CLI下载token，返回user_id"""
    db = await _get_db()
    try:
        await _ensure_tables(db)
        cursor = await db.execute(
            "SELECT * FROM cli_download_tokens WHERE token=? AND used=0",
            (token,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        # Check 10 min expiry
        if time.time() - row["created_at"] > 600:
            return None
        # Mark used
        await db.execute("UPDATE cli_download_tokens SET used=1 WHERE token=?", (token,))
        await db.commit()
        return row["user_id"]
    finally:
        await db.close()
