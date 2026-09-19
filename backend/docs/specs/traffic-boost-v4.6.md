# New Product Traffic Boost v4.6 — Feature Specification

**Owner**: Product Manager
**Status**: Draft
**Target Version**: v4.6
**Priority**: P1 (addresses seller pain point #2: low exposure for new products)
**Dependencies**: None (standalone feature, no auth required for public endpoints)

---

## 1. Feature Overview

### 1.1 Problem Statement

New products published on SkillBazaar are buried beneath established products in search results and category listings. New sellers struggle to get initial traction because:

- Search ranking is dominated by download count and sales volume
- New products start with 0 downloads and 0 sales, appearing at the bottom of every sort
- Sellers report "新商品没人看" (new products get no views) as their top frustration
- Without initial exposure, products cannot accumulate the social proof needed to rise organically

### 1.2 Solution

Implement a **New Product Traffic Boost** system that gives newly published products a temporary visibility advantage through:

1. **Boost Score**: Each new product starts with a boost score of 100, decaying exponentially (~14% per day), reaching 0 after 7 days
2. **Boost-Aware Search**: Search ranking formula incorporates boost score: `relevance * (1 + boost_score / 200)`, giving new products up to 50% ranking boost
3. **Seller Dashboard**: Analytics endpoint showing product-level stats (views, purchases, revenue) per product, helping sellers understand performance
4. **Cron Decay**: Automated daily job that decays all active boost scores
5. **Boost Reset**: Endpoint to reset boost score when a product is republished (new version or significant update)

### 1.3 User Value

| User | Value |
|------|-------|
| **New Seller** | Gets initial visibility window to accumulate first views and purchases |
| **Existing Seller** | Can reset boost when republishing updated products |
| **Buyer** | Discovers fresh content alongside established products |
| **Platform** | Higher quality catalog rotation, reduced winner-take-all dynamics |

### 1.4 Scope

- **In scope**: Boost score field, boost-aware search ranking, seller stats endpoint, cron decay job, boost reset endpoint
- **Out of scope**: A/B testing different decay curves, boost caps by category, paid boost promotions

---

## 2. API Endpoint Specifications

### 2.1 GET /api/v4/seller/stats — Get Seller Dashboard Statistics

**Purpose**: Return aggregated statistics for the authenticated seller's products, including per-product breakdown.

**Authentication**: Required (Bearer token)

**Request Parameters**: None (seller identified from auth token)

**Response (200 OK)**:

```json
{
  "total_products": 5,
  "total_views": 1240,
  "total_purchases": 38,
  "total_revenue": 125800,
  "avg_conversion_rate": 3.06,
  "products": [
    {
      "product_id": 42,
      "name": "crypto-trading-bot",
      "views": 580,
      "purchases": 22,
      "revenue_cents": 88000,
      "boost_score": 85.5
    },
    {
      "product_id": 43,
      "name": "data-analyzer",
      "views": 320,
      "purchases": 10,
      "revenue_cents": 24000,
      "boost_score": 42.0
    }
  ]
}
```

**Field Definitions**:

| Field | Type | Description |
|-------|------|-------------|
| `total_products` | int | Count of active products owned by the seller |
| `total_views` | int | Sum of views across all seller products (last 30 days) |
| `total_purchases` | int | Sum of purchases across all seller products (last 30 days) |
| `total_revenue` | int | Sum of revenue in cents across all seller products (last 30 days) |
| `avg_conversion_rate` | float | Average conversion rate (purchases/views * 100) across products |
| `products[].product_id` | int | Product ID |
| `products[].name` | str | Product name |
| `products[].views` | int | Views in last 30 days |
| `products[].purchases` | int | Purchases in last 30 days |
| `products[].revenue_cents` | int | Revenue in cents in last 30 days |
| `products[].boost_score` | float | Current boost score (0–100) |

**Time Window**: All statistics cover the last 30 days from current date.

**Status Codes**:

| Code | Condition |
|------|-----------|
| 200 | Success |
| 401 | Not authenticated |
| 500 | Server error |

---

### 2.2 POST /api/v4/cron/decay-boost — Daily Boost Decay Cron Job

**Purpose**: Decay all active product boost scores by ~14% per day, clamping to 0. Intended to be called by a scheduled cron job once daily.

**Authentication**: None (internal cron endpoint)

**Request Body**: None required

**Response (200 OK)**:

```json
{
  "decayed_count": 156,
  "reset_count": 0,
  "message": "Decayed boost scores for 156 products"
}
```

**Field Definitions**:

| Field | Type | Description |
|-------|------|-------------|
| `decayed_count` | int | Number of products whose boost score was decayed |
| `reset_count` | int | Number of products whose boost score was clamped to 0 |
| `message` | str | Human-readable summary |

**Status Codes**:

| Code | Condition |
|------|-----------|
| 200 | Success |
| 500 | Server error |

---

### 2.3 POST /api/v4/publish/boost-reset — Reset Boost Score for Republished Product

**Purpose**: Reset the boost score to 100 when a product is republished (new version, significant update, or re-listing after being unpublished).

**Authentication**: Required (Bearer token)

**Request Body**:

```json
{
  "product_id": 42,
  "reason": "version_2_published"
}
```

**Field Definitions**:

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | int | ID of the product to reset |
| `reason` | str | Reason for reset: `"version_2_published"`, `"significant_update"`, `"relist"` |

**Response (200 OK)**:

```json
{
  "product_id": 42,
  "boost_score": 100,
  "message": "Boost score reset to 100"
}
```

**Status Codes**:

| Code | Condition |
|------|-----------|
| 200 | Success |
| 400 | Invalid request body (missing product_id, bad reason) |
| 401 | Not authenticated |
| 403 | User does not own the product |
| 404 | Product not found |
| 500 | Server error |

---

### 2.4 Boost-Aware Search (Modified Existing Endpoint)

**Purpose**: The existing search endpoints (GET /api/v4/search, GET /api/products, GET /api/v4/products) incorporate boost score into ranking.

**Modified Behavior**:

The search ranking formula changes from:

```
relevance_score
```

To:

```
relevance_score * (1 + boost_score / 200)
```

Where `boost_score` ranges from 0 to 100. This gives new products up to a 50% ranking boost (when boost_score = 100) that decays daily.

**Implementation**: The `search_products()` database helper and `fetch_products()` function compute a `rank_score` in the ORDER BY clause:

```sql
ORDER BY (CASE WHEN p.boost_score IS NULL THEN 0 ELSE p.boost_score END) / 200 DESC,
         p.created_at DESC
```

**Backward Compatibility**: Products without a boost_score (legacy data before migration) default to 0.

---

## 3. Algorithm Details

### 3.1 Boost Score Initialization and Decay

```
Input: product creation or boost-reset request
Output: boost_score value (0 to 100)

INITIALIZATION (on product creation):
  boost_score = 100

DECAY (daily cron job):
  For each product where boost_score > 0:
    decay_factor = 0.86  (≈14% daily decay)
    boost_score = boost_score * decay_factor
    If boost_score < 1:
      boost_score = 0  (clamp to 0)
    UPDATE products SET boost_score = ? WHERE id = ?

MATHEMATICAL PROPERTIES:
  Day 0: 100.0 (just published)
  Day 1: 86.0
  Day 2: 73.96
  Day 3: 63.61
  Day 4: 54.70
  Day 5: 47.04
  Day 6: 40.46
  Day 7: 34.79
  Day 8: 29.92
  ...
  Effective boost duration: ~7 days to reach near-zero
```

**Decay Formula**: `boost_score = boost_score * 0.86`

### 3.2 Boost Reset

```
Input: product_id, reason
Output: boost_score = 100

STEP 1 — Validate ownership
  • Fetch product by product_id
  • If not found: return 404
  • Verify current user owns the product (seller_name matches user's nickname)
  • If not owner: return 403

STEP 2 — Reset boost score
  • UPDATE products SET boost_score = 100 WHERE id = ?

STEP 3 — Return new boost score
```

**Valid Reset Reasons**:
- `"version_2_published"` — New version published via skill_versions
- `"significant_update"` — Major content or description update
- `"relist"` — Product was unpublished and re-listed

### 3.3 Seller Stats Calculation

```
Input: user_id (from auth token)
Output: SellerStatsResponse with per-product breakdown

STEP 1 — Resolve seller identity
  • Get user by id from auth token
  • seller_name = user.nickname

STEP 2 — Get active products
  • SELECT id, name FROM products
    WHERE seller_name = ? AND status = 'active'

STEP 3 — For each product, aggregate 30-day stats
  • views = SUM(views) FROM product_analytics
    WHERE product_id = ? AND date >= date('now', '-30 days')
  • purchases = SUM(purchases) FROM product_analytics
    WHERE product_id = ? AND date >= date('now', '-30 days')
  • revenue_cents = SUM(revenue_cents) FROM product_analytics
    WHERE product_id = ? AND date >= date('now', '-30 days')
  • boost_score = p.boost_score (from products table)

STEP 4 — Compute totals
  • total_products = COUNT(active products)
  • total_views = SUM(all product views)
  • total_purchases = SUM(all product purchases)
  • total_revenue = SUM(all product revenue_cents)
  • avg_conversion_rate = (total_purchases / total_views * 100)
    If total_views = 0: avg_conversion_rate = 0

STEP 5 — Build product breakdown list
  • Sort products by revenue_cents DESC
  • Include: product_id, name, views, purchases, revenue_cents, boost_score
```

### 3.4 Boost-Aware Search Ranking

```
Input: search query with optional filters
Output: product list sorted by boost-aware relevance

STEP 1 — Execute base search (full-text + filters)
  • Same as existing search_products()

STEP 2 — Compute rank score for ordering
  • rank_score = (CASE WHEN p.boost_score IS NULL THEN 0 ELSE p.boost_score END) / 200
  • This adds 0 to 0.5 to the base relevance

STEP 3 — Apply ordering
  • ORDER BY rank_score DESC, p.created_at DESC
  • This ensures boosted products appear first within the same relevance tier
  • Among products with same boost_score, newest appears first

EXAMPLE:
  Product A: boost_score=100, created_at=2025-01-15 → rank_score=0.50
  Product B: boost_score=50, created_at=2025-01-14 → rank_score=0.25
  Product C: boost_score=0, created_at=2025-01-13 → rank_score=0.00
  Result order: A, B, C
```

### 3.5 Database Queries

**Schema migration** (add boost_score column):

```sql
ALTER TABLE products ADD COLUMN boost_score REAL DEFAULT 100;
```

**Decay query** (bulk update all active products with boost_score > 0):

```sql
UPDATE products
SET boost_score = MAX(0, boost_score * 0.86)
WHERE status = 'active' AND boost_score > 0
```

**Boost reset query**:

```sql
UPDATE products SET boost_score = 100 WHERE id = ?
```

**Seller stats query** (per-product 30-day aggregation):

```sql
SELECT
  p.id, p.name,
  COALESCE(SUM(a.views), 0) as views,
  COALESCE(SUM(a.purchases), 0) as purchases,
  COALESCE(SUM(a.revenue_cents), 0) as revenue_cents,
  p.boost_score
FROM products p
LEFT JOIN product_analytics a ON p.id = a.product_id
  AND a.date >= date('now', '-30 days')
WHERE p.seller_name = ? AND p.status = 'active'
GROUP BY p.id, p.name, p.boost_score
ORDER BY revenue_cents DESC
```

---

## 4. Error Handling

### 4.1 Request Validation Errors

| Scenario | Status | Response Body |
|----------|--------|---------------|
| `product_id` missing in boost-reset request | 400 | `{"detail": "请提供 product_id"}` |
| `reason` missing in boost-reset request | 400 | `{"detail": "请提供 reason"}` |
| `reason` not in allowed values | 400 | `{"detail": "reason 必须是 version_2_published / significant_update / relist"}` |
| Unauthenticated request to boost-reset | 401 | `{"detail": "未登录"}` |
| Auth token expired | 401 | `{"detail": "登录已过期"}` |

### 4.2 Authorization Errors

| Scenario | Status | Response Body |
|----------|--------|---------------|
| User does not own the product | 403 | `{"detail": "无权操作该商品"}` |
| Product not found | 404 | `{"detail": "商品不存在"}` |
| Seller has no active products | 200 | Empty products array, all totals = 0 |

### 4.3 Algorithm Edge Cases

| Scenario | Behavior |
|----------|----------|
| Product has no analytics data | views/purchases/revenue default to 0 |
| Product boost_score is NULL (legacy data) | Treated as 0 in search ranking and stats |
| Boost score decays to < 1 | Clamped to 0 |
| Seller stats with 0 total views | avg_conversion_rate = 0.0 |

### 4.4 Server Errors

All unhandled exceptions return 500 with generic message: `{"detail": "服务器内部错误"}`. No stack traces exposed.

---

## 5. File Structure

```
backend/
├── routers/
│   ├── traffic_boost_v4.py              # New: seller stats + boost reset endpoints
│   └── cron.py                          # Modify: add decay-boost endpoint
├── services/
│   └── traffic_boost_service.py         # New: seller stats + boost reset logic
├── models.py                            # Extend: add SellerStatsResponse, ProductStatsItem
├── database.py                          # Modify: add boost_score migration in _seed_products(),
│                                        # modify search_products() for boost-aware ranking
├── main.py                              # Add: include_router(traffic_boost_v4_router)
└── docs/specs/
    └── traffic-boost-v4.6.md            # This document
```

---

## 6. Test Strategy

Target: 8+ tests, mirroring the pattern of existing v4 feature tests.

| # | Test | Description |
|---|------|-------------|
| 1 | `test_seller_stats_returns_correct_aggregates` | GET /api/v4/seller/stats returns correct totals for a seller with multiple products |
| 2 | `test_seller_stats_includes_boost_score` | GET /api/v4/seller/stats includes boost_score for each product |
| 3 | `test_seller_stats_empty_seller` | GET /api/v4/seller/stats returns zeros for seller with no products |
| 4 | `test_boost_reset_sets_score_to_100` | POST /api/v4/publish/boost-reset sets boost_score to 100 |
| 5 | `test_boost_reset_requires_ownership` | POST /api/v4/publish/boost-reset returns 403 for non-owner |
| 6 | `test_boost_reset_invalid_reason` | POST /api/v4/publish/boost-reset returns 400 for invalid reason |
| 7 | `test_decay_boost_reduces_scores` | POST /api/v4/cron/decay-boost reduces active boost scores |
| 8 | `test_decay_boost_clamps_to_zero` | POST /api/v4/cron/decay-boost clamps very low scores to 0 |
| 9 | `test_search_ranks_boosted_products_higher` | Products with higher boost_score appear first in search results |
| 10 | `test_new_product_gets_initial_boost` | Newly created product has boost_score = 100 |

---

## 7. Integration Points

| System | Usage |
|--------|-------|
| `products` table | Store boost_score column; source of product data |
| `product_analytics` table | Source of views/purchases/revenue for seller stats |
| `database.py` helpers | `fetch_product_by_id()`, `search_products()`, `_seed_products()` for migration |
| `routers.user_v2` | `get_current_user` dependency for authenticated endpoints |
| `FastAPI router system` | Standard v4 router registration in `main.py` |
| `cron.py` router | Add decay-boost endpoint to existing cron router |

**Future Integration**:
- Product creation flow: Automatically set boost_score = 100 on new products
- Product detail page: Display boost status indicator ("新商品扶持中")
- Seller dashboard UI: Show boost score per product with countdown to expiration
- Analytics v4: Include boost_score in product analytics reports

---

## 8. Non-Functional Requirements

| Requirement | Target | Notes |
|-------------|--------|-------|
| Response latency (seller stats) | < 300ms | One aggregated SQL query with LEFT JOIN |
| Response latency (boost reset) | < 100ms | Single UPDATE query |
| Response latency (decay boost) | < 500ms | Bulk UPDATE on active products |
| Search performance impact | < 5% overhead | Simple column addition to ORDER BY |
| Cacheability | Optional | Seller stats can be cached for 5 min per user |
| Rate limiting | None (public for decay) | Low compute cost, internal endpoint |
| Boost score precision | 1 decimal place | Stored as REAL, displayed as float |
| Localization | Chinese | All reason strings and messages in Chinese |

---

## Appendix A: Model Definitions

### SellerStatsResponse

```python
class ProductStatsItem(BaseModel):
    product_id: int
    name: str
    views: int = 0
    purchases: int = 0
    revenue_cents: int = 0
    boost_score: float = 0.0

class SellerStatsResponse(BaseModel):
    total_products: int
    total_views: int
    total_purchases: int
    total_revenue: int
    avg_conversion_rate: float
    products: list[ProductStatsItem]
```

### BoostResetRequest

```python
class BoostResetRequest(BaseModel):
    product_id: int
    reason: str  # "version_2_published" | "significant_update" | "relist"
```

### BoostResetResponse

```python
class BoostResetResponse(BaseModel):
    product_id: int
    boost_score: float
    message: str
```

### DecayBoostResponse

```python
class DecayBoostResponse(BaseModel):
    decayed_count: int
    reset_count: int
    message: str
```
