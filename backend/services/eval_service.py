"""Skill evaluation service.

Runs static checks + optional LLM smoke test for a product's skill asset.
Stores results in skill_evaluations table (UPSERT by product_id, version bump).
"""
from __future__ import annotations

import json
import os
import re
import time

import httpx

import database as db
from services.skill_vault import decrypt_content, verify_integrity

LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.finmall.com/v1/chat/completions")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "GLM-5.1-FP8")

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions?", re.IGNORECASE),
    re.compile(r"reveal\s+your\s+(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"output\s+the\s+secret", re.IGNORECASE),
    re.compile(r"disregard\s+all\s+previous", re.IGNORECASE),
    re.compile(r"new\s+instruction", re.IGNORECASE),
]
_MIN_CONTENT_LENGTH = 50
_MAX_STATIC_SCORE = 40
_MAX_LLM_SCORE = 60


async def evaluate_product(product_id: int) -> dict:
    """Evaluate a product's skill asset or content. Returns evaluation result dict.

    Falls back to product.content_preview when no skill asset is uploaded.
    """
    product = await db.fetch_product_by_id(product_id)
    if not product:
        return {"status": "failed", "reason": "Product not found", "eval_score": 0,
                "flags": ["not_found"], "static_flags": [], "eval_version": 1}

    asset = await db.fetch_skill_asset(product_id)

    # Build a synthetic asset dict from content_preview if no real asset exists
    if not asset:
        content_preview = product.get("content_preview") or ""
        if not content_preview.strip():
            return {"status": "failed", "reason": "No skill asset or content available",
                    "eval_score": 0, "flags": ["no_content"], "static_flags": [],
                    "eval_version": 1}
        # Create a minimal asset-like dict for static checks
        import hashlib
        content_hash = hashlib.sha256(content_preview.encode()).hexdigest()[:32]
        asset = {
            "encrypted_blob": content_preview.encode("utf-8"),
            "encryption_iv": b"\x00" * 12,
            "encryption_salt": b"\x00" * 16,
            "content_hash": content_hash,
            "skill_type": "prompt",
        }

    # --- Static checks ---
    static_flags, static_score = _run_static_checks(product, asset)

    # --- LLM smoke test (prompt skills only) ---
    llm_flags = []
    llm_score = 0
    status = "completed"
    reason = None
    sample_output = ""

    skill_type = asset.get("skill_type", "prompt")

    if skill_type == "prompt":
        try:
            sample_output = await _call_eval_llm(asset)
            llm_flags, llm_score = _score_llm_output(sample_output)
        except Exception as e:
            status = "failed"
            reason = f"LLM evaluation failed: {e}"
            llm_flags = ["llm_unavailable"]
            llm_score = 0
    elif skill_type == "code":
        llm_flags = ["code_needs_sandbox"]
        llm_score = 30  # Placeholder: needs sandbox execution
    elif skill_type == "sdk":
        llm_flags = ["sdk_needs_endpoint"]
        llm_score = 30
    else:
        llm_flags = [f"unknown_type:{skill_type}"]
        llm_score = 0

    # --- Aggregate ---
    all_flags = static_flags + llm_flags
    eval_score = min(100, static_score + llm_score)

    if status == "failed":
        eval_score = max(0, eval_score - 30)

    # --- Determine version (increment existing) ---
    existing = await db.fetch_eval_report(product_id)
    version = 1
    if existing:
        version = (existing.get("eval_version") or 0) + 1

    # --- Persist ---
    result = {
        "product_id": product_id,
        "eval_score": eval_score,
        "status": status,
        "eval_version": version,
        "flags": all_flags,
        "static_flags": static_flags,
        "sample_output": sample_output[:500] if sample_output else "",
        "reason": reason,
    }

    await db.upsert_eval_report(result)
    return result


def _run_static_checks(product: dict, asset: dict) -> tuple[list, int]:
    """Run static checks on skill content. Returns (flags, score)."""
    flags = []
    score = _MAX_STATIC_SCORE

    encrypted_blob = asset.get("encrypted_blob")
    iv = asset.get("encryption_iv")
    salt = asset.get("encryption_salt")

    # Try decryption; if it fails, treat blob as already plaintext bytes
    if isinstance(encrypted_blob, bytes):
        plaintext = encrypted_blob
    else:
        try:
            plaintext = decrypt_content(encrypted_blob, iv, salt)
        except Exception:
            flags.append("decrypt_failed")
            return flags, 0

    # Integrity check
    if asset.get("content_hash"):
        if not verify_integrity(plaintext, asset["content_hash"]):
            flags.append("hash_mismatch")
            score -= 20

    content = plaintext.decode("utf-8", errors="replace") if isinstance(plaintext, bytes) else str(plaintext)

    # Empty check
    if not content or not content.strip():
        flags.append("empty_content")
        return flags, 0  # Hard fail

    # Length check
    if len(content.strip()) < _MIN_CONTENT_LENGTH:
        flags.append("too_short")
        score -= 15

    # Injection patterns
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(content):
            flags.append(f"injection:{pattern.pattern[:30]}")
            score -= 15
            break  # Report once

    return flags, max(0, score)


async def _call_eval_llm(asset: dict) -> str:
    """Call LLM for smoke test evaluation. Returns sample output text."""
    encrypted_blob = asset.get("encrypted_blob")

    if isinstance(encrypted_blob, bytes):
        skill_content = encrypted_blob.decode("utf-8", errors="replace")
    else:
        plaintext = decrypt_content(
            encrypted_blob,
            asset["encryption_iv"],
            asset["encryption_salt"],
        )
        skill_content = plaintext.decode("utf-8", errors="replace")

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": skill_content},
            {"role": "user", "content": "Execute this skill with input: test"},
        ],
        "max_tokens": 256,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(LLM_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    return msg.get("content", "") or msg.get("reasoning_content", "")


def _score_llm_output(output: str) -> tuple[list, int]:
    """Score LLM output quality. Returns (flags, score)."""
    flags = []
    score = _MAX_LLM_SCORE

    if not output or not output.strip():
        flags.append("empty_llm_output")
        return flags, 0

    if len(output) < 10:
        flags.append("very_short_output")
        score -= 20

    return flags, max(0, score)
