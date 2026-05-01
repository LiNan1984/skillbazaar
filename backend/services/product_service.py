from __future__ import annotations

from models import ProductResponse, ProductList
import database


async def get_products(
    category: str | None = None,
    sub_category: str | None = None,
    keyword: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    sort_by: str = "downloads",
    page: int = 1,
    page_size: int = 20,
) -> ProductList:
    products, total = await database.fetch_products(
        category=category,
        sub_category=sub_category,
        keyword=keyword,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    return ProductList(
        total=total,
        page=page,
        page_size=page_size,
        products=[ProductResponse(**p) for p in products],
    )


async def get_product_by_id(product_id: int) -> ProductResponse | None:
    product = await database.fetch_product_by_id(product_id)
    if product is None:
        return None
    return ProductResponse(**product)


async def create_product(data: dict) -> ProductResponse:
    product_id = await database.insert_product(data)
    product = await database.fetch_product_by_id(product_id)
    return ProductResponse(**product)


async def get_category_tree() -> list[dict]:
    return await database.fetch_category_tree()
