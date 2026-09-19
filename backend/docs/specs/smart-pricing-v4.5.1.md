# Smart Pricing Suggestions v4.5.1 — Feature Specification

**Owner**: Product Manager
**Status**: Draft
**Target Version**: v4.5.1
**Priority**: P1 (addresses seller pain point #2 and buyer pain point #10)
**Dependencies**: None (standalone feature, no auth required)

---

## 1. Feature Overview

### 1.1 Problem Statement

**Buyer pain**: Skill prices range from ¥1 to ¥999 with no transparent reference. Buyers cannot tell if a price is fair — "不知道值不值" (don't know if it's worth it).

**Seller pain**: First-time sellers have no market reference for pricing. Set too high and no one buys; set too low and leave money on the table — "定价困难" (difficult to price).

### 1.2 Solution

Provide data-driven price suggestions to sellers (and price transparency to buyers) by analyzing comparable products in the same category. The algorithm computes a market median, then adjusts based on the seller's reputation signals (rating, download count).

### 1.3 User Value

| User | Value |
|------|-------|
| **Seller (new)** | Gets a realistic price range before listing, reducing trial-and-error |
| **Seller (existing)** | Can re-evaluate pricing when adding new products |
| **Buyer** | Sees market context (average price, competitor count) on product pages |
| **Platform** | More realistic pricing → higher conversion → better trust |

### 1.4 Scope

- **In scope**: Two public API endpoints, pricing algorithm, price trend analytics
- **Out of scope**: A/B pricing testing (v4.6+), dynamic auto-pricing, price change notifications

---

## 2. API Endpoint Specifications

### 2.1 POST /api/v4/pricing/suggest — Get Price Suggestion

**Purpose**: Return a data-informed price suggestion for a product based on market data.

**Authentication**: None (public endpoint)

**Request Body** (one of two modes):

```json
// Mode A: By product ID
{
  "product_id": 42
}

// Mode B: By product attributes (for pre-listing preview)
{
  "category": "Agent",
  "name": "crypto-trading-bot",
  "description": "Autonomous cryptocurrency trading agent"
}
```

**Response (200 OK)**:

```json
{
  "suggested_price": 349,
  "price_range": {
    "min": 199,
    "max": 499
  },
  "reason": "同类商品中位价为 ¥299，该商品描述复杂度较高，建议上浮 15%",
  "market_avg": 299.0,
  "competitors_count": 12
}
```

**Field Definitions**:

| Field | Type | Description |
|-------|------|-------------|
| `suggested_price` | int | Recommended price, rounded to nearest integer |
| `price_range.min` | int | Lower bound of suggested range |
| `price_range.max` | int | Upper bound of suggested range |
| `reason` | str | Human-readable explanation (Chinese) of the suggestion |
| `market_avg` | float | Median price of competitor products used |
| `competitors_count` | int | Number of comparable products found |

**Low-Confidence Response** (when < 3 competitors):

```json
{
  "suggested_price": 299,
  "price_range": {
    "min": 149,
    "max": 449
  },
  "reason": "同类商品样本较少（2个），建议范围较宽，仅供参考",
  "market_avg": 299.0,
  "competitors_count": 2,
  "confidence": "low"
}
```

The `confidence` field is omitted in the normal (high-confidence) response.

**Status Codes**:

| Code | Condition |
|------|-----------|
| 200 | Success |
| 400 | Invalid request body (missing required fields, bad types) |
| 404 | `product_id` specified but not found |
| 500 | Server error |

---

### 2.2 GET /api/v4/pricing/trends/{category} — Get Category Price Trends

**Purpose**: Return price statistics and trend direction for a category over a time window.

**Authentication**: None (public endpoint)

**Request Parameters**:

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `category` | str | Yes (path) | — | Product category (e.g., "Agent", "Skill", "Cron", "Workflow") |
| `days` | int | No (query) | 30 | Lookback window in days |

**Response (200 OK)**:

```json
{
  "category": "Agent",
  "avg_price": 312.5,
  "min_price": 99,
  "max_price": 599,
  "price_trend": "stable",
  "sample_count": 18,
  "period_days": 30
}
```

**Field Definitions**:

| Field | Type | Description |
|-------|------|-------------|
| `category` | str | The queried category |
| `avg_price` | float | Average price of active products in category |
| `min_price` | int | Lowest price in category |
| `max_price` | int | Highest price in category |
| `price_trend` | str | One of: `"up"`, `"down"`, `"stable"` |
| `sample_count` | int | Number of active products in category |
| `period_days` | int | The lookback window used |

**Trend Calculation**:

- Compare average price of products created in the first half of the period vs. the second half
- If second-half average > first-half average by > 5%: `"up"`
- If second-half average < first-half average by > 5%: `"down"`
- Otherwise: `"stable"`

**Status Codes**:

| Code | Condition |
|------|-----------|
| 200 | Success |
| 400 | Invalid `days` parameter (< 1 or > 365) |
| 500 | Server error |

---

## 3. Algorithm Details

### 3.1 Price Suggestion Algorithm

```
Input: product_id OR (category, name, description)
Output: suggested_price, price_range, reason, market_avg, competitors_count

STEP 1 — Identify the target category
  • If product_id given: look up product in DB, extract category
  • If category given directly: use it
  • If neither: return 400

STEP 2 — Find competitors
  • Query products WHERE category = target_category AND status = 'active'
  • Exclude the product itself (if product_id given)
  • Cap at 20 competitors, minimum 3 needed for high confidence

STEP 3 — Calculate market median
  • Collect competitor prices
  • Sort ascending, take median (or average of two middle values if even count)
  • This is market_avg

STEP 4 — Determine base adjustment factor
  • Start with ±20% range around market median
  • price_range.min = floor(market_avg * 0.80)
  • price_range.max = ceil(market_avg * 1.20)

STEP 5 — Apply seller-specific adjustment (when product_id given)
  • Fetch the product's seller data: rating, downloads
  • Rating factor:
    - rating >= 4.8: multiplier = 1.10 (premium seller, can charge more)
    - rating 4.5–4.79: multiplier = 1.05
    - rating 4.0–4.49: multiplier = 1.00 (baseline)
    - rating < 4.0: multiplier = 0.90 (discount to compete)
  • Downloads factor (logarithmic scale):
    - downloads >= 10000: +5%
    - downloads 1000–9999: +3%
    - downloads 100–999: +0%
    - downloads < 100: -3%
  • Combined adjustment = rating_factor × downloads_factor
  • Clamp combined adjustment to [0.80, 1.20] range
  • suggested_price = round(market_avg × combined_adjustment)
  • Adjust price_range proportionally

STEP 6 — Build reason string (Chinese)
  • Include: competitor count, market median, adjustment direction
  • Example templates:
    - "同类商品中位价为 ¥{median}，共 {count} 个竞品。卖家评分 {rating}，建议价格 {direction} {pct}%"
    - "同类商品样本较少（{count}个），建议范围较宽，仅供参考"

STEP 7 — Confidence flag
  • competitors_count >= 3: omit confidence field (implicit high)
  • competitors_count < 3: add "confidence": "low"
```

### 3.2 Price Trend Algorithm

```
Input: category, days
Output: avg_price, min_price, max_price, price_trend, sample_count

STEP 1 — Query active products in category
  • SELECT price, created_at FROM products
    WHERE category = ? AND status = 'active'

STEP 2 — Compute statistics
  • avg_price = AVG(price)
  • min_price = MIN(price)
  • max_price = MAX(price)
  • sample_count = COUNT(*)

STEP 3 — Compute trend (if days >= 14)
  • Split products by created_at into two halves of the period
  • First half: created_at < (now - days/2 days)
  • Second half: created_at >= (now - days/2 days)
  • avg_first = AVG(price) for first half
  • avg_second = AVG(price) for second half
  • If avg_second > avg_first × 1.05: trend = "up"
  • If avg_second < avg_first × 0.95: trend = "down"
  • Else: trend = "stable"

STEP 4 — For short periods (< 14 days)
  • trend = "stable" (not enough data for meaningful comparison)
```

### 3.3 Database Queries

Both endpoints query the existing `products` table. No new tables or migrations are needed.

**Competitor query** (used by suggest):

```sql
SELECT id, name, price, rating, downloads, sales
FROM products
WHERE category = ? AND status = 'active' AND id != ?
ORDER BY created_at DESC
LIMIT 20
```

**Category stats query** (used by trends):

```sql
SELECT price, created_at
FROM products
WHERE category = ? AND status = 'active'
```

---

## 4. Error Handling

### 4.1 Request Validation Errors

| Scenario | Status | Response Body |
|----------|--------|---------------|
| Empty request body | 400 | `{"detail": "请求体不能为空"}` |
| Neither `product_id` nor `category` provided | 400 | `{"detail": "请提供 product_id 或 category"}` |
| Both `product_id` and `category` provided | 400 | `{"detail": "请仅提供 product_id 或 category，不要同时提供"}` |
| `product_id` not found | 404 | `{"detail": "商品不存在"}` |
| `product_id` is not an integer | 422 | FastAPI validation error |
| `category` is empty string | 400 | `{"detail": "分类不能为空"}` |
| `days` < 1 or > 365 | 400 | `{"detail": "days 参数必须在 1-365 之间"}` |

### 4.2 Algorithm Edge Cases

| Scenario | Behavior |
|----------|----------|
| Category has 0 active products | Return 404 with message "该分类暂无商品数据" |
| Category has 1–2 active products | Return suggestion with `confidence: "low"` and wider range |
| All competitors have same price | Range = [price, price], suggested = price |
| Product found but category is empty/null | Return 400 |

### 4.3 Server Errors

All unhandled exceptions return 500 with generic message: `{"detail": "服务器内部错误"}`. No stack traces exposed.

---

## 5. File Structure

```
backend/
├── routers/
│   └── pricing_v4.py              # New: router with two endpoints
├── services/
│   └── pricing_service.py         # New: algorithm implementation
├── models.py                       # Extend: add PricingSuggestionResponse, PricingTrendResponse, etc.
├── database.py                     # No changes needed (uses existing products table)
├── main.py                         # Add: include_router(pricing_router)
└── docs/specs/
    └── smart-pricing-v4.5.1.md     # This document
```

---

## 6. Test Strategy

Target: 8+ tests, mirroring the pattern of existing v4 feature tests.

| # | Test | Description |
|---|------|-------------|
| 1 | `test_suggest_with_product_id` | POST with valid product_id returns suggestion with all fields |
| 2 | `test_suggest_with_category_name_description` | POST with category+name+description works |
| 3 | `test_suggest_nonexistent_product_id_returns_404` | POST with nonexistent product_id returns 404 |
| 4 | `test_suggest_empty_request_returns_400` | POST with empty body returns 400 |
| 5 | `test_trends_returns_category_stats` | GET trends for a populated category returns stats |
| 6 | `test_trends_with_days_parameter` | GET trends with days=7 works |
| 7 | `test_trends_empty_category_returns_404` | GET trends for empty category returns 404 |
| 8 | `test_suggest_price_within_competitor_range` | Suggested price falls within calculated range |

---

## 7. Integration Points

| System | Usage |
|--------|-------|
| `products` table | Source of competitor data (no schema changes) |
| `database.py` helpers | `fetch_product_by_id()` for product lookup |
| FastAPI router system | Standard v4 router registration in `main.py |

**Future Integration**:
- Product creation flow (v4.6): Call `/api/v4/pricing/suggest` during publish wizard
- Product detail page: Display `market_avg` and `competitors_count` as price context
- BS 买卖助手 (AI Copilot): Include pricing suggestion in publish conversation flow

---

## 8. Non-Functional Requirements

| Requirement | Target | Notes |
|-------------|--------|-------|
| Response latency | < 200ms | Single SQL query + simple computation |
| Cacheability | Optional | Results can be cached for 5 min per category |
| Rate limiting | None (public) | Low compute cost, no auth barrier |
| Localization | Chinese | All reason strings in Chinese |
