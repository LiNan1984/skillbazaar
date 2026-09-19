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
    compat: Optional[str] = None  # JSON array of runtime strings


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
    compat: Optional[str] = None  # JSON array of runtime strings
    status: str
    created_at: Optional[str] = None
    eval_report: Optional[dict] = None  # Latest evaluation report


class ProductList(BaseModel):
    total: int
    page: int
    page_size: int
    products: List[ProductResponse]


class EvalReportResponse(BaseModel):
    product_id: int
    eval_score: int
    status: str
    eval_version: int
    flags: List[str] = []
    static_flags: List[str] = []
    sample_output: Optional[str] = None
    reason: Optional[str] = None


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
    # Identity comes from the Bearer token; buyer_id in the body is deprecated
    # and ignored (kept tolerant so legacy clients get a clean 401, not a 422).
    product_id: int
    affiliate_code: str = ""



class TransactionResponse(BaseModel):
    id: int
    buyer_id: str
    seller_id: Optional[str] = None
    product_id: int
    amount: int
    type: str
    status: str
    created_at: Optional[str] = None


# ---------- Product Reviews ----------

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, strict=True)
    content: str = Field("", max_length=500)


# ---------- Chat Models ----------

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None  # kept for backward compat; identity comes from Bearer token
    card: Optional[dict] = None


class ChatProductCard(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    price: Optional[int] = None
    rating: Optional[float] = None
    description: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    products: List[ChatProductCard] = []
    card: Optional[dict] = None


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


# ---------- Profile Models ----------

class ProfileResponse(BaseModel):
    id: str
    username: str
    nickname: str
    avatar: str
    role: str
    display_name: str
    bio: str
    location: Optional[str] = None
    website_url: Optional[str] = None
    avatar_url: Optional[str] = None
    social_links: list = []
    badges: list = []
    verified: bool = False
    industry: Optional[str] = None
    interests: list = []
    city: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website_url: Optional[str] = None
    avatar_url: Optional[str] = None
    social_links: Optional[list] = None
    industry: Optional[str] = None
    interests: Optional[list] = None
    city: Optional[str] = None
    language: Optional[str] = None


class FollowResponse(BaseModel):
    following_id: str
    is_following: bool


class UserProductResponse(BaseModel):
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


class SkillVersionCreate(BaseModel):
    changelog: str = ""
    content_preview: Optional[str] = None


class SkillVersionResponse(BaseModel):
    id: int
    product_id: int
    version: str
    changelog: str
    content_preview: Optional[str] = None
    is_current: bool
    created_at: Optional[str] = None
    created_by: Optional[str] = None


class SkillVersionList(BaseModel):
    versions: list[SkillVersionResponse]


class SkillRollbackRequest(BaseModel):
    target_version: str


class SkillExecutionRequest(BaseModel):
    product_id: int
    user_id: Optional[str] = None
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
    role: str = "user"


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


# ---------- Cron Subscription Models ----------

class CronProductCreate(BaseModel):
    product_id: int
    schedule_cron: str
    result_format: str = "json"

class CronProductResponse(BaseModel):
    id: int
    product_id: int
    schedule_cron: str
    result_format: str
    status: str
    last_executed_at: Optional[str] = None
    avg_duration_ms: int = 0
    subscriber_count: int = 0
    execution_count: int = 0
    created_at: Optional[str] = None

class CronSubscriptionResponse(BaseModel):
    id: int
    cron_product_id: int
    subscriber_id: str
    status: str
    subscribed_at: Optional[str] = None
    expires_at: Optional[str] = None
    monthly_price: int = 0
    webhook_url: Optional[str] = None
    api_token: Optional[str] = None
    last_result_at: Optional[str] = None

class CronPushRequest(BaseModel):
    payload: str
    executed_at: Optional[str] = None
    duration_ms: int = 0

class CronExecutionLogResponse(BaseModel):
    id: int
    cron_product_id: int
    subscription_id: Optional[int] = None
    payload: Optional[str] = None
    status: str
    executed_at: Optional[str] = None
    duration_ms: int = 0


# ---------- Activity & Points Models ----------

class ActivityResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    type: str
    start_at: str
    end_at: str
    status: str

class ActivityTaskResponse(BaseModel):
    id: int
    activity_id: int
    task_key: str
    name: str
    description: Optional[str] = None
    task_type: str
    action: str
    target_count: int
    reward_points: int
    reward_coins: int
    icon: Optional[str] = None
    progress: int = 0
    completed: bool = False
    reward_claimed: bool = False

class CheckinResponse(BaseModel):
    ok: bool
    message: str = ""
    points: int = 0
    streak: int = 0
    bonus: int = 0

class PointAccountResponse(BaseModel):
    user_id: str
    balance: int
    total_earned: int
    total_spent: int
    level: int
    continuous_checkin_days: int
    last_checkin_at: Optional[str] = None

class PointRedeemRequest(BaseModel):
    amount: int = Field(gt=0)
    redeem_type: str = "coins"

class LeaderboardEntry(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    total_earned: int
    level: int


# ---------- User Agent Models ----------

class UserAgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    skill_ids: list[int] = []

class UserAgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    skill_ids: Optional[list[int]] = None
    status: Optional[str] = None

class UserAgentResponse(BaseModel):
    id: int
    user_id: str
    name: str
    description: str
    system_prompt: str
    skill_ids: str
    agent_config: str
    status: str
    runs_count: int = 0
    last_run_at: Optional[str] = None
    created_at: Optional[str] = None

class AgentRunRequest(BaseModel):
    input_text: str = ""

class AgentRunResponse(BaseModel):
    id: int
    agent_id: int
    trigger_type: str
    input_text: str
    output_text: str
    tokens_used: int = 0
    status: str
    created_at: Optional[str] = None


# ---------- Analytics Models ----------

class DailyAnalytics(BaseModel):
    date: str
    views: int
    unique_visitors: int
    cart_adds: int
    purchases: int
    revenue_cents: int
    conversion_rate: float


class TrafficSource(BaseModel):
    source: str
    visits: int
    conversions: int
    conversion_rate: float


class TopProduct(BaseModel):
    product_id: int
    product_name: str
    views: int
    purchases: int
    revenue_cents: int


class SellerDashboardResponse(BaseModel):
    total_views: int
    total_purchases: int
    total_revenue_cents: int
    avg_conversion_rate: float
    top_products: List[TopProduct]


class ProductAnalyticsResponse(BaseModel):
    product_id: int
    product_name: str
    analytics: List[DailyAnalytics]


class ProductAnalyticsListResponse(BaseModel):
    product_id: int
    product_name: str
    analytics: List[dict]


# ---------- Payment Models ----------

class PaymentOrderCreate(BaseModel):
    product_id: int
    channel: str = "alipay"


class PaymentOrderResponse(BaseModel):
    id: int
    user_id: str
    product_id: int
    direction: str
    channel: str
    external_txn_id: Optional[str] = None
    amount_cents: int
    coins_amount: int = 0
    exchange_rate: float = 1.0
    platform_fee_cents: int = 0
    status: str
    gateway_response: dict = {}
    failure_reason: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PaymentCallbackRequest(BaseModel):
    payment_id: int
    external_txn_id: str
    status: str
    amount: int


class WithdrawalRequest(BaseModel):
    amount_coins: int
    channel: str
    account_info: dict


class WithdrawalResponse(BaseModel):
    id: int
    user_id: str
    amount_cents: int
    coins_deducted: int
    channel: str
    account_info: dict
    status: str
    processed_at: Optional[str] = None
    admin_note: str = ""
    created_at: Optional[str] = None


class PaymentHistoryResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int


class EarningsSummaryResponse(BaseModel):
    total_earnings_cents: int
    available_balance_cents: int
    withdrawn_cents: int
    pending_withdrawal_cents: int = 0


class PaymentMethodCreate(BaseModel):
    channel: str
    account_ref: str
    account_name: str = ""


class PaymentMethodResponse(BaseModel):
    id: int
    user_id: str
    channel: str
    account_ref: str
    account_name: str
    is_verified: bool = False
    is_default: bool = False
    created_at: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = ""
    filters: dict = {}


class SearchResponse(BaseModel):
    results: list[dict]
    total: int


# ---------- Bundle v4 Models ----------


class BundleItemResponse(BaseModel):
    product_id: int
    product_name: str = ""
    product_price: int = 0


class BundleCreate(BaseModel):
    name: str
    description: str = ""
    product_ids: list[int]
    discount_percent: float = 0


class BundleResponse(BaseModel):
    id: int
    seller_id: str = ""
    name: str
    description: str = ""
    discount_percent: float = 0
    bundle_price: int = 0
    items: list[dict] = []
    is_active: bool = True
    created_at: Optional[str] = None


class BundlePurchaseResponse(BaseModel):
    id: int
    status: str
    items_count: int


class BundleListResponse(BaseModel):
    bundles: list[dict]


# ---------- Agent v4 Models ----------


class UserAgentV4Response(BaseModel):
    id: int
    owner_id: str
    name: str
    description: str
    model: str
    skills: list[dict] = []
    created_at: Optional[str] = None


class AgentSkillInfo(BaseModel):
    product_id: int
    name: str
    price: int
    category: str


class SkillAdd(BaseModel):
    product_id: int


# ---------- Analytics v4 Models ----------


class ProductAnalyticsDashboard(BaseModel):
    views: int
    purchases: int
    conversion_rate: float
    revenue: int


class CategoryAnalyticsItem(BaseModel):
    category: str
    product_count: int
    total_views: int = 0
    total_purchases: int = 0
    revenue: int = 0


class SellerAnalyticsResponse(BaseModel):
    total_products: int
    total_views: int
    total_purchases: int
    total_revenue: int
    avg_conversion_rate: float
    top_products: list[dict]


class CategoryAnalyticsResponse(BaseModel):
    categories: list[CategoryAnalyticsItem]


class PlatformOverviewResponse(BaseModel):
    total_users: int
    total_products: int
    total_revenue: int
    top_categories: list[dict]


# ---------- Search v4 Models ----------


class SearchFilters(BaseModel):
    query: str = ""
    category: str = ""
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_rating: Optional[float] = None
    sort_by: str = "relevance"
    page: int = 1
    page_size: int = 20


class SavedSearchCreate(BaseModel):
    name: str
    query: str = ""
    filters: dict = {}


class SaveSearchRequest(SavedSearchCreate):
    """Alias for SavedSearchCreate (backward compat)."""


class SavedSearchResponse(BaseModel):
    id: int
    user_id: str
    name: str
    query: str = ""
    filters: dict
    created_at: Optional[str] = None


class SaveSearchResponse(SavedSearchResponse):
    """Alias for SavedSearchResponse (backward compat)."""


# ===========================================================================
# v4.3 – Wishlist & Recommendations
# ===========================================================================

class WishlistItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str = ""
    price: int = 0
    category: str = ""
    seller_name: str = ""
    created_at: Optional[str] = None


class WishlistListResponse(BaseModel):
    items: list[dict]


class RecommendationItemResponse(BaseModel):
    product_id: int
    name: str = ""
    price: int = 0
    category: str = ""
    seller_name: str = ""
    views: int = 0
    purchases: int = 0
    co_purchase_count: int = 0


class RecommendationsResponse(BaseModel):
    recommendations: list[dict]


# ===========================================================================
# v4.4 – Affiliate Program
# ===========================================================================

class AffiliateLinkCreate(BaseModel):
    product_id: int
    commission_rate: float = 10.0


class AffiliateLinkResponse(BaseModel):
    id: int
    product_id: int
    code: str
    link: str
    commission_rate: float = 10.0


class AffiliateStatsResponse(BaseModel):
    clicks: int
    conversions: int
    commission_earned: int
    conversion_rate: float


# ===========================================================================
# v4.5 – Semantic Search
# ===========================================================================


class SemanticSearchRequest(BaseModel):
    query: str = Field("", min_length=0, description="Search query text")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class SemanticSearchResponse(BaseModel):
    results: list[dict]


# ===========================================================================
# v4.5.1 – Smart Pricing Suggestions
# ===========================================================================


class PriceRange(BaseModel):
    min: int
    max: int


class PricingSuggestRequest(BaseModel):
    product_id: Optional[int] = None
    category: Optional[str] = None


class PricingSuggestionResponse(BaseModel):
    suggested_price: int
    price_range: PriceRange
    reason: str
    market_avg: float
    competitors_count: int
    confidence: Optional[str] = None


class PricingTrendResponse(BaseModel):
    category: str
    avg_price: float
    min_price: int
    max_price: int
    price_trend: str
    sample_count: int
    period_days: int


# ===========================================================================
# v4.6 – Traffic Boost
# ===========================================================================


class ProductStatsItem(BaseModel):
    product_id: int
    product_name: str = ""
    views: int = 0
    purchases: int = 0
    revenue_cents: int = 0
    boost_score: int = 0


class SellerStatsResponse(BaseModel):
    seller_id: str
    total_products: int
    total_views: int
    total_downloads: int = 0
    total_sales: int = 0
    total_revenue: int = 0
    avg_conversion_rate: float
    top_products: list[ProductStatsItem] = []


class BoostDecayResponse(BaseModel):
    decayed_count: int = 0
    reset_count: int = 0


class BoostResetResponse(BaseModel):
    product_id: int
    boost_score: int
