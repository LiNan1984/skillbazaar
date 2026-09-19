"""Skill Bundles v4 service."""
from __future__ import annotations

import services.license_service as license_service
from models import BundleItemResponse, BundleResponse, BundlePurchaseResponse
from models import LicenseType

import database as db


async def create_bundle(seller_id: str, name: str, description: str,
                        product_ids: list[int], discount_percent: float) -> dict:
    """Create a new bundle with given products and discount."""
    # Calculate bundle price from product prices
    total_price = 0
    for pid in product_ids:
        product = await db.fetch_product_by_id(pid)
        if product is None:
            raise ValueError(f"Product {pid} not found")
        total_price += product.get("price", 0)

    bundle_price = int(total_price * (100 - discount_percent) / 100)

    # Create bundle
    bundle = await db.create_bundle(
        seller_id=seller_id,
        name=name,
        description=description,
        discount_percent=discount_percent,
        bundle_price=bundle_price,
    )

    # Add items
    for pid in product_ids:
        await db.add_bundle_item(bundle["id"], pid)

    # Return formatted response
    return await _format_bundle_response(bundle["id"])


async def get_bundle(bundle_id: int) -> dict | None:
    """Get bundle details with items."""
    bundle = await db.fetch_bundle_by_id(bundle_id)
    if bundle is None:
        return None
    return await _format_bundle_response(bundle_id)


async def list_bundles() -> list[dict]:
    """List all active bundles."""
    bundles = await db.fetch_all_bundles()
    result = []
    for bundle in bundles:
        items = await db.fetch_bundle_items(bundle["id"])
        result.append({
            "id": bundle["id"],
            "name": bundle["name"],
            "description": bundle["description"],
            "discount_percent": bundle["discount_percent"],
            "bundle_price": bundle["bundle_price"],
            "seller_name": bundle.get("seller_name", ""),
            "item_count": len(items),
            "is_active": bool(bundle.get("is_active", 1)),
            "created_at": bundle.get("created_at"),
        })
    return result


async def purchase_bundle(bundle_id: int, buyer_id: str) -> dict:
    """Purchase a bundle - grants licenses for all included products."""
    bundle = await db.fetch_bundle_by_id(bundle_id)
    if bundle is None:
        raise ValueError("Bundle not found")

    if not bundle.get("is_active", 1):
        raise ValueError("Bundle is not active")

    items = await db.fetch_bundle_items(bundle_id)
    if not items:
        raise ValueError("Bundle has no items")

    # Create licenses for each product
    created_licenses = []
    for item in items:
        license_info = await license_service.create_license(
            user_id=buyer_id,
            product_id=item["product_id"],
            license_type=LicenseType.PERMANENT,
        )
        created_licenses.append(license_info)

    # Record transaction
    txn_id = await db.insert_transaction(
        buyer_id=buyer_id,
        seller_id=bundle.get("seller_id"),
        product_id=bundle_id,
        amount=bundle["bundle_price"],
        tx_type="buy",
    )

    return {
        "id": txn_id,
        "status": "completed",
        "items_count": len(items),
    }


async def add_skill_to_bundle(bundle_id: int, product_id: int, seller_id: str) -> dict:
    """Add a skill to an existing bundle and recalculate price."""
    bundle = await db.fetch_bundle_by_id(bundle_id)
    if bundle is None:
        raise ValueError("Bundle not found")

    if bundle.get("seller_id") != seller_id:
        raise PermissionError("Not authorized to modify this bundle")

    # Check product exists
    product = await db.fetch_product_by_id(product_id)
    if product is None:
        raise ValueError("Product not found")

    # Check not already in bundle
    existing = await db.fetch_bundle_item(bundle_id, product_id)
    if existing:
        raise ValueError("Product already in bundle")

    # Add item
    await db.add_bundle_item(bundle_id, product_id)

    # Recalculate price
    items = await db.fetch_bundle_items(bundle_id)
    total_price = 0
    for item in items:
        total_price += item.get("product_price", 0)

    discount = bundle.get("discount_percent", 0)
    new_price = int(total_price * (100 - discount) / 100)
    await db.update_bundle_price(bundle_id, new_price)

    return await _format_bundle_response(bundle_id)


async def remove_skill_from_bundle(bundle_id: int, product_id: int, seller_id: str) -> dict:
    """Remove a skill from a bundle and recalculate price."""
    bundle = await db.fetch_bundle_by_id(bundle_id)
    if bundle is None:
        raise ValueError("Bundle not found")

    if bundle.get("seller_id") != seller_id:
        raise PermissionError("Not authorized to modify this bundle")

    # Check product is in bundle
    existing = await db.fetch_bundle_item(bundle_id, product_id)
    if not existing:
        raise ValueError("Product not in bundle")

    # Remove item
    await db.remove_bundle_item(bundle_id, product_id)

    # Recalculate price
    items = await db.fetch_bundle_items(bundle_id)
    total_price = 0
    for item in items:
        total_price += item.get("product_price", 0)

    discount = bundle.get("discount_percent", 0)
    new_price = int(total_price * (100 - discount) / 100)
    await db.update_bundle_price(bundle_id, new_price)

    return await _format_bundle_response(bundle_id)


async def _format_bundle_response(bundle_id: int) -> dict:
    """Format bundle with items for API response."""
    bundle = await db.fetch_bundle_by_id(bundle_id)
    if bundle is None:
        return None

    items = await db.fetch_bundle_items(bundle_id)
    item_list = []
    for item in items:
        item_list.append(BundleItemResponse(
            product_id=item["product_id"],
            product_name=item.get("product_name", ""),
            product_price=item.get("product_price", 0),
        ))

    return {
        "id": bundle["id"],
        "seller_id": bundle.get("seller_id", ""),
        "name": bundle["name"],
        "description": bundle.get("description", ""),
        "discount_percent": bundle.get("discount_percent", 0),
        "bundle_price": bundle.get("bundle_price", 0),
        "items": [it.dict() for it in item_list],
        "is_active": bool(bundle.get("is_active", 1)),
        "created_at": bundle.get("created_at"),
    }
