from __future__ import annotations

import json
import os
import time
import httpx

import database as db
from services.skill_vault import decrypt_content, verify_integrity

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = "GLM-5.1-FP8"


async def execute_skill(
    user_id: str,
    product_id: int,
    license_id: int | None,
    skill_asset: dict,
    input_params: str | None = None,
    trial_mode: bool = False,
) -> dict:
    start = time.time()
    skill_type = skill_asset["skill_type"]
    try:
        if skill_type == "prompt":
            result = await _execute_prompt_skill(skill_asset, input_params, trial_mode=trial_mode)
        elif skill_type == "code":
            result = await _execute_code_skill(skill_asset, input_params, trial_mode=trial_mode)
        elif skill_type == "sdk":
            result = await _execute_sdk_skill(skill_asset, input_params, trial_mode=trial_mode)
        else:
            result = {"error": f"Unknown skill type: {skill_type}"}

        duration_ms = int((time.time() - start) * 1000)
        output_summary = (result.get("output", "") or "")[:500]
        await db.insert_execution({
            "license_id": license_id,
            "user_id": user_id,
            "product_id": product_id,
            "execution_type": skill_type,
            "input_params": input_params,
            "output_summary": output_summary,
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


async def _execute_prompt_skill(skill_asset: dict, input_params: str | None, trial_mode: bool = False) -> dict:
    plaintext = decrypt_content(
        skill_asset["encrypted_blob"],
        skill_asset["encryption_iv"],
        skill_asset["encryption_salt"],
    )
    if not verify_integrity(plaintext, skill_asset["content_hash"]):
        return {"error": "Integrity check failed"}
    skill_content = plaintext.decode("utf-8")
    user_input = input_params or ""
    messages = [
        {"role": "system", "content": skill_content},
        {"role": "user", "content": user_input},
    ]
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    # Trial mode: reduce max_tokens to 512 to control cost
    max_tokens = 512 if trial_mode else 1024
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
    content = msg.get("content", "") or msg.get("reasoning_content", "")

    # Trial mode: truncate output to 500 chars + suffix notice
    if trial_mode and len(content) > 500:
        content = content[:500] + "\n\n[...购买后解锁完整输出]"

    return {"output": content, "skill_type": "prompt"}


async def _execute_code_skill(skill_asset: dict, input_params: str | None, trial_mode: bool = False) -> dict:
    plaintext = decrypt_content(
        skill_asset["encrypted_blob"],
        skill_asset["encryption_iv"],
        skill_asset["encryption_salt"],
    )
    note = "Full code execution requires sandbox environment (internal only)"
    if trial_mode:
        note = "需购买后在沙箱运行"
    return {
        "output": f"Code skill executed (size: {len(plaintext)} bytes). Input: {input_params}",
        "skill_type": "code",
        "note": note,
    }


async def _execute_sdk_skill(skill_asset: dict, input_params: str | None, trial_mode: bool = False) -> dict:
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
