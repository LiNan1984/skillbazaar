"""SkillBazaar API Key & Developer Router — 开发者API密钥管理 + CLI下载 + OpenAI兼容鉴权"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from services import apikey_service, sandbox_service
from routers.user_v2 import get_current_user
import json
import asyncio

router = APIRouter(prefix="/api/sandbox", tags=["developer"])


class CreateApiKeyReq(BaseModel):
    name: str = "default"
    permissions: str = "chat,execute"
    rate_limit: int = 100


class ChatCompletionReq(BaseModel):
    model: str
    messages: List[dict]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 2048


# ========== 沙盒核心操作 ==========

class ExecuteCodeReq(BaseModel):
    code: str
    language: str = "python"
    encrypted: bool = False


class EncryptAgentReq(BaseModel):
    source_code: str


@router.get("/status")
async def get_sandbox_status(user: dict = Depends(get_current_user)):
    """查询沙盒状态和剩余时长"""
    result = await sandbox_service.get_sandbox_status(user["id"])
    return result


@router.post("/start")
async def start_sandbox(language: str = "python", user: dict = Depends(get_current_user)):
    """启动沙盒（一用户一沙盒）"""
    result = await sandbox_service.get_or_create_sandbox(user["id"], language)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/execute")
async def execute_code_in_sandbox(req: ExecuteCodeReq, user: dict = Depends(get_current_user)):
    """在沙盒中执行代码"""
    result = await sandbox_service.execute_in_sandbox(
        user["id"], req.code, req.encrypted, req.language
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


class ChatReq(BaseModel):
    message: str


@router.post("/chat")
async def chat_with_npc(req: ChatReq, user: dict = Depends(get_current_user)):
    """与NPC常驻Agent对话 — 通过文件管道交互"""
    result = await sandbox_service.chat_with_npc_agent(user["id"], req.message)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


@router.delete("/stop")
async def stop_sandbox(user: dict = Depends(get_current_user)):
    """停止沙盒"""
    result = await sandbox_service.destroy_sandbox(user["id"])
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/encrypt-agent")
async def encrypt_agent(req: EncryptAgentReq, user: dict = Depends(get_current_user)):
    """虾塘加密 — 加密Agent源码"""
    encrypted_blob, content_hash, salt = sandbox_service.encrypt_agent_code(req.source_code)
    import base64
    # Store encrypted agent for this user
    db = await sandbox_service._get_db()
    await db.execute(
        "INSERT OR REPLACE INTO user_agent_skills (user_id, encrypted_blob, content_hash, salt, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
        (user["id"], base64.urlsafe_b64encode(encrypted_blob).decode(), content_hash, salt)
    )
    await db.commit()
    return {
        "message": "🦐 Agent已虾入虾塘！源码加密保护，只能沙盒内执行",
        "encrypted_blob": base64.urlsafe_b64encode(encrypted_blob).decode(),
        "content_hash": content_hash,
        "salt": salt
    }


class DecryptAgentReq(BaseModel):
    encrypted_blob: str


class NpcChatReq(BaseModel):
    message: str


@router.post("/decrypt-agent")
async def decrypt_agent(req: DecryptAgentReq, user: dict = Depends(get_current_user)):
    """虾塘解密 — 在沙盒内解密Agent源码（仅验证用）"""
    import base64
    try:
        source_code = sandbox_service.decrypt_agent_code(base64.urlsafe_b64decode(req.encrypted_blob))
    except Exception as e:
        raise HTTPException(400, f"解密失败: {str(e)}")
    return {"source_code": source_code}


# ========== API Key 管理 ==========

@router.get("/api-keys")
async def list_api_keys(user: dict = Depends(get_current_user)):
    """列出用户所有API Key（脱敏）"""
    keys = await apikey_service.list_api_keys(user["id"])
    return {"keys": keys}


@router.post("/api-keys")
async def create_api_key(req: CreateApiKeyReq, user: dict = Depends(get_current_user)):
    """创建新的API Key"""
    result = await apikey_service.create_api_key(
        user["id"], req.name, req.permissions, req.rate_limit
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: int, user: dict = Depends(get_current_user)):
    """撤销API Key"""
    return await apikey_service.revoke_api_key(user["id"], key_id)


# ========== OpenAI兼容接口（支持API Key鉴权）==========

async def _get_user_from_request(request: Request) -> str:
    """从Bearer token或API Key中提取user_id"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        # Try API key first (sk-xxx)
        if token.startswith("sk-"):
            info = await apikey_service.verify_api_key(token)
            if info:
                return info["user_id"]
        # Fall back to user auth token
        from database import fetch_user_by_token
        user = await fetch_user_by_token(token)
        if user:
            return user["id"]
        raise HTTPException(401, "Invalid token or API key")
    raise HTTPException(401, "Missing Authorization header")


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionReq, request: Request):
    """
    OpenAI /v1/chat/completions 兼容接口
    
    支持两种鉴权:
    - 用户token: Bearer {user_token}
    - API Key: Bearer sk-xxxxxx
    
    model参数:
    - GLM-5.1-FP8: 直接调用LLM
    - agent-{id}: 调用用户已购买的Agent
    - skill-{id}: 调用已购买的Skill
    
    外部调用示例:
    ```bash
    curl https://skillbazaar.harness-agent.app/api/sandbox/v1/chat/completions \\
      -H "Authorization: Bearer sk-xxxxxx" \\
      -H "Content-Type: application/json" \\
      -d '{"model":"GLM-5.1-FP8","messages":[{"role":"user","content":"你好"}]}'
    ```
    """
    user_id = await _get_user_from_request(request)
    
    if req.stream:
        # SSE streaming response
        return StreamingResponse(
            _stream_chat(req, user_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    
    try:
        result = await sandbox_service.chat_completion_with_agent(
            model=req.model, messages=req.messages,
            user_id=user_id, stream=False,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"执行失败: {str(e)}")


async def _stream_chat(req: ChatCompletionReq, user_id: str):
    """SSE streaming for chat completions"""
    import httpx
    
    system_prompt = "你是SkillBazaar智能助手。"
    full_messages = [{"role": "system", "content": system_prompt}] + req.messages
    
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{sandbox_service.LLM_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {sandbox_service.LLM_API_KEY}"},
                json={
                    "model": sandbox_service.LLM_MODEL,
                    "messages": full_messages,
                    "stream": True,
                    "max_tokens": req.max_tokens
                }
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield line + "\n\n"
                        if line.strip() == "data: [DONE]":
                            break
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


# ========== CLI 下载 ==========

@router.get("/cli-download")
async def generate_cli_download(user: dict = Depends(get_current_user)):
    """生成CLI下载认证链接"""
    return await apikey_service.generate_cli_download_token(user["id"])


@router.get("/cli-download/{token}")
async def download_cli(token: str):
    """下载skbz CLI工具（一次性token认证）"""
    user_id = await apikey_service.verify_cli_token(token)
    if not user_id:
        raise HTTPException(401, "下载链接无效或已过期")
    
    cli_path = "/usr/local/bin/skbz"
    import os
    if not os.path.exists(cli_path):
        raise HTTPException(404, "CLI工具未安装")
    
    return FileResponse(
        cli_path,
        filename="skbz",
        media_type="application/octet-stream"
    )


# ========== API 文档 ==========

@router.get("/api-docs")
async def get_api_docs():
    """获取API调用文档（开发者参考）"""
    base = "https://skillbazaar.harness-agent.app/api/sandbox"
    curl_ex = (
        "curl -X POST " + base + "/v1/chat/completions \\\n"
        '  -H "Authorization: Bearer sk-xxxxxx" \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{"model":"GLM-5.1-FP8","messages":[{"role":"user","content":"你好"}]}\''
    )
    python_ex = (
        "from openai import OpenAI\n"
        "client = OpenAI(\n"
        "    base_url='" + base + "/v1',\n"
        "    api_key='sk-xxxxxx'\n"
        ")\n"
        "response = client.chat.completions.create(\n"
        "    model='GLM-5.1-FP8',\n"
        "    messages=[{'role': 'user', 'content': '你好'}]\n"
        ")\n"
        "print(response.choices[0].message.content)"
    )
    nodejs_ex = (
        "import OpenAI from 'openai';\n"
        "const client = new OpenAI({\n"
        "  baseURL: '" + base + "/v1',\n"
        "  apiKey: 'sk-xxxxxx'\n"
        "});\n"
        "const resp = await client.chat.completions.create({\n"
        "  model: 'GLM-5.1-FP8',\n"
        "  messages: [{role: 'user', content: '你好'}]\n"
        "});"
    )
    return {
        "title": "SkillBazaar 开发者API文档",
        "version": "1.0",
        "base_url": base,
        "auth": {
            "methods": [
                {"type": "API Key", "header": "Authorization: Bearer sk-xxxx", "description": "在「开发者」页面申请API Key，用于外部程序调用"},
                {"type": "User Token", "header": "Authorization: Bearer {token}", "description": "登录后获取的用户token"}
            ]
        },
        "endpoints": [
            {
                "path": "/v1/chat/completions",
                "method": "POST",
                "description": "OpenAI兼容聊天接口 — 调用LLM/Agent/Skill",
                "request_body": {"model": "GLM-5.1-FP8 | agent-{id} | skill-{id}", "messages": [{"role": "user", "content": "你的问题"}], "stream": False, "temperature": 0.7, "max_tokens": 2048},
                "response": "OpenAI标准chat.completion格式",
                "example": {"curl": curl_ex, "python": python_ex, "nodejs": nodejs_ex}
            },
            {"path": "/status", "method": "GET", "description": "查询沙盒状态和剩余时长", "auth": "required"},
            {"path": "/start?language=python", "method": "POST", "description": "启动沙盒（一用户一沙盒）", "auth": "required"},
            {"path": "/execute", "method": "POST", "description": "在沙盒中执行代码", "request_body": {"code": "print('hello')", "encrypted": False, "language": "python"}, "auth": "required"},
            {"path": "/stop", "method": "DELETE", "description": "停止沙盒", "auth": "required"},
            {"path": "/encrypt-agent", "method": "POST", "description": "虾塘加密 — 加密Agent源码", "request_body": {"source_code": "your code here"}, "auth": "required"},
            {"path": "/decrypt-agent", "method": "POST", "description": "虾塘解密 — 解密Agent源码", "request_body": {"encrypted_blob": "base64 encoded..."}, "auth": "required"},
            {"path": "/api-keys", "method": "GET/POST/DELETE", "description": "管理API密钥", "auth": "required"},
            {"path": "/cli-download", "method": "GET", "description": "生成CLI下载认证链接", "auth": "required"}
        ],
        "models": {
            "GLM-5.1-FP8": "智谱GLM-5.1 — 通用大模型，推荐日常使用",
            "agent-{id}": "已购买Agent — model填agent-{数字id}，如agent-1",
            "skill-{id}": "已购买Skill — model填skill-{数字id}，如skill-1"
        },
        "rate_limits": {"default": "100 requests/min per API key", "sandbox_execute": "60 seconds quota deducted per execution"},
        "pricing": {"sandbox": "100积分 = 1小时沙盒时长", "api_calls": "免费额度: 100次/天，超出需充值积分"}
    }
