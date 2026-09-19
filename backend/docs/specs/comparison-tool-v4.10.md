# Comparison Tool — v4.10 Feature Spec

## 1. Overview

Add a side-by-side comparison feature allowing buyers to compare up to 4 Skills simultaneously on criteria like price, eval score, features, and seller reputation. This helps buyers make informed decisions when choosing between similar products.

## 2. Problem Statement

**Buyer Pain Point #1**: "不知道买什么 — 信息过载与选择困难"
- Users see multiple similar Skills but can't easily compare them
- Current experience requires navigating back and forth between product pages
- No structured comparison view to weigh trade-offs

**Current State**:
- Search results show individual product cards
- Product detail pages show full info but one at a time
- No mechanism to compare multiple products side-by-side

**Goal**: Enable structured comparison of up to 4 Skills to reduce decision friction.

## 3. Scope

### In Scope
- Compare button on product cards and detail pages
- Comparison page/panel with side-by-side layout
- Compare up to 4 products
- Key comparison dimensions: price, eval score, features, seller stats
- Save/Share comparison (via URL)
- Clear comparison and add/remove products

### Out of Scope
- Comparison of more than 4 products
- AI-powered comparison recommendation
- Comparison history/analytics
- Print/export comparison

## 4. Database Schema

### 4.1 No new tables needed

Comparison is a stateless feature — the comparison state is stored client-side or in a shareable URL parameter. No persistent storage required.

## 5. API Endpoints

### 5.1 GET `/api/v4/compare`

Retrieve comparison data for up to 4 products.

**Auth**: Optional (more info for logged-in users)
**Query Params**: `product_ids` (comma-separated, e.g., `?product_ids=1,2,3`)
**Response**:
```json
{
    "products": [
        {
            "id": 1,
            "name": "Data Analyzer",
            "price": 100,
            "seller_name": "alice",
            "eval_score": 0.92,
            "eval_status": "passed",
            "eval_badge": {"tier": "excellent", "color": "#22c55e", "label": "A+", "score_display": "92/100"},
            "category": "Skill",
            "sales": 150,
            "downloads": 320,
            "description": "Analyze data with AI...",
            "features": ["支持CSV", "API调用", "批量处理"],
            "subscription_plans": [{"plan": "monthly", "price": 50}],
            "created_at": "2025-01-15T00:00:00"
        }
    ],
    "comparison_matrix": {
        "price": [100, 80, 120],
        "eval_score": [0.92, 0.85, 0.78],
        "sales": [150, 200, 80],
        "downloads": [320, 450, 210]
    }
}
```

**Business Rules**:
- Max 4 products per comparison
- Returns 400 if more than 4 product_ids
- Returns 404 if any product_id doesn't exist
- Includes eval_badge for each product
- Includes seller stats (sales, downloads) from product_analytics

### 5.2 POST `/api/v4/compare/save` (optional)

Save a comparison for later reference.

**Auth**: Required
**Request**:
```json
{
    "product_ids": [1, 2, 3],
    "name": "My Comparison"
}
```

**Response**:
```json
{
    "comparison_id": "abc123",
    "share_url": "/compare/abc123",
    "product_ids": [1, 2, 3]
}
```

## 6. Models (`models.py`)

```python
class CompareRequest(BaseModel):
    product_ids: list[int]

class CompareProductResponse(BaseModel):
    id: int
    name: str
    price: int
    seller_name: str
    eval_score: float | None = None
    eval_status: str | None = None
    eval_badge: dict | None = None
    category: str
    sales: int = 0
    downloads: int = 0
    description: str
    features: list[str] = []
    subscription_plans: list[dict] = []
    created_at: str

class CompareResponse(BaseModel):
    products: list[CompareProductResponse]
    comparison_matrix: dict | None = None

class ComparisonSaveRequest(BaseModel):
    product_ids: list[int]
    name: str | None = None

class ComparisonSaveResponse(BaseModel):
    comparison_id: str
    share_url: str
    product_ids: list[int]
```

## 7. Service Layer

### 7.1 `comparison_service.py`

```python
async def get_comparison_data(product_ids: list[int], user_id: str | None = None) -> dict:
    """Get comparison data for up to 4 products."""

async def save_comparison(user_id: str, product_ids: list[int], name: str | None) -> dict:
    """Save a comparison for later reference."""
```

## 8. Frontend Changes

### 8.1 Compare Button

Add "对比" (Compare) button to:
- Product cards in search results
- Product detail pages

Button behavior:
- First click: adds product to comparison (max 4)
- Shows counter badge (e.g., "对比 (2)")
- When 2+ products selected: shows "开始对比" button
- Disabled when 4 products already selected

### 8.2 Comparison Page

Layout:
- Header: product names, remove buttons
- Table/side-by-side cards with rows for each attribute
- Sticky header with "Clear All" and "Share" buttons
- Responsive: horizontal scroll on mobile

Comparison dimensions:
- Price (with subscription price if available)
- Eval score + badge
- Sales/Downloads
- Features list
- Seller info
- Description

### 8.3 Comparison Drawer (optional)

A slide-out drawer from the bottom showing current comparison selection:
- Shows selected product thumbnails
- Quick remove buttons
- "Compare Now" CTA

## 9. Implementation Phases

### Phase 1: Backend API
- `GET /api/v4/compare`
- `compute_comparison_matrix` helper

### Phase 2: Frontend Components
- Compare button on product cards
- Comparison page/panel
- Comparison drawer

### Phase 3: Tests & Polish
- 8 tests (TDD)
- Run full suite
- Commit

## 10. Test Plan

| ID | Test Name | What It Verifies |
|----|-----------|------------------|
| CT-01 | `test_compare_two_products` | Returns data for 2 products |
| CT-02 | `test_compare_four_products` | Max 4 products allowed |
| CT-03 | `test_compare_more_than_four_rejected` | 5+ products returns 400 |
| CT-04 | `test_compare_nonexistent_product` | Returns 404 for invalid product |
| CT-05 | `test_compare_includes_eval_badge` | Response includes eval_badge |
| CT-06 | `test_compare_matrix_present` | comparison_matrix is included |
| CT-07 | `test_compare_includes_seller_stats` | Sales/downloads included |
| CT-08 | `test_compare_single_product` | Single product comparison works |
