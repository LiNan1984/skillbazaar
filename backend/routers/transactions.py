from fastapi import APIRouter, Depends, HTTPException, Cookie
from models import TransactionCreate
import services.transaction_service as tx_service
from routers.user_v2 import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("/buy")
async def buy_product(
    body: TransactionCreate,
    user: dict = Depends(get_current_user),
    affiliate_code: str = Cookie(None),
):
    # Identity always comes from the Bearer token; body.buyer_id is deprecated.
    # Affiliate code can come from request body or cookie (set by affiliate link click).
    code = body.affiliate_code or affiliate_code or ""
    try:
        result = await tx_service.buy_product(user["id"], body.product_id, code)
        return {
            "success": True,
            "message": "购买成功",
            "data": result,
        }
    except tx_service.UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except tx_service.ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except tx_service.AlreadyPurchasedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except tx_service.InsufficientBalanceError as e:
        raise HTTPException(status_code=402, detail=str(e))


@router.get("/user/{user_id}")
async def get_user_transactions(
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    # Close the historical IDOR: token identity must match the path id.
    if user_id != user["id"]:
        raise HTTPException(status_code=403, detail="无权查看他人交易记录")
    result = await tx_service.get_user_transactions(user["id"], page, page_size)
    return {"success": True, "data": result}


@router.get("/library/{user_id}")
async def get_user_library(user_id: str, user: dict = Depends(get_current_user)):
    if user_id != user["id"]:
        raise HTTPException(status_code=403, detail="无权查看他人商品库")
    items = await tx_service.get_user_library(user["id"])
    return {"success": True, "data": items, "total": len(items)}
