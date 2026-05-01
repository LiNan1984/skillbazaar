from __future__ import annotations

import uuid
import random
from models import UserResponse
import database

NICKNAMES = [
    "创意旅人", "代码诗人", "数据探索者", "AI调教师", "自动化达人",
    "技能收集者", "区块链先锋", "策略交易员", "市场观察家", "效率专家",
]

AVATAR_STYLES = [
    "adventurer", "avataaars", "bottts", "croodles", "fun-emoji",
    "lorelei", "micah", "notionists", "open-peeps", "personas",
]


def _random_avatar() -> str:
    style = random.choice(AVATAR_STYLES)
    seed = random.randint(1, 9999)
    return f"https://api.dicebear.com/7.x/{style}/svg?seed={seed}"


async def create_anonymous_user(nickname: str | None = None, avatar: str | None = None) -> UserResponse:
    user_id = str(uuid.uuid4())
    if not nickname:
        nickname = random.choice(NICKNAMES)
    if not avatar:
        avatar = _random_avatar()

    user_data = await database.insert_user(user_id, nickname, avatar)
    return UserResponse(**user_data)


async def get_user(user_id: str) -> UserResponse | None:
    user = await database.fetch_user(user_id)
    if user is None:
        return None
    return UserResponse(**user)


async def update_coins(user_id: str, coins: int) -> UserResponse | None:
    user = await database.fetch_user(user_id)
    if user is None:
        return None
    new_balance = user["coins"] + coins
    if new_balance < 0:
        return None
    success = await database.update_user_coins(user_id, new_balance)
    if not success:
        return None
    user["coins"] = new_balance
    return UserResponse(**user)
