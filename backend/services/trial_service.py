"""Trial service v4.9.

Implements:
- Trial execution with token cap (512 tokens)
- Trial eligibility checks (not purchased, under limit)
- Trial history retrieval
- Cron cleanup of old trial runs (>30 days)
"""
from __future__ import annotations

import time
import database as db
from datetime import datetime, timedelta

MAX_TRIALS_PER_PRODUCT = 3
MAX_TOKENS = 512


async def run_trial(user_id: str, product_id: int, input_text: str) -> dict:
    """Execute a trial run of a Skill.

    Raises ValueError on validation errors.
    Returns dict with trial data.
    """
    # Verify product exists and is active
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise ValueError("Product not found")
    if product.get("status") != "active":
        raise ValueError("Product is not available")

    # Check if user already purchased
    already_purchased = await db.check_already_purchased(user_id, product_id)
    if already_purchased:
        raise ValueError("已购买此商品，无需试用")

    # Check trial limit
    trial_count = await db.count_trial_runs_by_user_and_product(user_id, product_id)
    if trial_count >= MAX_TRIALS_PER_PRODUCT:
        raise ValueError("试用次数已达上限（每个商品最多3次试用）")

    # Create trial record
    trial = await db.create_trial_run(user_id, product_id, input_text, status="running")
    if not trial:
        raise ValueError("Failed to create trial run")

    start_time = time.time()

    try:
        # Simulate trial execution — in production this would invoke the sandbox
        output_text = _simulate_trial_execution(input_text, product)

        # Cap output at MAX_TOKENS (simulated as character count)
        output_text = output_text[:MAX_TOKENS * 4]  # ~4 chars per token
        tokens_used = min(len(output_text) // 4, MAX_TOKENS)

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Update trial record with results
        updated = await db.update_trial_run(
            trial["trial_id"],
            status="completed",
            output_text=output_text,
            tokens_used=tokens_used,
            execution_time_ms=elapsed_ms,
        )

        result = dict(updated) if updated else dict(trial)
        result["product_name"] = product.get("name", "")
        return result

    except Exception as e:
        # Mark trial as failed
        elapsed_ms = int((time.time() - start_time) * 1000)
        await db.update_trial_run(
            trial["id"],
            status="failed",
            error_message=str(e),
            execution_time_ms=elapsed_ms,
        )
        raise ValueError(f"试用执行失败: {e}")


def _simulate_trial_execution(input_text: str, product: dict) -> str:
    """Simulate a skill execution for trial purposes.

    In production, this would call the actual sandbox/execution engine.
    """
    product_name = product.get("name", "Skill")
    skill_type = product.get("category", "Skill")

    if skill_type == "Skill":
        return f"[{product_name}] 模拟执行结果:\n输入: {input_text[:100]}\n\n分析完成。这是一个试用输出，实际购买后将获得完整功能。"
    elif skill_type == "Agent":
        return f"[{product_name}] Agent 模拟执行:\n处理输入: {input_text[:100]}\n\nAgent 已完成任务。试用模式下仅展示部分结果。"
    else:
        return f"[{product_name}] 执行结果:\n{input_text[:200]}\n\n（试用输出）"


async def get_trial_history(user_id: str, product_id: int = None) -> list[dict]:
    """Get trial history for a user, optionally filtered by product."""
    if product_id:
        trials = await db.get_trial_runs_by_user_and_product(user_id, product_id)
    else:
        trials = await db.get_trial_runs_by_user(user_id)

    # Enrich with product_name
    result = []
    for t in trials:
        if not t.get("product_name"):
            product = await db.fetch_product_by_id(t["product_id"])
            t["product_name"] = product.get("name", "") if product else ""
        result.append(t)
    return result


async def can_trial(user_id: str, product_id: int) -> dict:
    """Check if user can trial a product.

    Returns dict with can_trial (bool), reason (str|None), trials_remaining (int).
    """
    # Check product exists
    product = await db.fetch_product_by_id(product_id)
    if not product:
        return {"can_trial": False, "reason": "商品不存在", "trials_remaining": 0}
    if product.get("status") != "active":
        return {"can_trial": False, "reason": "商品不支持试用", "trials_remaining": 0}

    # Check if already purchased
    already_purchased = await db.check_already_purchased(user_id, product_id)
    if already_purchased:
        return {"can_trial": False, "reason": "已购买此商品", "trials_remaining": 0}

    # Check trial limit
    trial_count = await db.count_trial_runs_by_user_and_product(user_id, product_id)
    remaining = max(0, MAX_TRIALS_PER_PRODUCT - trial_count)
    if remaining <= 0:
        return {"can_trial": False, "reason": "试用次数已达上限", "trials_remaining": 0}

    return {"can_trial": True, "reason": None, "trials_remaining": remaining}


async def cleanup_old_trials(days: int = 30) -> dict:
    """Cron: delete trial runs older than 30 days.

    Returns dict with deleted_count and message.
    """
    deleted_count = await db.cleanup_old_trials(days)
    return {
        "deleted_count": deleted_count,
        "message": f"Cleaned up {deleted_count} old trial runs",
    }
