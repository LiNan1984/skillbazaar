"""
SkillBazaar Sandbox Service — 虾塘加密 + 沙盒执行引擎
一个用户一个沙盒，积分只能换时长
Agent源码Fernet加密，只在沙盒内解密执行
执行策略: Cubelet containerd → 本地subprocess降级
"""
from __future__ import annotations
import asyncio
import json
import os
import uuid
import time
import hashlib
import base64
import subprocess
import tempfile
import shutil
import signal
from typing import Optional
from cryptography.fernet import Fernet
import aiosqlite

# --- 虾塘加密 (Shrimp Pond Encryption) ---
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BACKEND_DIR, "data")
os.makedirs(_DATA_DIR, exist_ok=True)

SHRIMP_POND_KEY = os.environ.get("SHRIMP_POND_KEY", "").strip()
if not SHRIMP_POND_KEY:
    _key_path = os.path.join(_DATA_DIR, ".shrimp_pond_key")
    if os.path.exists(_key_path):
        with open(_key_path) as f:
            SHRIMP_POND_KEY = f.read().strip()
    else:
        SHRIMP_POND_KEY = Fernet.generate_key().decode()
        with open(_key_path, "w") as f:
            f.write(SHRIMP_POND_KEY)
        os.chmod(_key_path, 0o600)

_fernet = Fernet(SHRIMP_POND_KEY.encode())

CUBELET_SOCKET = "/data/cubelet/cubelet.sock"
SANDBOX_NS = "skbz-sandbox"
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://xiaozhuoai.harness-agent.app/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "GLM-5.1-FP8")

DB_PATH = os.environ.get("SKBZ_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "skillbazaar.db"))

# Sandbox workspace base dir
SANDBOX_WORKSPACE = "/data/skbz-sandbox-workspaces"


def _cubelet_available() -> bool:
    """Check if Cubelet containerd socket is accessible"""
    return os.path.exists(CUBELET_SOCKET)


async def _get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


def _start_npc_agent(sandbox_id: str, workspace: str, user_id: str) -> int:
    """启动NPC常驻Agent守护进程，通过文件管道(stdin/stdout)交互"""
    npc_script = os.path.join(workspace, "npc_agent.py")
    # Write NPC agent script
    npc_code = '''#!/usr/bin/env python3
"""NPC Agent — 常驻运行，通过文件管道接收消息，调用LLM回复"""
import json, os, sys, time, signal, urllib.request

PIPE_IN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "npc_pipe_in")
PIPE_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "npc_pipe_out")
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "npc.pid")
LLM_BASE = os.environ.get("LLM_API_BASE", "https://xiaozhuoai.harness-agent.app/v1")
LLM_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "GLM-5.1-FP8")

# Write PID
with open(PID_FILE, "w") as f:
    f.write(str(os.getpid()))

conversation_history = []

def call_llm(messages):
    """Call LLM API with urllib (no deps needed)"""
    try:
        data = json.dumps({"model": LLM_MODEL, "messages": messages, "max_tokens": 2048}).encode()
        req = urllib.request.Request(
            f"{LLM_BASE}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {LLM_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[NPC Error] LLM调用失败: {e}"

def process_message(msg):
    """处理一条消息"""
    global conversation_history
    conversation_history.append({"role": "user", "content": msg})
    # Keep last 20 messages
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]
    
    system_msg = {"role": "system", "content": "你是SkillBazaar沙盒中的NPC Agent，常驻运行。你帮助用户执行任务、回答问题、编写代码。用中文回复。"}
    full_messages = [system_msg] + conversation_history
    
    reply = call_llm(full_messages)
    conversation_history.append({"role": "assistant", "content": reply})
    return reply

def main():
    # Signal handler for graceful shutdown
    running = True
    def handle_signal(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    while running:
        try:
            # Check for incoming message
            if os.path.exists(PIPE_IN):
                with open(PIPE_IN, "r") as f:
                    content = f.read().strip()
                if content:
                    # Process and write response
                    reply = process_message(content)
                    with open(PIPE_OUT, "w") as f:
                        f.write(reply)
                    # Clear input pipe
                    os.remove(PIPE_IN)
            time.sleep(0.5)
        except Exception as e:
            time.sleep(1)

if __name__ == "__main__":
    main()
'''
    with open(npc_script, "w") as f:
        f.write(npc_code)
    
    # Start NPC agent as background process
    proc = subprocess.Popen(
        ["python3", npc_script],
        cwd=workspace,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # Pass LLM config to NPC agent
        env={
            **os.environ,
            "LLM_API_BASE": LLM_API_BASE,
            "LLM_API_KEY": LLM_API_KEY,
            "LLM_MODEL": LLM_MODEL,
        }
    )
    return proc.pid


async def chat_with_npc_agent(user_id: str, message: str) -> dict:
    """与常驻NPC Agent交互 — 通过文件管道"""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM sandbox_sessions WHERE user_id=? AND status='running'",
            (user_id,)
        )
        sb = await cursor.fetchone()
        if not sb:
            return {"error": "沙盒未启动，请先启动沙盒"}
        
        sandbox_id = sb["sandbox_id"]
        workspace = os.path.join(SANDBOX_WORKSPACE, sandbox_id)
        pipe_in = os.path.join(workspace, "npc_pipe_in")
        pipe_out = os.path.join(workspace, "npc_pipe_out")
        pid_file = os.path.join(workspace, "npc.pid")
        
        # Check NPC is alive
        npc_alive = False
        if os.path.exists(pid_file):
            with open(pid_file) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 0)  # Check process exists
                npc_alive = True
            except (ProcessLookupError, ValueError):
                pass
        
        if not npc_alive:
            # Restart NPC agent
            _start_npc_agent(sandbox_id, workspace, user_id)
            await asyncio.sleep(1)
        
        # Write message to input pipe
        with open(pipe_in, "w") as f:
            f.write(message)
        
        # Wait for response (poll output pipe)
        for _ in range(120):  # 60 seconds max (LLM API can be slow)
            await asyncio.sleep(0.5)
            if os.path.exists(pipe_out):
                with open(pipe_out, "r") as f:
                    reply = f.read()
                os.remove(pipe_out)
                return {
                    "sandbox_id": sandbox_id,
                    "message": message,
                    "reply": reply,
                    "status": "success"
                }
        
        return {"error": "NPC Agent响应超时", "status": "timeout"}
    finally:
        await db.close()


def encrypt_agent_code(source_code: str) -> tuple[bytes, str, str]:
    """虾入虾塘 — 加密Agent源码"""
    encrypted = _fernet.encrypt(source_code.encode())
    salt = base64.urlsafe_b64encode(os.urandom(16)).decode()
    content_hash = hashlib.sha256(source_code.encode()).hexdigest()
    return encrypted, salt, content_hash


def decrypt_agent_code(encrypted_blob: bytes) -> str:
    """虾出虾塘 — 只在沙盒内部调用"""
    return _fernet.decrypt(encrypted_blob).decode()


async def _ctr(*args, timeout: int = 60) -> tuple[int, str, str]:
    """Run ctr command via Cubelet containerd"""
    cmd = ["ctr", "-a", CUBELET_SOCKET, "-n", SANDBOX_NS] + list(args)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode()[:10000], stderr.decode()[:5000]
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "timeout"


async def _ensure_namespace():
    await _ctr("namespace", "create", SANDBOX_NS, timeout=5)
    return True


async def _ensure_image(image: str):
    rc, out, _ = await _ctr("images", "ls", "-q", image, timeout=10)
    if image not in out:
        await _ctr("images", "pull", image, timeout=120)


async def get_or_create_sandbox(user_id: str, language: str = "python") -> dict:
    """
    一个用户一个沙盒 — 获取或创建
    优先Cubelet containerd，降级到本地subprocess
    """
    db = await _get_db()
    try:
        # Check existing running sandbox
        cursor = await db.execute(
            "SELECT * FROM sandbox_sessions WHERE user_id=? AND status='running'",
            (user_id,)
        )
        existing = await cursor.fetchone()
        if existing:
            row = dict(existing)
            # Check if expired
            if row.get("expires_at") and time.time() > row["expires_at"]:
                await db.execute(
                    "UPDATE sandbox_sessions SET status='expired' WHERE sandbox_id=?",
                    (row["sandbox_id"],)
                )
                await db.commit()
            else:
                return row

        # Check sandbox quota
        cursor = await db.execute("SELECT sandbox_quota FROM users WHERE id=?", (user_id,))
        user = await cursor.fetchone()
        if not user or (user["sandbox_quota"] or 0) <= 0:
            return {"error": "沙盒时长不足，请先用积分兑换", "status": "no_quota"}

        quota_seconds = user["sandbox_quota"] or 0
        sandbox_id = f"skbz-{user_id[:8]}"
        now = time.time()
        expires_at = now + quota_seconds

        if _cubelet_available():
            # --- Cubelet containerd path ---
            await _ensure_namespace()
            image_map = {
                "python": "docker.io/library/python:3.11-slim",
                "nodejs": "docker.io/library/node:20-slim",
            }
            image = image_map.get(language, image_map["python"])
            await _ctr("task", "kill", sandbox_id, timeout=5)
            await _ctr("container", "delete", sandbox_id, timeout=5)
            await _ensure_image(image)
            rc, out, err = await _ctr("run", "-d", image, sandbox_id, "sleep", "infinity", timeout=60)
            status = "running" if rc == 0 else "failed"
            executor = "cubelet"
            if status == "failed":
                # Fall through to local
                _cubelet_fallback = True
            else:
                await db.execute(
                    """INSERT OR REPLACE INTO sandbox_sessions 
                    (sandbox_id, user_id, language, image, status, created_at, expires_at, timeout)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (sandbox_id, user_id, language, image, "running", now, expires_at, quota_seconds)
                )
                await db.commit()
                return {
                    "sandbox_id": sandbox_id,
                    "language": language,
                    "status": "running",
                    "executor": "cubelet",
                    "expires_at": expires_at,
                    "message": "🦐 沙盒已启动！(Cubelet容器) 你的虾可以打工了！"
                }
        
        # --- Local subprocess path (fallback or default) ---
        workspace = os.path.join(SANDBOX_WORKSPACE, sandbox_id)
        os.makedirs(workspace, exist_ok=True)

        # Check if python3/node available
        if language == "nodejs":
            runner = shutil.which("node")
        else:
            runner = shutil.which("python3") or shutil.which("python")
        
        if not runner:
            if language == "nodejs":
                return {"sandbox_id": sandbox_id, "status": "failed", "error": "node not available"}
            runner = shutil.which("python3") or "python3"

        await db.execute(
            """INSERT OR REPLACE INTO sandbox_sessions 
            (sandbox_id, user_id, language, image, status, created_at, expires_at, timeout)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sandbox_id, user_id, language, runner, "running", now, expires_at, quota_seconds)
        )
        await db.commit()

        # --- 启动NPC常驻Agent守护进程 ---
        npc_pid = _start_npc_agent(sandbox_id, workspace, user_id)

        # Store NPC PID
        await db.execute("UPDATE sandbox_sessions SET pid=? WHERE sandbox_id=?", (npc_pid, sandbox_id))
        await db.commit()

        return {
            "sandbox_id": sandbox_id,
            "language": language,
            "status": "running",
            "executor": "local",
            "workspace": workspace,
            "npc_pid": npc_pid,
            "expires_at": expires_at,
            "message": "🦐 沙盒已启动！NPC Agent常驻运行中！"
        }
    finally:
        await db.close()


async def execute_in_sandbox(user_id: str, code: str, encrypted: bool = False, language: str = "python") -> dict:
    """在沙盒中执行代码"""
    # Decrypt if encrypted (code is base64-encoded Fernet token from client)
    if encrypted:
        raw_fernet = base64.urlsafe_b64decode(code if isinstance(code, str) else code)
        code = decrypt_agent_code(raw_fernet)

    # Get or create sandbox
    sb = await get_or_create_sandbox(user_id, language)
    if sb.get("status") == "no_quota":
        return sb
    if sb.get("status") == "failed":
        return sb

    sandbox_id = sb["sandbox_id"]
    executor = sb.get("executor", "local")

    if executor == "cubelet" and _cubelet_available():
        # --- Cubelet containerd execution ---
        exec_id = f"exec-{uuid.uuid4().hex[:8]}"
        escaped_code = code.replace("'", "'\\''")
        if language == "python":
            cmd_str = f"python3 -c '{escaped_code}'"
        else:
            cmd_str = f"node -e '{escaped_code}'"
        rc, out, err = await _ctr("task", "exec", "--exec-id", exec_id, sandbox_id, "/bin/sh", "-c", cmd_str, timeout=300)
    else:
        # --- Local subprocess execution ---
        workspace = os.path.join(SANDBOX_WORKSPACE, sandbox_id)
        os.makedirs(workspace, exist_ok=True)
        
        if language == "nodejs":
            suffix = ".js"
            cmd_prefix = ["node"]
        else:
            suffix = ".py"
            cmd_prefix = ["python3"]

        # Write code to temp file for reliable execution
        tmp_file = os.path.join(workspace, f"exec_{uuid.uuid4().hex[:8]}{suffix}")
        with open(tmp_file, "w") as f:
            f.write(code)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_prefix, tmp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
                rc = proc.returncode or 0
                out = stdout.decode(errors="replace")[:10000]
                err = stderr.decode(errors="replace")[:5000]
            except asyncio.TimeoutError:
                proc.kill()
                rc = -1
                out = ""
                err = "Execution timeout (60s)"
        finally:
            # Cleanup temp file
            try:
                os.unlink(tmp_file)
            except:
                pass

    # Deduct sandbox time (60 seconds per execution)
    db = await _get_db()
    try:
        await db.execute(
            "UPDATE users SET sandbox_quota = MAX(COALESCE(sandbox_quota,0) - 60, 0) WHERE id=?",
            (user_id,)
        )
        await db.commit()
        cursor = await db.execute("SELECT sandbox_quota FROM users WHERE id=?", (user_id,))
        row = await cursor.fetchone()
        remaining = row["sandbox_quota"] if row else 0
    finally:
        await db.close()

    return {
        "sandbox_id": sandbox_id,
        "exit_code": rc,
        "stdout": out,
        "stderr": err,
        "status": "success" if rc == 0 else "error",
        "remaining_quota": remaining,
        "executor": executor if _cubelet_available() else "local"
    }


async def destroy_sandbox(user_id: str) -> dict:
    """销毁用户的沙盒"""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM sandbox_sessions WHERE user_id=? AND status='running'",
            (user_id,)
        )
        sb = await cursor.fetchone()
        if not sb:
            return {"status": "not_found", "message": "没有运行中的沙盒"}

        sandbox_id = sb["sandbox_id"]
        row = dict(sb)
        
        # Kill NPC Agent process
        pid_file = os.path.join(SANDBOX_WORKSPACE, sandbox_id, "npc.pid")
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, ValueError, FileNotFoundError):
                pass
        
        if row.get("image") and _cubelet_available() and "docker.io" in str(row.get("image", "")):
            # Cubelet container
            await _ctr("task", "kill", sandbox_id, timeout=10)
            await _ctr("container", "delete", sandbox_id, timeout=10)
        
        # Cleanup workspace
        workspace = os.path.join(SANDBOX_WORKSPACE, sandbox_id)
        if os.path.exists(workspace):
            shutil.rmtree(workspace, ignore_errors=True)

        await db.execute(
            "UPDATE sandbox_sessions SET status='destroyed' WHERE sandbox_id=?",
            (sandbox_id,)
        )
        await db.commit()
        return {"sandbox_id": sandbox_id, "status": "destroyed", "message": "🦐 沙盒已销毁，虾回虾塘"}
    finally:
        await db.close()


async def get_sandbox_status(user_id: str) -> dict:
    """查询沙盒状态和剩余时长"""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM sandbox_sessions WHERE user_id=? AND status='running'",
            (user_id,)
        )
        sb = await cursor.fetchone()
        
        cursor = await db.execute("SELECT sandbox_quota FROM users WHERE id=?", (user_id,))
        user = await cursor.fetchone()
        quota = user["sandbox_quota"] if user else 0
        
        return {
            "sandbox": dict(sb) if sb else None,
            "remaining_seconds": quota,
            "remaining_hours": round(quota / 3600, 1) if quota else 0,
            "executor": ("cubelet" if _cubelet_available() else "local"),
            "message": "🦐 沙盒运行中" if sb else "沙盒未启动"
        }
    finally:
        await db.close()


# --- OpenAI-Compatible Model-as-Application ---

async def chat_completion_with_agent(
    model: str,
    messages: list,
    user_id: str,
    stream: bool = False,
) -> dict:
    """
    OpenAI /v1/chat/completions 兼容
    model=agent-{id} → 调用Agent
    model=skill-{id} → 调用Skill
    其他 → 直接调用LLM
    """
    import httpx

    system_prompt = "你是SkillBazaar智能导购助手，帮助用户选择合适的AI技能和智能体。"

    if model.startswith("agent-"):
        agent_id = model.split("-", 1)[1]
        db = await _get_db()
        try:
            cursor = await db.execute("SELECT * FROM user_agents WHERE id=?", (int(agent_id),))
            agent = await cursor.fetchone()
        finally:
            await db.close()
        if not agent:
            raise ValueError(f"Agent {agent_id} 不存在")
        system_prompt = agent["system_prompt"] if agent["system_prompt"] else system_prompt

    elif model.startswith("skill-"):
        product_id = model.split("-", 1)[1]
        db = await _get_db()
        try:
            cursor = await db.execute("SELECT * FROM products WHERE id=?", (int(product_id),))
            product = await cursor.fetchone()
        finally:
            await db.close()
        if product:
            system_prompt = f"[Skill: {product['name']}] {product['description'] or ''}"

    # Build messages
    full_messages = [{"role": "system", "content": system_prompt}]
    full_messages.extend(messages)

    # Call LLM API
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{LLM_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={"model": LLM_MODEL, "messages": full_messages, "stream": stream}
        )
        result = resp.json()

    return result
