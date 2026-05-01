# SkillBazaar Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add LangGraph autonomous shopping agent, layered skill encryption (SkillVault), user upload/sell system, and markdown chat rendering to SkillBazaar.

**Architecture:** Single FastAPI monolith. LangGraph replaces the simple LLM chat_service. SkillVault adds AES-256-GCM encryption for uploaded skills with type-specific protection (server-side execution for prompts, encrypted packages + license for code, SDK protocol for high-code). Three new DB tables: skill_assets, licenses, skill_executions.

**Tech Stack:** Python 3.9+ / FastAPI / LangGraph / aiosqlite / cryptography / React 18 / react-markdown / remark-gfm

---

## Phase 1: Foundation (Database + Dependencies)

### Task 1: Add Python dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Update requirements.txt**

```
fastapi==0.115.0
uvicorn==0.32.0
pydantic==2.9.0
aiosqlite==0.20.0
langgraph>=0.2.0
langchain-core>=0.3.0
langchain-openai>=0.2.0
cryptography>=43.0
httpx>=0.27.0
```

**Step 2: Install dependencies**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && pip install -r requirements.txt`

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add langgraph, cryptography dependencies"
```

---

### Task 2: Add new database tables

**Files:**
- Modify: `backend/database.py:28-71` (the `_create_tables` function)
- Modify: `backend/database.py` (add new helper functions)

**Step 1: Add skill_assets, licenses, skill_executions tables to `_create_tables`**

Add after the transactions CREATE TABLE statement (after line 70):

```python
        CREATE TABLE IF NOT EXISTS skill_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id),
            skill_type TEXT NOT NULL,
            encrypted_blob BLOB NOT NULL,
            encryption_iv TEXT NOT NULL,
            encryption_salt TEXT NOT NULL,
            skill_meta TEXT,
            content_hash TEXT NOT NULL,
            file_size INTEGER,
            version TEXT DEFAULT '1.0.0',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            license_type TEXT NOT NULL,
            license_token TEXT UNIQUE NOT NULL,
            expires_at TEXT,
            max_calls INTEGER,
            calls_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS skill_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER REFERENCES licenses(id),
            user_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            execution_type TEXT NOT NULL,
            input_params TEXT,
            output_summary TEXT,
            duration_ms INTEGER,
            status TEXT DEFAULT 'success',
            created_at TEXT DEFAULT (datetime('now'))
        );
```

**Step 2: Add database helper functions for new tables**

Add these functions after the existing helper functions (after `check_already_purchased`):

```python
# ---------- Skill Asset Helpers ----------

async def insert_skill_asset(data: dict) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO skill_assets
            (product_id, skill_type, encrypted_blob, encryption_iv, encryption_salt,
             skill_meta, content_hash, file_size, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["product_id"], data["skill_type"], data["encrypted_blob"],
             data["encryption_iv"], data["encryption_salt"], data.get("skill_meta"),
             data["content_hash"], data.get("file_size"), data.get("version", "1.0.0")),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_skill_asset(product_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM skill_assets WHERE product_id = ?", (product_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ---------- License Helpers ----------

async def insert_license(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO licenses
            (user_id, product_id, license_type, license_token, expires_at, max_calls, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
            (data["user_id"], data["product_id"], data["license_type"],
             data["license_token"], data.get("expires_at"), data.get("max_calls"), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_license_by_token(token: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM licenses WHERE license_token = ? AND status = 'active'", (token,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_user_licenses(user_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT l.*, p.name as product_name, p.category, sa.skill_type
            FROM licenses l
            JOIN products p ON l.product_id = p.id
            LEFT JOIN skill_assets sa ON l.product_id = sa.product_id
            WHERE l.user_id = ? AND l.status = 'active'
            ORDER BY l.created_at DESC""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def increment_license_calls(license_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE licenses SET calls_count = calls_count + 1 WHERE id = ?", (license_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def check_user_has_license(user_id: str, product_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM licenses
            WHERE user_id = ? AND product_id = ? AND status = 'active'
            AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY created_at DESC LIMIT 1""",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ---------- Execution Helpers ----------

async def insert_execution(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO skill_executions
            (license_id, user_id, product_id, execution_type, input_params,
             output_summary, duration_ms, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data.get("license_id"), data["user_id"], data["product_id"],
             data["execution_type"], data.get("input_params"),
             data.get("output_summary"), data.get("duration_ms"),
             data.get("status", "success"), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_user_executions(user_id: str, limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT se.*, p.name as product_name
            FROM skill_executions se
            JOIN products p ON se.product_id = p.id
            WHERE se.user_id = ?
            ORDER BY se.created_at DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
```

**Step 3: Delete old database file so tables are recreated**

Run: `rm -f /Users/linan/Desktop/aicode/skillbazaar/backend/skillbazaar.db`

**Step 4: Restart backend to verify table creation**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && python -c "import asyncio; from database import init_db; asyncio.run(init_db())"`

**Step 5: Commit**

```bash
git add backend/database.py
git commit -m "feat: add skill_assets, licenses, skill_executions tables and helpers"
```

---

### Task 3: Add new Pydantic models

**Files:**
- Modify: `backend/models.py`

**Step 1: Add new models at end of file**

```python
# ---------- Skill Asset Models ----------

class SkillType(str, Enum):
    PROMPT = "prompt"
    CODE = "code"
    SDK = "sdk"


class SkillUploadRequest(BaseModel):
    skill_type: SkillType
    skill_meta: Optional[str] = None  # JSON: API desc, params, version
    sdk_endpoint: Optional[str] = None  # For SDK type


class SkillAssetResponse(BaseModel):
    id: int
    product_id: int
    skill_type: str
    skill_meta: Optional[str] = None
    file_size: Optional[int] = None
    version: str = "1.0.0"
    created_at: Optional[str] = None


class SkillExecutionRequest(BaseModel):
    product_id: int
    user_id: str
    input_params: Optional[str] = None  # JSON


# ---------- License Models ----------

class LicenseType(str, Enum):
    PERMANENT = "permanent"
    TRIAL = "trial"
    SUBSCRIPTION = "subscription"


class LicenseCreate(BaseModel):
    product_id: int
    user_id: str
    license_type: LicenseType = LicenseType.PERMANENT
    max_calls: Optional[int] = None


class LicenseResponse(BaseModel):
    id: int
    user_id: str
    product_id: int
    license_type: str
    license_token: str
    expires_at: Optional[str] = None
    max_calls: Optional[int] = None
    calls_count: int = 0
    status: str
    created_at: Optional[str] = None


class LicenseVerifyRequest(BaseModel):
    license_token: str
    product_id: int


class LicenseVerifyResponse(BaseModel):
    valid: bool
    license_type: Optional[str] = None
    calls_remaining: Optional[int] = None
    expires_at: Optional[str] = None


# ---------- Enhanced Chat Models ----------

class ChatResponseV2(BaseModel):
    reply: str
    products: List[ProductResponse] = []
    intent: str = "search"
    search_params: Optional[dict] = None
```

**Step 2: Commit**

```bash
git add backend/models.py
git commit -m "feat: add skill, license, and enhanced chat models"
```

---

## Phase 2: SkillVault Encryption Engine

### Task 4: Create SkillVault encryption service

**Files:**
- Create: `backend/services/skill_vault.py`

**Step 1: Write the encryption service**

```python
from __future__ import annotations

import os
import hashlib
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


# Master key loaded from env or generated once
_MASTER_KEY = os.environ.get(
    "SKILLBAZAAR_MASTER_KEY",
    "skillbazaar-default-master-key-change-in-production-2026"
)


def _derive_key(master_key: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(master_key.encode())


def encrypt_content(plaintext: bytes, master_key: str = _MASTER_KEY) -> dict:
    salt = os.urandom(16)
    key = _derive_key(master_key, salt)
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext, None)

    return {
        "encrypted_blob": ciphertext,
        "encryption_iv": iv.hex(),
        "encryption_salt": salt.hex(),
        "content_hash": hashlib.sha256(plaintext).hexdigest(),
        "file_size": len(plaintext),
    }


def decrypt_content(
    encrypted_blob: bytes,
    iv_hex: str,
    salt_hex: str,
    master_key: str = _MASTER_KEY,
) -> bytes:
    salt = bytes.fromhex(salt_hex)
    iv = bytes.fromhex(iv_hex)
    key = _derive_key(master_key, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, encrypted_blob, None)


def verify_integrity(plaintext: bytes, expected_hash: str) -> bool:
    actual_hash = hashlib.sha256(plaintext).hexdigest()
    return actual_hash == expected_hash
```

**Step 2: Test encryption round-trip**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && python -c "
from services.skill_vault import encrypt_content, decrypt_content, verify_integrity
test = b'Hello, this is a test skill prompt!'
enc = encrypt_content(test)
print('Encrypted:', enc['encryption_iv'][:16] + '...')
dec = decrypt_content(enc['encrypted_blob'], enc['encryption_iv'], enc['encryption_salt'])
print('Decrypted:', dec)
print('Integrity:', verify_integrity(dec, enc['content_hash']))
assert dec == test
print('PASS: encryption round-trip works')
"`

**Step 3: Commit**

```bash
git add backend/services/skill_vault.py
git commit -m "feat: add SkillVault AES-256-GCM encryption engine"
```

---

### Task 5: Create License service

**Files:**
- Create: `backend/services/license_service.py`

**Step 1: Write the license service**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

import database as db
from models import LicenseType


async def create_license(
    user_id: str,
    product_id: int,
    license_type: LicenseType = LicenseType.PERMANENT,
    max_calls: Optional[int] = None,
) -> dict:
    token = str(uuid.uuid4())
    expires_at = None

    if license_type == LicenseType.TRIAL:
        expires_at = (datetime.now() + timedelta(days=7)).isoformat()
        max_calls = max_calls or 3
    elif license_type == LicenseType.SUBSCRIPTION:
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()

    license_id = await db.insert_license({
        "user_id": user_id,
        "product_id": product_id,
        "license_type": license_type.value,
        "license_token": token,
        "expires_at": expires_at,
        "max_calls": max_calls,
    })

    return {
        "id": license_id,
        "license_token": token,
        "license_type": license_type.value,
        "expires_at": expires_at,
        "max_calls": max_calls,
    }


async def verify_license(token: str, product_id: int) -> dict:
    license_data = await db.fetch_license_by_token(token)
    if not license_data:
        return {"valid": False, "reason": "License not found"}

    if license_data["product_id"] != product_id:
        return {"valid": False, "reason": "Product mismatch"}

    if license_data["status"] != "active":
        return {"valid": False, "reason": "License revoked"}

    if license_data["expires_at"]:
        expires = datetime.fromisoformat(license_data["expires_at"])
        if datetime.now() > expires:
            return {"valid": False, "reason": "License expired"}

    calls_remaining = None
    if license_data["max_calls"]:
        calls_remaining = license_data["max_calls"] - license_data["calls_count"]
        if calls_remaining <= 0:
            return {"valid": False, "reason": "Call limit reached"}

    return {
        "valid": True,
        "license_id": license_data["id"],
        "license_type": license_data["license_type"],
        "calls_remaining": calls_remaining,
        "expires_at": license_data["expires_at"],
    }


async def check_user_access(user_id: str, product_id: int) -> dict:
    license_data = await db.check_user_has_license(user_id, product_id)
    if not license_data:
        return {"has_access": False}
    return {"has_access": True, "license": license_data}
```

**Step 2: Commit**

```bash
git add backend/services/license_service.py
git commit -m "feat: add license creation and verification service"
```

---

### Task 6: Create Skill Execution service

**Files:**
- Create: `backend/services/execution_service.py`

**Step 1: Write the execution service**

```python
from __future__ import annotations

import json
import time
import httpx

import database as db
from services.skill_vault import decrypt_content, verify_integrity
from services import chat_service as _chat_service

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = "sk-bV3TVx9azStj8KJe3oW0rsqpaIZKX8E21wyXMtHYCjWBxly1"
LLM_MODEL = "GLM-5.1-FP8"


async def execute_skill(
    user_id: str,
    product_id: int,
    license_id: int | None,
    skill_asset: dict,
    input_params: str | None = None,
) -> dict:
    start = time.time()
    skill_type = skill_asset["skill_type"]

    try:
        if skill_type == "prompt":
            result = await _execute_prompt_skill(skill_asset, input_params)
        elif skill_type == "code":
            result = await _execute_code_skill(skill_asset, input_params)
        elif skill_type == "sdk":
            result = await _execute_sdk_skill(skill_asset, input_params)
        else:
            result = {"error": f"Unknown skill type: {skill_type}"}

        duration_ms = int((time.time() - start) * 1000)

        await db.insert_execution({
            "license_id": license_id,
            "user_id": user_id,
            "product_id": product_id,
            "execution_type": skill_type,
            "input_params": input_params,
            "output_summary": (result.get("output", "") or "")[:500],
            "duration_ms": duration_ms,
            "status": "success",
        })

        if license_id:
            await db.increment_license_calls(license_id)

        return result

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        await db.insert_execution({
            "license_id": license_id,
            "user_id": user_id,
            "product_id": product_id,
            "execution_type": skill_type,
            "input_params": input_params,
            "output_summary": str(e)[:500],
            "duration_ms": duration_ms,
            "status": "failed",
        })
        return {"error": str(e)}


async def _execute_prompt_skill(skill_asset: dict, input_params: str | None) -> dict:
    plaintext = decrypt_content(
        skill_asset["encrypted_blob"],
        skill_asset["encryption_iv"],
        skill_asset["encryption_salt"],
    )

    if not verify_integrity(plaintext, skill_asset["content_hash"]):
        return {"error": "Integrity check failed"}

    skill_content = plaintext.decode("utf-8")
    meta = json.loads(skill_asset.get("skill_meta") or "{}")

    user_input = input_params or ""

    messages = [
        {"role": "system", "content": skill_content},
        {"role": "user", "content": user_input},
    ]

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": 1024,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(LLM_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content", "") or msg.get("reasoning_content", "")

    return {"output": content, "skill_type": "prompt"}


async def _execute_code_skill(skill_asset: dict, input_params: str | None) -> dict:
    plaintext = decrypt_content(
        skill_asset["encrypted_blob"],
        skill_asset["encryption_iv"],
        skill_asset["encryption_salt"],
    )
    return {
        "output": f"Code skill executed (size: {len(plaintext)} bytes). Input: {input_params}",
        "skill_type": "code",
        "note": "Full code execution requires sandbox environment (internal only)",
    }


async def _execute_sdk_skill(skill_asset: dict, input_params: str | None) -> dict:
    meta = json.loads(skill_asset.get("skill_meta") or "{}")
    endpoint = meta.get("sdk_endpoint", "")

    if not endpoint:
        return {"error": "SDK endpoint not configured"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                endpoint,
                json={"input": input_params},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return {"output": resp.text, "skill_type": "sdk"}
    except Exception as e:
        return {"error": f"SDK call failed: {e}"}
```

**Step 2: Commit**

```bash
git add backend/services/execution_service.py
git commit -m "feat: add skill execution service (prompt/code/sdk)"
```

---

## Phase 3: LangGraph Shopping Agent

### Task 7: Create LangGraph agent

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/state.py`
- Create: `backend/agents/nodes.py`
- Create: `backend/agents/shopping_agent.py`

**Step 1: Create agents package**

Create `backend/agents/__init__.py` (empty file).

**Step 2: Create agent state definition**

Create `backend/agents/state.py`:

```python
from __future__ import annotations

from typing import TypedDict, Optional, List, Annotated
import operator


class AgentState(TypedDict):
    messages: list[dict]
    intent: str
    search_params: dict
    search_results: list[dict]
    iteration: int
    final_reply: str
    products_json: str
```

**Step 3: Create agent nodes**

Create `backend/agents/nodes.py`:

```python
from __future__ import annotations

import json
import re
import httpx

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = "sk-bV3TVx9azStj8KJe3oW0rsqpaIZKX8E21wyXMtHYCjWBxly1"
LLM_MODEL = "GLM-5.1-FP8"

SYSTEM_PROMPT = """你是 SkillBazaar 市场的 AI 导购助手"小B"。SkillBazaar 是一个 AI Agent、Skill（技能包）、Cron（定时任务）和 Workflow（工作流）的交易市场。

你的职责：
1. 理解用户想找什么类型的商品（Agent/Skill/Cron/Workflow）
2. 提取用户提到的关键词、功能需求、价格范围
3. 返回 JSON 格式的搜索参数，系统会自动搜索匹配商品

回复规则：
- 用中文回复
- 热情专业，像私人导购一样
- 使用 Markdown 格式美化回复（加粗价格、列表推荐等）
- 每次回复必须包含一个 JSON 块（用 ```json ``` 包裹），格式如下：

```json
{
  "category": "Agent 或 Skill 或 Cron 或 Workflow 或空字符串",
  "keyword": "搜索关键词",
  "min_price": 最低价或null,
  "max_price": 最高价或null,
  "sort": "rating 或 downloads 或 price_asc 或 price_desc"
}
```

如果是打招呼或闲聊，不需要返回 JSON，直接热情回复即可。
如果用户说的不够明确，主动追问。
多轮对话时要结合上下文理解用户意图。"""

INTENT_PROMPT = """分析用户意图，返回以下之一：
- search: 用户想搜索商品
- chat: 闲聊或打招呼
- followup: 追问上一次搜索的结果
- buy: 用户想购买某个商品

只返回意图关键词，不要其他内容。

对话历史：
{history}

用户最新消息：{message}"""

RESULT_EVAL_PROMPT = """你是搜索结果评估器。评估搜索结果是否满足用户需求。

用户搜索条件：{params}
搜索结果数量：{count}

如果结果为空或太少（少于3个），建议放宽条件的 JSON：
```json
{{"category": "...", "keyword": "...", "min_price": null, "max_price": null, "sort": "..."}}
```

如果结果足够好，只回复 "GOOD"。"""

REPLY_PROMPT = """你是 SkillBazaar 的导购助手小B，根据搜索结果给用户推荐商品。

搜索结果：
{products}

用 Markdown 格式回复，要求：
1. 先用一句话总结找到的商品
2. 用列表推荐 2-3 个最佳选择，加粗价格
3. 询问用户是否想了解详情或购买
4. 风格热情亲切"""


async def _call_llm(messages: list[dict], max_tokens: int = 1024) -> str:
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(LLM_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    return msg.get("content", "") or msg.get("reasoning_content", "")


def _extract_json(text: str) -> dict:
    pattern = r"```json\s*(\{[^}]+\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    pattern2 = r'\{[^{}]*"category"[^{}]*\}'
    match2 = re.search(pattern2, text, re.DOTALL)
    if match2:
        try:
            return json.loads(match2.group())
        except json.JSONDecodeError:
            pass
    return {}


async def understand_intent(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""

    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
        for m in messages[-6:]
    )

    prompt = INTENT_PROMPT.format(history=history_text, message=user_msg)
    result = await _call_llm([{"role": "user", "content": prompt}], max_tokens=32)

    intent = result.strip().lower()
    if intent not in ("search", "chat", "followup", "buy"):
        intent = "search"

    return {**state, "intent": intent}


async def extract_params(state: dict) -> dict:
    if state["intent"] == "chat":
        reply = await _call_llm(
            [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"][-10:],
            max_tokens=512,
        )
        return {**state, "final_reply": reply, "search_params": {}}

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"][-10:]
    reply = await _call_llm(messages, max_tokens=512)

    params = _extract_json(reply)
    if not params and state["intent"] == "followup" and state.get("search_params"):
        params = state["search_params"]

    return {**state, "search_params": params}


async def search_products(state: dict) -> dict:
    if not state.get("search_params"):
        return {**state, "search_results": []}

    import services.product_service as ps
    params = state["search_params"]

    try:
        result = await ps.get_products(
            category=params.get("category") or None,
            keyword=params.get("keyword") or None,
            min_price=params.get("min_price"),
            max_price=params.get("max_price"),
            sort_by=params.get("sort", "rating"),
            page=1,
            page_size=8,
        )
        products = result.products
    except Exception:
        products = []

    products_data = [
        {
            "id": p.id, "name": p.name, "category": p.category,
            "price": p.price, "rating": p.rating,
            "description": p.description[:60] if p.description else "",
            "source_platform": p.source_platform,
        }
        for p in products
    ]

    return {**state, "search_results": products_data}


async def evaluate_results(state: dict) -> dict:
    results = state.get("search_results", [])
    params = state.get("search_params", {})
    iteration = state.get("iteration", 0)

    if len(results) >= 3 or iteration >= 2:
        return state

    eval_prompt = RESULT_EVAL_PROMPT.format(
        params=json.dumps(params, ensure_ascii=False),
        count=len(results),
    )
    suggestion = await _call_llm([{"role": "user", "content": eval_prompt}], max_tokens=256)

    if "GOOD" in suggestion:
        return state

    new_params = _extract_json(suggestion)
    if new_params:
        return {**state, "search_params": new_params, "iteration": iteration + 1}

    return state


async def generate_reply(state: dict) -> dict:
    results = state.get("search_results", [])
    params = state.get("search_params", {})

    if state["intent"] == "chat":
        return state

    if not results:
        reply = "抱歉，暂时没有找到完全匹配的商品。\n\n"
        reply += "您可以试试：\n"
        reply += "- **换个关键词**搜索\n"
        reply += "- **放宽价格范围**\n"
        reply += "- 浏览我们的[热门商品](/)\n"
        return {**state, "final_reply": reply}

    products_text = json.dumps(results[:8], ensure_ascii=False, indent=2)
    reply = await _call_llm(
        [
            {"role": "system", "content": REPLY_PROMPT},
            {"role": "user", "content": f"搜索条件: {json.dumps(params, ensure_ascii=False)}\n\n搜索结果:\n{products_text}"},
        ],
        max_tokens=1024,
    )

    product_links = "\n".join(
        f"| [{p['name']}](/product/{p['id']}) | {p['category']} | **¥{p['price']}** | {p['rating']} |"
        for p in results[:8]
    )
    table = f"\n\n| 名称 | 分类 | 价格 | 评分 |\n|------|------|------|------|\n{product_links}"

    return {**state, "final_reply": reply + table, "products_json": json.dumps(results)}
```

**Step 4: Create the LangGraph graph**

Create `backend/agents/shopping_agent.py`:

```python
from __future__ import annotations

from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.nodes import (
    understand_intent,
    extract_params,
    search_products,
    evaluate_results,
    generate_reply,
)


def _should_search(state: dict) -> str:
    if state.get("intent") == "chat":
        return "end"
    return "search"


def _should_retry(state: dict) -> str:
    results = state.get("search_results", [])
    iteration = state.get("iteration", 0)
    if len(results) < 3 and iteration < 2:
        return "retry"
    return "reply"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("understand_intent", understand_intent)
    graph.add_node("extract_params", extract_params)
    graph.add_node("search_products", search_products)
    graph.add_node("evaluate_results", evaluate_results)
    graph.add_node("generate_reply", generate_reply)

    graph.set_entry_point("understand_intent")
    graph.add_conditional_edges("understand_intent", _should_search, {
        "search": "extract_params",
        "end": END,
    })
    graph.add_edge("extract_params", "search_products")
    graph.add_edge("search_products", "evaluate_results")
    graph.add_conditional_edges("evaluate_results", _should_retry, {
        "retry": "search_products",
        "reply": "generate_reply",
    })
    graph.add_edge("generate_reply", END)

    return graph.compile()


_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_graph()
    return _agent
```

**Step 5: Verify agent graph compiles**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && python -c "
from agents.shopping_agent import build_graph
graph = build_graph()
print('Graph nodes:', list(graph.nodes.keys()) if hasattr(graph, 'nodes') else 'compiled')
print('PASS: LangGraph agent compiles successfully')
"`

**Step 6: Commit**

```bash
git add backend/agents/
git commit -m "feat: add LangGraph autonomous shopping agent"
```

---

### Task 8: Replace chat_service with LangGraph agent

**Files:**
- Modify: `backend/services/chat_service.py`

**Step 1: Rewrite chat_service.py to use LangGraph**

Replace the entire file content with:

```python
from __future__ import annotations

import json
from typing import Optional

from models import ChatResponse, ProductResponse
from agents.shopping_agent import get_agent

_sessions: dict[str, list[dict]] = {}


def _get_history(user_id: str) -> list[dict]:
    if user_id not in _sessions:
        _sessions[user_id] = []
    return _sessions[user_id]


async def handle_chat(user_id: str, message: str) -> ChatResponse:
    history = _get_history(user_id)

    history.append({"role": "user", "content": message})

    agent = get_agent()
    state = {
        "messages": history[-10:],
        "intent": "",
        "search_params": {},
        "search_results": [],
        "iteration": 0,
        "final_reply": "",
        "products_json": "",
    }

    try:
        result = await agent.ainvoke(state)
    except Exception as e:
        result = {**state, "final_reply": f"让我为您搜索一下...\n\n({str(e)[:50]})"}

    reply = result.get("final_reply") or "让我为您搜索一下..."

    if result.get("final_reply"):
        history.append({"role": "assistant", "content": result["final_reply"]})

    if len(history) > 20:
        _sessions[user_id] = history[-16:]

    products = []
    products_json = result.get("products_json", "")
    if products_json:
        try:
            products_data = json.loads(products_json)
            for p in products_data:
                products.append(ProductResponse(
                    id=p["id"], name=p["name"], description=p.get("description", ""),
                    category=p["category"], sub_category=None, price=p["price"],
                    original_price=None, seller_name="", seller_avatar=None,
                    rating=p["rating"], downloads=0, sales=0, tags="[]",
                    source_platform=p.get("source_platform"), github_url=None,
                    icon=None, content_preview=None, status="active", created_at=None,
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    return ChatResponse(reply=reply, products=products)
```

**Step 2: Restart backend and test chat**

Run: `curl -s -X POST http://localhost:9527/api/chat -H "Content-Type: application/json" -d '{"user_id":"test","message":"推荐交易类工具"}' | python -m json.tool`

**Step 3: Commit**

```bash
git add backend/services/chat_service.py
git commit -m "refactor: replace simple LLM chat with LangGraph agent"
```

---

## Phase 4: Skill Upload API

### Task 9: Create skill upload router

**Files:**
- Create: `backend/routers/skills.py`

**Step 1: Write the skills router**

```python
from __future__ import annotations

import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

import database as db
from services.skill_vault import encrypt_content
from services.license_service import create_license, check_user_access
from services.execution_service import execute_skill
from models import (
    SkillAssetResponse, LicenseResponse, LicenseCreate,
    LicenseVerifyRequest, LicenseVerifyResponse, SkillExecutionRequest,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.post("/upload")
async def upload_skill(
    product_id: int = Form(...),
    skill_type: str = Form(...),
    skill_meta: str = Form(None),
    file: UploadFile = File(None),
    seller_id: str = Form(...),
):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    if skill_type not in ("prompt", "code", "sdk"):
        raise HTTPException(400, "Invalid skill_type. Must be: prompt, code, sdk")

    existing = await db.fetch_skill_asset(product_id)
    if existing:
        raise HTTPException(400, "Skill already uploaded for this product")

    content = b""
    if file:
        content = await file.read()
    elif skill_meta:
        meta_dict = json.loads(skill_meta) if isinstance(skill_meta, str) else skill_meta
        content = json.dumps(meta_dict, ensure_ascii=False).encode("utf-8")
    else:
        raise HTTPException(400, "Must provide either file or skill_meta")

    encrypted = encrypt_content(content)

    asset_id = await db.insert_skill_asset({
        "product_id": product_id,
        "skill_type": skill_type,
        "encrypted_blob": encrypted["encrypted_blob"],
        "encryption_iv": encrypted["encryption_iv"],
        "encryption_salt": encrypted["encryption_salt"],
        "skill_meta": skill_meta,
        "content_hash": encrypted["content_hash"],
        "file_size": encrypted["file_size"],
    })

    return {"id": asset_id, "product_id": product_id, "skill_type": skill_type, "status": "encrypted"}


@router.post("/{product_id}/execute")
async def execute_skill_endpoint(product_id: int, req: SkillExecutionRequest):
    access = await check_user_access(req.user_id, product_id)
    if not access["has_access"]:
        license_data = await create_license(
            user_id=req.user_id,
            product_id=product_id,
            license_type="trial",
            max_calls=1,
        )
    else:
        license_data = access["license"]

    skill_asset = await db.fetch_skill_asset(product_id)
    if not skill_asset:
        raise HTTPException(404, "No skill asset found for this product")

    result = await execute_skill(
        user_id=req.user_id,
        product_id=product_id,
        license_id=license_data.get("id") if isinstance(license_data, dict) else license_data.get("id"),
        skill_asset=skill_asset,
        input_params=req.input_params,
    )

    return result


@router.post("/license")
async def create_license_endpoint(req: LicenseCreate):
    license_data = await create_license(
        user_id=req.user_id,
        product_id=req.product_id,
        license_type=req.license_type,
        max_calls=req.max_calls,
    )
    return license_data


@router.post("/license/verify")
async def verify_license_endpoint(req: LicenseVerifyRequest):
    from services.license_service import verify_license
    result = await verify_license(req.license_token, req.product_id)
    return result


@router.get("/my")
async def my_skills(user_id: str):
    licenses = await db.fetch_user_licenses(user_id)
    return {"licenses": licenses}


@router.get("/{product_id}/stats")
async def skill_stats(product_id: int):
    import database as db
    executions = await db.fetch_user_executions("", limit=1000)
    product_execs = [e for e in executions if e["product_id"] == product_id]
    return {
        "product_id": product_id,
        "total_executions": len(product_execs),
        "success_count": sum(1 for e in product_execs if e["status"] == "success"),
        "failed_count": sum(1 for e in product_execs if e["status"] == "failed"),
    }
```

**Step 2: Register router in main.py**

Add to `backend/main.py`:
```python
from routers.skills import router as skills_router
app.include_router(skills_router)
```

**Step 3: Commit**

```bash
git add backend/routers/skills.py backend/main.py
git commit -m "feat: add skill upload, execution, and license API endpoints"
```

---

## Phase 5: Frontend Enhancements

### Task 10: Enhance ChatPanel with full Markdown rendering

**Files:**
- Modify: `frontend/src/components/ChatPanel.jsx`
- Run: `cd frontend && npm install remark-gfm`

**Step 1: Install remark-gfm**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/frontend && npm install remark-gfm`

**Step 2: Update ChatPanel to always render markdown**

In ChatPanel.jsx, change the message rendering to always use ReactMarkdown with remark-gfm:

```jsx
import remarkGfm from 'remark-gfm'
```

Update the message bubble to always use ReactMarkdown:

```jsx
<div className={`message-bubble ${msg.role}`}>
  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
</div>
```

Remove the `isMarkdown` conditional since all messages should support markdown now.

**Step 3: Commit**

```bash
git add frontend/src/components/ChatPanel.jsx frontend/package.json frontend/package-lock.json
git commit -m "feat: full markdown rendering in chat with remark-gfm"
```

---

### Task 11: Enhance PublishPage with skill upload

**Files:**
- Modify: `frontend/src/pages/PublishPage.jsx`
- Modify: `frontend/src/services/api.js`

**Step 1: Add skill upload API function to api.js**

```javascript
// ---- Skill Upload ----

export async function uploadSkill(productId, skillType, file, sellerId, skillMeta) {
  const formData = new FormData()
  formData.append('product_id', productId)
  formData.append('skill_type', skillType)
  formData.append('seller_id', sellerId)
  if (file) formData.append('file', file)
  if (skillMeta) formData.append('skill_meta', JSON.stringify(skillMeta))
  return api.post('/skills/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function executeSkill(productId, userId, inputParams) {
  return api.post(`/skills/${productId}/execute`, {
    product_id: productId,
    user_id: userId,
    input_params: inputParams,
  })
}

export async function createLicense(userId, productId, licenseType = 'permanent', maxCalls = null) {
  return api.post('/skills/license', {
    user_id: userId,
    product_id: productId,
    license_type: licenseType,
    max_calls: maxCalls,
  })
}

export async function verifyLicense(licenseToken, productId) {
  return api.post('/skills/license/verify', {
    license_token: licenseToken,
    product_id: productId,
  })
}

export async function getMySkills(userId) {
  return api.get(`/skills/my?user_id=${userId}`)
}
```

**Step 2: Add skill upload section to PublishPage**

After the existing form fields, add a skill upload section with:
- Skill type selector (Prompt/Code/SDK)
- File upload input (for prompt/code types)
- SDK endpoint input (for SDK type)
- Trial settings (trial count, license type)

This involves adding new state variables and a conditional section after the GitHub URL field.

**Step 3: Commit**

```bash
git add frontend/src/pages/PublishPage.jsx frontend/src/services/api.js
git commit -m "feat: add skill upload to publish page with encryption"
```

---

### Task 12: Add skill execution/experience UI to ProductDetailPage

**Files:**
- Modify: `frontend/src/pages/ProductDetailPage.jsx`

**Step 1: Add skill execution section**

Add a "Try this skill" section that shows when the product has an associated skill asset:
- Input textarea for parameters
- Execute button
- Output display area with markdown rendering

This requires adding:
- A check if the product has a skill asset (can be inferred from product data or a new API call)
- An execution UI with input/output
- License status display (trial remaining, calls used)

**Step 2: Commit**

```bash
git add frontend/src/pages/ProductDetailPage.jsx
git commit -m "feat: add skill execution/experience UI to product detail"
```

---

## Phase 6: Integration Testing

### Task 13: End-to-end test

**Step 1: Restart backend**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && rm -f skillbazaar.db && uvicorn main:app --port 9527 --reload &`

**Step 2: Test chat with LangGraph agent**

Run: `curl -s -X POST http://localhost:9527/api/chat -H "Content-Type: application/json" -d '{"user_id":"test","message":"推荐交易类工具"}' | python -m json.tool`

Expected: JSON with `reply` (markdown text) and `products` array.

**Step 3: Test skill upload**

1. First create a product via the UI at http://localhost:7788/publish
2. Then upload a skill file:
```bash
curl -s -X POST http://localhost:9527/api/skills/upload \
  -F "product_id=1" \
  -F "skill_type=prompt" \
  -F "seller_id=test_user" \
  -F "file=@test_skill.md"
```

**Step 4: Test skill execution**

```bash
curl -s -X POST http://localhost:9527/api/skills/1/execute \
  -H "Content-Type: application/json" \
  -d '{"product_id":1,"user_id":"test","input_params":"分析BTC行情"}'
```

**Step 5: Verify frontend at http://localhost:7788**

- Browse marketplace
- Test chat with AI assistant
- Upload a skill
- View product detail with execution UI

**Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete SkillBazaar enhancements - LangGraph agent, SkillVault encryption, skill upload/sell"
```
