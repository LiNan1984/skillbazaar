from fastapi import APIRouter, HTTPException
from models import TransactionCreate
import services.transaction_service as tx_service

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("/buy")
async def buy_product(body: TransactionCreate):
    try:
        result = await tx_service.buy_product(body.buyer_id, body.product_id)
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
):
    result = await tx_service.get_user_transactions(user_id, page, page_size)
    return {"success": True, "data": result}


@router.get("/library/{user_id}")
async def get_user_library(user_id: str):
    items = await tx_service.get_user_library(user_id)
    return {"success": True, "data": items, "total": len(items)}
