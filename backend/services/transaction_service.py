from __future__ import annotations

from models import TransactionResponse
import database
import services.user_service as user_service
import services.product_service as product_service


class InsufficientBalanceError(Exception):
    pass


class AlreadyPurchasedError(Exception):
    pass


class ProductNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


async def buy_product(buyer_id: str, product_id: int) -> dict:
    user = await database.fetch_user(buyer_id)
    if user is None:
        raise UserNotFoundError("用户不存在")

    product = await database.fetch_product_by_id(product_id)
    if product is None:
        raise ProductNotFoundError("商品不存在")

    already = await database.check_already_purchased(buyer_id, product_id)
    if already:
        raise AlreadyPurchasedError("您已购买过此商品")

    price = product["price"]
    if user["coins"] < price:
        raise InsufficientBalanceError(f"余额不足，当前余额 {user['coins']} 币，需要 {price} 币")

    new_balance = user["coins"] - price
    await database.update_user_coins(buyer_id, new_balance)

    tx_id = await database.insert_transaction(
        buyer_id=buyer_id,
        seller_id=None,
        product_id=product_id,
        amount=price,
        tx_type="buy",
    )

    # Record wallet transaction
    await database.insert_wallet_transaction({
        "user_id": buyer_id,
        "amount": -price,
        "balance_after": new_balance,
        "type": "buy",
        "ref_type": "product",
        "ref_id": str(product_id),
        "description": f"购买「{product['name']}」 -{price} 金币",
    })

    return {
        "transaction_id": tx_id,
        "product": product,
        "paid_amount": price,
        "remaining_balance": new_balance,
    }


async def get_user_transactions(user_id: str, page: int = 1, page_size: int = 20) -> dict:
    transactions, total = await database.fetch_user_transactions(user_id, page, page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "transactions": [TransactionResponse(**t) for t in transactions],
    }


async def get_user_library(user_id: str) -> list[dict]:
    items = await database.fetch_user_library(user_id)
    return items
