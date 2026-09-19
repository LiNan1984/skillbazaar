"""Bulk Operation service v4.12.

Implements:
- execute_bulk_operation: validates ownership, applies operation, logs results
- get_bulk_operation_history: paginated history for a seller
"""
from __future__ import annotations

import database as db
from datetime import datetime

MAX_BULK_PRODUCTS = 50

VALID_OPERATIONS = {"publish", "unpublish", "price_update", "delete"}


async def execute_bulk_operation(user_id: str, operation: str, product_ids: list[int], params: dict | None = None) -> dict:
    """Execute a bulk operation on multiple products.

    Validates operation type, product count limit, and ownership.
    Applies the operation to each product and logs results.

    Returns dict with operation summary and per-product results.
    """
    # Validate operation type
    if operation not in VALID_OPERATIONS:
        raise ValueError(f"不支持的操作类型: {operation}。支持的类型: {', '.join(sorted(VALID_OPERATIONS))}")

    # Validate max products
    if len(product_ids) > MAX_BULK_PRODUCTS:
        raise ValueError(f"单次批量操作最多支持{MAX_BULK_PRODUCTS}个商品，当前选择了{len(product_ids)}个")

    if not product_ids:
        raise ValueError("请至少选择一个商品")

    params = params or {}

    # Insert initial bulk_operations record
    op_id = await db.insert_bulk_operation({
        "user_id": user_id,
        "operation": operation,
        "product_ids": product_ids,
        "params": params,
        "status": "pending",
        "succeeded_count": 0,
        "failed_count": 0,
        "error_details": [],
    })

    results = []
    succeeded = 0
    failed = 0
    error_details = []

    for pid in product_ids:
        try:
            product = await db.fetch_product_by_id(pid)
            if not product:
                results.append({
                    "product_id": pid,
                    "status": "failed",
                    "message": "商品不存在",
                })
                failed += 1
                error_details.append({"product_id": pid, "error": "商品不存在"})
                continue

            # Ownership check: product.seller_name must match user's nickname
            user = await db.fetch_user(user_id)
            if not user or product.get("seller_name") != user.get("nickname"):
                results.append({
                    "product_id": pid,
                    "status": "failed",
                    "message": "无权操作该商品（非本人发布）",
                })
                failed += 1
                error_details.append({"product_id": pid, "error": "无权操作该商品（非本人发布）"})
                continue

            # Apply operation
            message = await _apply_operation(operation, product, params)
            results.append({
                "product_id": pid,
                "status": "success",
                "message": message,
            })
            succeeded += 1

        except ValueError as e:
            results.append({
                "product_id": pid,
                "status": "failed",
                "message": str(e),
            })
            failed += 1
            error_details.append({"product_id": pid, "error": str(e)})
        except Exception as e:
            results.append({
                "product_id": pid,
                "status": "failed",
                "message": f"操作失败: {e}",
            })
            failed += 1
            error_details.append({"product_id": pid, "error": str(e)})

    # Determine overall status
    if failed == 0:
        overall_status = "completed"
    elif succeeded == 0:
        overall_status = "failed"
    else:
        overall_status = "partial"

    # Update the bulk_operations record
    completed_at = datetime.now().isoformat()
    await db.update_bulk_operation(
        op_id,
        status=overall_status,
        succeeded_count=succeeded,
        failed_count=failed,
        error_details=error_details,
        completed_at=completed_at,
    )

    return {
        "operation_id": op_id,
        "operation": operation,
        "status": overall_status,
        "total": len(product_ids),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


async def _apply_operation(operation: str, product: dict, params: dict) -> str:
    """Apply a single operation to a product. Returns success message.

    Raises ValueError on failure.
    """
    pid = product["id"]

    if operation == "publish":
        # Set is_published=1 (using status='active' in this schema)
        # Products use status field: 'active' = published, 'inactive' = unpublished
        await _update_product_status(pid, "active")
        return "已发布"

    elif operation == "unpublish":
        await _update_product_status(pid, "inactive")
        return "已下架"

    elif operation == "price_update":
        return await _apply_price_update(pid, product, params)

    elif operation == "delete":
        # Soft delete: set status to inactive
        await _update_product_status(pid, "inactive")
        return "已删除（软删除）"

    else:
        raise ValueError(f"未知操作类型: {operation}")


async def _update_product_status(product_id: int, status: str) -> bool:
    """Update product status (publish/unpublish/delete use this)."""
    return await db.update_product_field(product_id, "status", status)


async def _apply_price_update(product_id: int, product: dict, params: dict) -> str:
    """Apply price update with percentage or fixed amount.

    Enforces minimum price of ¥1.
    """
    old_price = product.get("price", 0)
    new_price = old_price

    if "percentage" in params:
        pct = float(params["percentage"])
        if pct < -100 or pct > 100:
            raise ValueError(f"百分比必须在-100到100之间，当前值: {pct}")
        # Positive percentage increases price, negative decreases
        new_price = int(round(old_price * (1 + pct / 100)))

    elif "amount" in params:
        amount = int(params["amount"])
        new_price = old_price + amount

    else:
        raise ValueError("price_update 需要 params 中包含 'percentage' 或 'amount'")

    # Enforce minimum price of ¥1
    if new_price < 1:
        new_price = 1
        applied_note = "（已调整为最低价 ¥1）"
    else:
        applied_note = ""

    if new_price == old_price:
        return f"价格未变（¥{old_price}）"

    # Update price and record in price history
    await db.update_product_price(product_id, new_price)
    await db.insert_price_history({
        "product_id": product_id,
        "old_price": old_price,
        "new_price": new_price,
        "reason": f"批量价格更新 ({params})",
    })

    return f"价格 ¥{old_price} → ¥{new_price}{applied_note}"


async def get_bulk_operation_history(user_id: str, page: int = 1, limit: int = 20) -> dict:
    """Get paginated history of bulk operations for a seller."""
    operations, total = await db.fetch_user_bulk_operations(user_id, page=page, limit=limit)

    # Format operations for response
    formatted_ops = []
    for op in operations:
        formatted_ops.append({
            "id": op["id"],
            "operation": op["operation"],
            "status": op["status"],
            "total": op["succeeded_count"] + op["failed_count"],
            "succeeded": op["succeeded_count"],
            "failed": op["failed_count"],
            "created_at": op["created_at"],
            "completed_at": op.get("completed_at"),
        })

    return {
        "operations": formatted_ops,
        "total": total,
        "page": page,
        "limit": limit,
    }
