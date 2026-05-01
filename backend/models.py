from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class ProductCategory(str, Enum):
    AGENT = "Agent"
    SKILL = "Skill"
    CRON = "Cron"
    WORKFLOW = "Workflow"


class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TransactionStatus(str, Enum):
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"


# ---------- Product Models ----------

class Product(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    category: str
    sub_category: Optional[str] = None
    price: int
    original_price: Optional[int] = None
    seller_name: str
    seller_avatar: Optional[str] = None
    rating: float = 4.0
    downloads: int = 0
    sales: int = 0
    tags: str = "[]"
    source_platform: Optional[str] = None
    github_url: Optional[str] = None
    icon: Optional[str] = None
    content_preview: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None


class ProductCreate(BaseModel):
    name: str
    description: str
    category: str
    sub_category: Optional[str] = None
    price: int = Field(gt=0)
    original_price: Optional[int] = None
    seller_name: str
    seller_avatar: Optional[str] = None
    tags: str = "[]"
    source_platform: Optional[str] = None
    github_url: Optional[str] = None
    icon: Optional[str] = None
    content_preview: Optional[str] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str
    category: str
    sub_category: Optional[str] = None
    price: int
    original_price: Optional[int] = None
    seller_name: str
    seller_avatar: Optional[str] = None
    rating: float
    downloads: int
    sales: int
    tags: str
    source_platform: Optional[str] = None
    github_url: Optional[str] = None
    icon: Optional[str] = None
    content_preview: Optional[str] = None
    status: str
    created_at: Optional[str] = None


class ProductList(BaseModel):
    total: int
    page: int
    page_size: int
    products: List[ProductResponse]


# ---------- User Models ----------

class User(BaseModel):
    id: str
    nickname: str
    avatar: str
    coins: int = 10000
    created_at: Optional[str] = None


class UserCreate(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    nickname: str
    avatar: str
    coins: int
    created_at: Optional[str] = None


# ---------- Transaction Models ----------

class Transaction(BaseModel):
    id: Optional[int] = None
    buyer_id: str
    seller_id: Optional[str] = None
    product_id: int
    amount: int
    type: str
    status: str = "completed"
    created_at: Optional[str] = None


class TransactionCreate(BaseModel):
    buyer_id: str
    product_id: int


class TransactionResponse(BaseModel):
    id: int
    buyer_id: str
    seller_id: Optional[str] = None
    product_id: int
    amount: int
    type: str
    status: str
    created_at: Optional[str] = None


# ---------- Chat Models ----------

class ChatRequest(BaseModel):
    message: str
    user_id: str


class ChatResponse(BaseModel):
    reply: str
    products: List[ProductResponse] = []


# ---------- Filter Models ----------

class CategoryFilter(BaseModel):
    category: Optional[str] = None
    sub_category: Optional[str] = None
    keyword: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    sort_by: Optional[str] = "downloads"
    page: int = 1
    page_size: int = 20


# ---------- Skill Asset Models ----------

class SkillType(str, Enum):
    PROMPT = "prompt"
    CODE = "code"
    SDK = "sdk"


class SkillUploadRequest(BaseModel):
    skill_type: SkillType
    skill_meta: Optional[str] = None
    sdk_endpoint: Optional[str] = None


class SkillAssetResponse(BaseModel):
    id: int
    product_id: int
    skill_type: str
    skill_meta: Optional[str] = None
    file_size: Optional[int] = None
    version: str = "1.0.0"
    created_at: Optional[str] = None


class SkillExecutionRequest(BaseModel):
    product_id: int
    user_id: str
    input_params: Optional[str] = None


# ---------- License Models ----------

class LicenseType(str, Enum):
    PERMANENT = "permanent"
    TRIAL = "trial"
    SUBSCRIPTION = "subscription"


class LicenseCreate(BaseModel):
    product_id: int
    user_id: str
    license_type: LicenseType = LicenseType.PERMANENT
    max_calls: Optional[int] = None


class LicenseResponse(BaseModel):
    id: int
    user_id: str
    product_id: int
    license_type: str
    license_token: str
    expires_at: Optional[str] = None
    max_calls: Optional[int] = None
    calls_count: int = 0
    status: str
    created_at: Optional[str] = None


class LicenseVerifyRequest(BaseModel):
    license_token: str
    product_id: int


class LicenseVerifyResponse(BaseModel):
    valid: bool
    license_type: Optional[str] = None
    calls_remaining: Optional[int] = None
    expires_at: Optional[str] = None


# ---------- Auth Models ----------

class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    user_id: str
    username: str
    nickname: str
    token: str
    coins: int = 10000


# ---------- Profile Models ----------

class ProfileUpdate(BaseModel):
    industry: Optional[str] = None
    interests: Optional[list] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    bio: Optional[str] = None
    preferred_categories: Optional[list] = None


# ---------- Wallet Models ----------

class RechargeRequest(BaseModel):
    user_id: str
    promo_code: str


class WalletHistoryResponse(BaseModel):
    total: int
    page: int
    transactions: list


# ---------- Behavior Models ----------

class BehaviorLog(BaseModel):
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    metadata: Optional[dict] = None


# ---------- Notification Models ----------

class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    content: str
    is_read: bool
    created_at: Optional[str] = None


# ---------- Pricing Models ----------

class PricingModel(str, Enum):
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    AUCTION = "auction"


class PricingUpdate(BaseModel):
    pricing_model: PricingModel = PricingModel.FIXED


class PriceHistoryResponse(BaseModel):
    id: int
    product_id: int
    old_price: int
    new_price: int
    pricing_model: str
    demand_score: float
    reason: str
    created_at: Optional[str] = None


class DynamicPriceResponse(BaseModel):
    product_id: int
    current_price: int
    base_price: int
    pricing_model: str
    demand_score: float
    price_trend: str  # "up", "down", "stable"


# ---------- Bounty Models ----------

class BountyCreate(BaseModel):
    title: str
    description: str
    category: str = "Skill"
    tags: Optional[list] = []
    budget_min: int = Field(gt=0)
    budget_max: int = Field(gt=0)
    deadline: Optional[str] = None
    skill_type: str = "prompt"
    requirements: Optional[str] = None


class BountyResponse(BaseModel):
    id: int
    poster_id: str
    poster_name: Optional[str] = None
    poster_avatar: Optional[str] = None
    title: str
    description: str
    category: str
    tags: str
    budget_min: int
    budget_max: int
    deadline: Optional[str] = None
    status: str
    selected_developer_id: Optional[str] = None
    final_price: Optional[int] = None
    skill_type: str
    requirements: Optional[str] = None
    application_count: Optional[int] = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BountyApplicationCreate(BaseModel):
    bounty_id: int
    proposal: str
    estimated_days: int = 7
    quoted_price: int = Field(gt=0)
    portfolio: Optional[str] = None


class BountyApplicationResponse(BaseModel):
    id: int
    bounty_id: int
    developer_id: str
    developer_name: Optional[str] = None
    developer_avatar: Optional[str] = None
    proposal: str
    estimated_days: int
    quoted_price: int
    portfolio: Optional[str] = None
    status: str
    created_at: Optional[str] = None


class BountyDeliveryCreate(BaseModel):
    bounty_id: int
    description: Optional[str] = None


class BountyDeliveryResponse(BaseModel):
    id: int
    bounty_id: int
    developer_id: str
    developer_name: Optional[str] = None
    description: str
    status: str
    created_at: Optional[str] = None


class BountyAcceptRequest(BaseModel):
    application_id: int


class BountyReviewRequest(BaseModel):
    delivery_id: int
    accept: bool
