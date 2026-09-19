# Skill Subscription System — v4.7 Feature Spec

## 1. Overview

Implement a subscription-based monetization model for Skills on SkillBazaar. Sellers can offer Skills on a recurring subscription basis (weekly/monthly/yearly), providing passive recurring revenue instead of one-time purchases. Buyers subscribe to access Skills continuously.

## 2. Problem Statement

**Seller Pain Point #4**: "收入不稳定 — 一次性付费收入不可持续"
- Buyers pay once and own forever → no recurring revenue
- Sellers must continuously acquire new customers
- High-quality Skills that require ongoing maintenance have no ongoing income

**Buyer Pain Point #6**: "买断制不适合试用 — 一次性付费决策压力大"
- Full price upfront for untested Skills is risky
- Subscription lowers the barrier to entry

## 3. Goals

1. Allow sellers to publish Skills with subscription pricing (weekly/monthly/yearly tiers)
2. Allow buyers to subscribe to Skills with automatic renewal
3. Track subscription lifecycle (active, expired, cancelled)
4. Provide sellers with subscription revenue analytics
5. Maintain backward compatibility with one-time purchase model

## 4. Scope

### In Scope
- Subscription product type alongside existing one-time purchase
- Subscription lifecycle management (create, renew, cancel, expire)
- Subscription access control (check active subscription before granting access)
- Seller subscription analytics (active subscribers, MRR, churn)
- Subscription notification (renewal reminders, expiry warnings)
- Cron job for subscription expiry processing

### Out of Scope (Future)
- Free trial periods
- Plan upgrades/downgrades mid-subscription
- Prorated billing
- Refund processing for subscriptions
- Gift subscriptions

## 5. Database Schema

### 5.1 New Table: `subscriptions`

```sql
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,           -- Subscriber (buyer)
    product_id INTEGER NOT NULL,     -- The Skill being subscribed to
    plan TEXT NOT NULL,              -- 'weekly' | 'monthly' | 'yearly'
    price INTEGER NOT NULL,          -- Price in coins per period
    status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'cancelled' | 'expired'
    starts_at TEXT NOT NULL,         -- ISO datetime
    expires_at TEXT NOT NULL,        -- ISO datetime
    auto_renew INTEGER DEFAULT 1,    -- 1=auto-renew, 0=manual
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_product ON subscriptions(product_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
```

### 5.2 Modified Table: `products`

Add subscription configuration fields to existing products table:

```sql
ALTER TABLE products ADD COLUMN subscription_plans TEXT DEFAULT '[]';  -- JSON: [{"plan":"monthly","price":50}]
ALTER TABLE products ADD COLUMN is_subscription INTEGER DEFAULT 0;    -- 1=subscription, 0=one-time
```

### 5.3 New Table: `subscription_events`

Track subscription lifecycle events for analytics:

```sql
CREATE TABLE IF NOT EXISTS subscription_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,        -- 'created' | 'renewed' | 'cancelled' | 'expired' | 'payment_failed'
    amount INTEGER,                  -- Coins charged (for payment events)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
);
```

## 6. API Endpoints

### 6.1 POST `/api/v4/subscriptions/create`

Create a new subscription for a product.

**Auth**: Required (buyer)
**Request**:
```json
{
    "product_id": 123,
    "plan": "monthly"
}
```

**Response**:
```json
{
    "subscription_id": 1,
    "product_id": 123,
    "plan": "monthly",
    "price": 50,
    "status": "active",
    "starts_at": "2025-01-15T00:00:00",
    "expires_at": "2025-02-15T00:00:00",
    "auto_renew": true
}
```

**Business Rules**:
- User must have sufficient balance for at least one period
- If user already has an active subscription for this product, return existing subscription
- Deduct coins immediately upon creation

### 6.2 GET `/api/v4/subscriptions/my`

List current user's active subscriptions.

**Auth**: Required
**Response**:
```json
{
    "subscriptions": [
        {
            "subscription_id": 1,
            "product_id": 123,
            "product_name": "Data Analyzer",
            "plan": "monthly",
            "price": 50,
            "status": "active",
            "expires_at": "2025-02-15T00:00:00",
            "auto_renew": true
        }
    ]
}
```

### 6.3 POST `/api/v4/subscriptions/{subscription_id}/cancel`

Cancel an active subscription. Access continues until `expires_at`.

**Auth**: Required (subscriber only)
**Response**:
```json
{
    "ok": true,
    "subscription_id": 1,
    "status": "cancelled",
    "expires_at": "2025-02-15T00:00:00"
}
```

### 6.4 POST `/api/v4/subscriptions/{subscription_id}/toggle-renew`

Toggle auto-renew on/off.

**Auth**: Required (subscriber only)
**Response**:
```json
{
    "ok": true,
    "subscription_id": 1,
    "auto_renew": false
}
```

### 6.5 POST `/api/v4/cron/process-subscriptions`

Cron endpoint: process subscription renewals and expirations.

**Auth**: None (internal cron)
**Response**:
```json
{
    "renewed_count": 15,
    "expired_count": 3,
    "payment_failed_count": 1,
    "message": "Processed 19 subscriptions"
}
```

**Logic**:
1. Find all `active` subscriptions where `expires_at < now` AND `auto_renew = 1`
2. Attempt renewal: deduct coins, extend `expires_at`, record event
3. For failed renewals (insufficient balance): mark status, record event, notify user
4. Find all `active` subscriptions where `expires_at < now` AND `auto_renew = 0` → mark expired

### 6.6 GET `/api/v4/seller/subscription-stats`

Get subscription analytics for seller's products.

**Auth**: Required (seller)
**Response**:
```json
{
    "total_subscribers": 45,
    "active_subscriptions": 38,
    "monthly_recurring_revenue": 1900,
    "churn_rate": 0.13,
    "by_plan": {
        "weekly": {"count": 5, "revenue": 250},
        "monthly": {"count": 30, "revenue": 1500},
        "yearly": {"count": 3, "revenue": 450}
    },
    "top_products": [
        {"product_id": 123, "name": "Data Analyzer", "subscribers": 20, "mrr": 1000}
    ]
}
```

### 6.7 GET `/api/v4/subscriptions/check`

Check if user has active subscription for a product (used by execution/access layer).

**Auth**: Required
**Query Params**: `product_id`
**Response**:
```json
{
    "has_subscription": true,
    "subscription_id": 1,
    "plan": "monthly",
    "expires_at": "2025-02-15T00:00:00",
    "days_remaining": 28
}
```

## 7. Service Layer

### 7.1 `subscription_service.py`

```python
async def create_subscription(user_id: str, product_id: int, plan: str) -> dict:
    """Create a new subscription or return existing active one."""

async def cancel_subscription(subscription_id: int, user_id: str) -> dict:
    """Cancel subscription (effective at expiry)."""

async def toggle_auto_renew(subscription_id: int, user_id: str) -> dict:
    """Toggle auto-renew flag."""

async def get_my_subscriptions(user_id: str) -> list[dict]:
    """Get all active subscriptions for a user."""

async def check_subscription(user_id: str, product_id: int) -> dict | None:
    """Check if user has active subscription for product."""

async def process_renewals() -> dict:
    """Cron: process subscription renewals and expirations."""

async def get_seller_subscription_stats(seller_id: str) -> dict:
    """Get subscription analytics for seller's products."""
```

## 8. Models (`models.py`)

```python
class SubscriptionPlan(BaseModel):
    plan: str          # "weekly" | "monthly" | "yearly"
    price: int         # coins per period

class SubscriptionCreateRequest(BaseModel):
    product_id: int
    plan: str

class SubscriptionResponse(BaseModel):
    subscription_id: int
    product_id: int
    plan: str
    price: int
    status: str
    starts_at: str
    expires_at: str
    auto_renew: bool = True

class SubscriptionListResponse(BaseModel):
    subscriptions: list[SubscriptionResponse]

class SubscriptionCheckResponse(BaseModel):
    has_subscription: bool
    subscription_id: int | None = None
    plan: str | None = None
    expires_at: str | None = None
    days_remaining: int | None = None

class SubscriptionProcessResponse(BaseModel):
    renewed_count: int = 0
    expired_count: int = 0
    payment_failed_count: int = 0
    message: str

class SellerSubscriptionStatsResponse(BaseModel):
    total_subscribers: int
    active_subscriptions: int
    monthly_recurring_revenue: int
    churn_rate: float
    by_plan: dict[str, dict]
    top_products: list[dict]
```

## 9. Access Control Integration

The execution/access layer should check for active subscription before granting access:

```python
async def can_access_product(user_id: str, product_id: int) -> bool:
    """Check if user can access a product (purchased OR active subscription)."""
    # Check one-time purchase
    purchased = await check_already_purchased(user_id, product_id)
    if purchased:
        return True
    # Check active subscription
    sub = await subscription_service.check_subscription(user_id, product_id)
    return sub is not None and sub["status"] == "active"
```

## 10. Pricing

| Plan | Duration | Example Price (coins) |
|------|----------|----------------------|
| weekly | 7 days | 15 |
| monthly | 30 days | 50 |
| yearly | 365 days | 500 |

Conversion discount: yearly = monthly × 10 (≈ 17% discount)

## 11. Test Plan

### Test Coverage (8 tests minimum)

| ID | Test Name | What It Verifies |
|----|-----------|------------------|
| SB-01 | `test_create_subscription` | Creates subscription, deducts coins, returns correct data |
| SB-02 | `test_duplicate_subscription_returns_existing` | Cannot create duplicate active subscription |
| SB-03 | `test_cancel_subscription` | Cancels subscription, access continues until expiry |
| SB-04 | `test_toggle_auto_renew` | Toggles auto-renew flag |
| SB-05 | `test_list_my_subscriptions` | Returns user's active subscriptions with product info |
| SB-06 | `test_cron_renews_expired_active_subs` | Cron extends expiry for auto-renew subs |
| SB-07 | `test_cron_expires_non_renew_subs` | Cron marks manual subs as expired |
| SB-08 | `test_seller_subscription_stats` | Returns correct MRR and subscriber counts |
| SB-09 | `test_check_subscription_access` | Verifies subscription grants product access |
| SB-10 | `test_insufficient_balance_rejected` | Cannot subscribe without sufficient coins |

## 12. Implementation Phases

### Phase 1: Database & Models
- Add `subscriptions` and `subscription_events` tables
- Add `subscription_plans` and `is_subscription` to products
- Add Pydantic models

### Phase 2: Core Subscription API
- `POST /api/v4/subscriptions/create`
- `GET /api/v4/subscriptions/my`
- `POST /api/v4/subscriptions/{id}/cancel`
- `POST /api/v4/subscriptions/{id}/toggle-renew`
- `GET /api/v4/subscriptions/check`

### Phase 3: Cron & Analytics
- `POST /api/v4/cron/process-subscriptions`
- `GET /api/v4/seller/subscription-stats`

### Phase 4: Access Control
- Integrate subscription check into `can_access_product`

### Phase 5: Tests & Polish
- 10 tests (TDD)
- Run full suite
- Commit

## 13. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Race condition on renewal | Use atomic transactions in cron processing |
| Clock skew causing premature expiry | Use generous grace period (1 hour) |
| Double subscription creation | Unique constraint on (user_id, product_id, status='active') |
| Coin deduction without subscription | Rollback on failure (transaction pattern) |
